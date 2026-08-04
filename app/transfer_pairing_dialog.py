from __future__ import annotations

import threading

from packages.qt_compat.QtCore import Qt, QTimer
from packages.qt_compat import pyqtSignal as Signal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QListWidget, QListWidgetItem, QWidget,
)


_STYLE = """
QDialog { background: #16162A; }
QLabel#title { color: #E8EEFF; font-size: 18px; font-weight: 700; }
QLabel#subtitle { color: #8080B0; font-size: 12px; }
QLabel#code_display {
    color: #FF9900; font-size: 26px; font-weight: 800;
    font-family: monospace; letter-spacing: 4px;
    background: #1E1E38; border: 1px solid #3A3A60; border-radius: 8px;
    padding: 14px;
}
QLabel#countdown { color: #8080B0; font-size: 12px; }
QLabel#device_name { color: #E8EEFF; font-size: 13px; font-weight: 600; }
QLabel#device_status { color: #8080B0; font-size: 11px; }
QLabel#device_status_revoked { color: #E05050; font-size: 11px; }
QPushButton#btn_add {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FF7700, stop:1 #FF4400);
    color: white; border: none; border-radius: 8px; padding: 10px 20px;
    font-size: 13px; font-weight: 700;
}
QPushButton#btn_add:hover { background: #FF9900; }
QPushButton#btn_add:disabled { background: #553322; color: #886655; }
QPushButton#btn_revoke {
    background: transparent; color: #E05050; border: 1px solid #E05050;
    border-radius: 6px; padding: 4px 12px; font-size: 11px;
}
QPushButton#btn_revoke:hover { background: rgba(224,80,80,0.12); }
QPushButton#btn_revoke:disabled { background: transparent; color: #553030; border-color: #553030; }
QPushButton#btn_close {
    background: transparent; color: #6060A0; border: 1px solid #3A3A60;
    border-radius: 8px; padding: 9px 18px; font-size: 13px;
}
QLabel#status_err { color: #E05050; font-size: 12px; }
QListWidget {
    background: #1E1E38; border: 1px solid #3A3A60; border-radius: 6px;
}
QFrame#divider { background: #2A2A4A; }
"""

_PAIRING_TTL_SECONDS = 120


class TransferPairingDialog(QDialog):
    """Quản lý thiết bị companion (iPhone/iPad) cho key doanh nghiệp 3TR-E.

    Chỉ implement Phase 1 (SPEC_TRANSFER_GATEWAY_V2.md) — ghép nối bằng
    mã 8 ký tự + thu hồi thiết bị. Chưa có phần truyền PDF (Phase 2).
    """

    _sig_session_ok = Signal(dict)
    _sig_session_err = Signal(str)
    _sig_devices_ok = Signal(list)
    _sig_devices_err = Signal(str)
    _sig_revoke_ok = Signal(str)
    _sig_revoke_err = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thiết bị ScanDoc")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_STYLE)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self._seconds_left = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        title = QLabel("Thiết bị ScanDoc")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel("Ghép nối iPhone/iPad với key doanh nghiệp — không cần tài khoản.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._code_label = QLabel("")
        self._code_label.setObjectName("code_display")
        self._code_label.setAlignment(Qt.AlignCenter)
        self._code_label.hide()
        layout.addWidget(self._code_label)

        self._countdown_label = QLabel("")
        self._countdown_label.setObjectName("countdown")
        self._countdown_label.setAlignment(Qt.AlignCenter)
        self._countdown_label.hide()
        layout.addWidget(self._countdown_label)

        self._status_label = QLabel("")
        self._status_label.setObjectName("status_err")
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        layout.addWidget(self._status_label)

        self._btn_add = QPushButton("Thêm thiết bị")
        self._btn_add.setObjectName("btn_add")
        self._btn_add.clicked.connect(self._on_add_clicked)
        layout.addWidget(self._btn_add)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        list_label = QLabel("Thiết bị đã ghép nối")
        list_label.setObjectName("subtitle")
        layout.addWidget(list_label)

        self._device_list = QListWidget()
        self._device_list.setMinimumHeight(160)
        layout.addWidget(self._device_list)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("btn_close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._sig_session_ok.connect(self._on_session_ok)
        self._sig_session_err.connect(self._on_session_err)
        self._sig_devices_ok.connect(self._on_devices_ok)
        self._sig_devices_err.connect(self._on_devices_err)
        self._sig_revoke_ok.connect(self._on_revoke_ok)
        self._sig_revoke_err.connect(self._on_revoke_err)

        self._refresh_devices()

    # ── Tạo phiên ghép nối ───────────────────────────────────────────────

    def _on_add_clicked(self) -> None:
        self._status_label.hide()
        self._btn_add.setEnabled(False)
        self._btn_add.setText("Đang tạo mã...")

        def _run():
            try:
                from packages.transfer import get_transfer_client
                result = get_transfer_client().create_companion_session()
                self._sig_session_ok.emit(result)
            except Exception as exc:  # noqa: BLE001 — báo lỗi lên UI, không crash
                self._sig_session_err.emit(str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_session_ok(self, result: dict) -> None:
        self._btn_add.setEnabled(True)
        self._btn_add.setText("Thêm thiết bị")
        code = result.get("code", "")
        self._code_label.setText(code)
        self._code_label.show()
        self._seconds_left = _PAIRING_TTL_SECONDS
        self._countdown_label.show()
        self._tick_countdown()
        self._countdown_timer.start(1000)

    def _on_session_err(self, message: str) -> None:
        self._btn_add.setEnabled(True)
        self._btn_add.setText("Thêm thiết bị")
        self._status_label.setText(message)
        self._status_label.show()

    def _tick_countdown(self) -> None:
        if self._seconds_left <= 0:
            self._countdown_timer.stop()
            self._code_label.hide()
            self._countdown_label.hide()
            self._refresh_devices()
            return
        self._countdown_label.setText(f"Mã hết hạn sau {self._seconds_left} giây")
        self._seconds_left -= 1

    # ── Danh sách thiết bị ───────────────────────────────────────────────

    def _refresh_devices(self) -> None:
        def _run():
            try:
                from packages.transfer import get_transfer_client
                devices = get_transfer_client().list_devices()
                self._sig_devices_ok.emit(devices)
            except Exception as exc:  # noqa: BLE001
                self._sig_devices_err.emit(str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_devices_ok(self, devices: list) -> None:
        self._device_list.clear()
        for device in devices:
            self._add_device_item(device)

    def _on_devices_err(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.show()

    def _add_device_item(self, device: dict) -> None:
        item = QListWidgetItem()
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 6, 10, 6)

        text_col = QVBoxLayout()
        name_label = QLabel(device.get("display_name") or device.get("device_type", ""))
        name_label.setObjectName("device_name")
        text_col.addWidget(name_label)

        revoked = bool(device.get("revoked_at"))
        status_label = QLabel("Đã thu hồi" if revoked else "Đang hoạt động")
        status_label.setObjectName("device_status_revoked" if revoked else "device_status")
        text_col.addWidget(status_label)
        row_layout.addLayout(text_col)
        row_layout.addStretch(1)

        btn_revoke = QPushButton("Thu hồi")
        btn_revoke.setObjectName("btn_revoke")
        btn_revoke.setEnabled(not revoked)
        device_id = device.get("device_id", "")
        btn_revoke.clicked.connect(lambda _=False, did=device_id, btn=btn_revoke: self._on_revoke_clicked(did, btn))
        row_layout.addWidget(btn_revoke)

        item.setSizeHint(row.sizeHint())
        self._device_list.addItem(item)
        self._device_list.setItemWidget(item, row)

    # ── Thu hồi thiết bị ─────────────────────────────────────────────────

    def _on_revoke_clicked(self, device_id: str, btn: QPushButton) -> None:
        btn.setEnabled(False)
        btn.setText("Đang thu hồi...")

        def _run():
            try:
                from packages.transfer import get_transfer_client
                get_transfer_client().revoke_device(device_id)
                self._sig_revoke_ok.emit(device_id)
            except Exception as exc:  # noqa: BLE001
                self._sig_revoke_err.emit(str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_revoke_ok(self, device_id: str) -> None:
        self._refresh_devices()

    def _on_revoke_err(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.show()
        self._refresh_devices()
