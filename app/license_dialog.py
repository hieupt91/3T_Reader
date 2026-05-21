from __future__ import annotations

import re
import threading

_KEY_RE = re.compile(r'^3TR-[BPE]-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')

from packages.qt_compat.QtCore import Qt, QTimer
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QApplication,
)


# ── stylesheet ──────────────────────────────────────────────────────────────

_STYLE = """
QDialog {
    background: #16162A;
}
QLabel#title {
    color: #E8EEFF;
    font-size: 18px;
    font-weight: 700;
}
QLabel#subtitle {
    color: #8080B0;
    font-size: 12px;
}
QLabel#field_label {
    color: #B0B8E0;
    font-size: 12px;
    font-weight: 600;
}
QLineEdit {
    background: #1E1E38;
    color: #E8EEFF;
    border: 1px solid #3A3A60;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    font-family: monospace;
    letter-spacing: 1px;
}
QLineEdit:focus {
    border-color: #FF6600;
}
QPushButton#btn_activate {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #FF7700, stop:1 #FF4400);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#btn_activate:hover { background: #FF9900; }
QPushButton#btn_activate:pressed { background: #DD4400; }
QPushButton#btn_activate:disabled { background: #553322; color: #886655; }
QPushButton#btn_quit {
    background: transparent;
    color: #6060A0;
    border: 1px solid #3A3A60;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
}
QPushButton#btn_quit:hover { color: #E05050; border-color: #E05050; }
QLabel#status_ok  { color: #4fc080; font-size: 12px; }
QLabel#status_err { color: #E05050; font-size: 12px; }
QLabel#status_info { color: #8080B0; font-size: 12px; }
QFrame#divider { background: #2A2A4A; }
"""


# ── dialog ───────────────────────────────────────────────────────────────────

class LicenseActivationDialog(QDialog):
    """Modal dialog — hiện khi app khởi động và chưa có license hợp lệ."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kích hoạt 3T Reader")
        self.setModal(True)
        self.setFixedSize(480, 340)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )
        self._activated = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # Header
        title = QLabel("Kích hoạt 3T Reader")
        title.setObjectName("title")
        root.addWidget(title)

        root.addSpacing(4)
        sub = QLabel("Nhập license key để sử dụng đầy đủ tính năng.")
        sub.setObjectName("subtitle")
        root.addWidget(sub)

        root.addSpacing(24)

        # License key field
        lbl_key = QLabel("License Key")
        lbl_key.setObjectName("field_label")
        root.addWidget(lbl_key)
        root.addSpacing(6)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("3TR-P-XXXX-XXXX-XXXX")
        self._key_input.setMaxLength(64)
        self._key_input.textChanged.connect(self._on_input_changed)
        root.addWidget(self._key_input)

        root.addSpacing(20)

        # Status label
        self._status = QLabel("")
        self._status.setObjectName("status_info")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        root.addStretch()

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        root.addWidget(div)
        root.addSpacing(16)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._btn_quit = QPushButton("Thoát")
        self._btn_quit.setObjectName("btn_quit")
        self._btn_quit.clicked.connect(self._on_quit)

        self._btn_activate = QPushButton("Kích hoạt")
        self._btn_activate.setObjectName("btn_activate")
        self._btn_activate.setEnabled(False)
        self._btn_activate.clicked.connect(self._on_activate)
        self._key_input.returnPressed.connect(self._btn_activate.click)

        btn_row.addWidget(self._btn_quit)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_activate)

        root.addLayout(btn_row)

    # ── slots ────────────────────────────────────────────────────────────────

    def _on_input_changed(self, text: str):
        key = text.strip().upper()
        valid = bool(_KEY_RE.match(key))
        self._btn_activate.setEnabled(valid)
        if key and not valid:
            self._set_status("Định dạng key không đúng. VD: 3TR-P-XXXX-XXXX-XXXX", "err")
        else:
            self._set_status("", "info")

    def _on_activate(self):
        key = self._key_input.text().strip().upper()
        if not key:
            return

        self._btn_activate.setEnabled(False)
        self._btn_quit.setEnabled(False)
        self._set_status("Đang kích hoạt…", "info")

        def _do():
            try:
                from packages.license_client import get_license_client
                from packages.license_client.fingerprint import get_device_fingerprint
                client = get_license_client()
                fp = get_device_fingerprint()
                result = client.activate(key, "", fp)
                if result.status.active:
                    QTimer.singleShot(0, lambda: self._finish_ok(result))
                else:
                    QTimer.singleShot(0, lambda: self._finish_err("Kích hoạt thất bại."))
            except RuntimeError as e:
                msg = str(e)
                QTimer.singleShot(0, lambda: self._finish_err(msg))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._finish_err(f"Lỗi kết nối: {e}"))

        threading.Thread(target=_do, daemon=True).start()

    def _finish_ok(self, result):
        exp = result.status.expires_at
        exp_str = exp.strftime("%d/%m/%Y") if exp else "không xác định"
        self._set_status(f"Kích hoạt thành công! Hết hạn: {exp_str}", "ok")
        self._activated = True
        QTimer.singleShot(1200, self.accept)

    def _finish_err(self, msg: str):
        self._set_status(msg, "err")
        self._btn_activate.setEnabled(True)
        self._btn_quit.setEnabled(True)

    def _on_quit(self):
        QApplication.quit()

    def _set_status(self, text: str, level: str):
        self._status.setText(text)
        obj = {"ok": "status_ok", "err": "status_err"}.get(level, "status_info")
        self._status.setObjectName(obj)
        self._status.setStyleSheet(
            {"ok": "color:#4fc080;", "err": "color:#E05050;"}.get(level, "color:#8080B0;")
        )

    def was_activated(self) -> bool:
        return self._activated


# ── public helpers ────────────────────────────────────────────────────────────

def check_license_on_startup(window) -> bool:
    """Kiểm tra license khi khởi động. Trả về True nếu được phép chạy."""
    from app.config import VPS_LICENSE_BASE_URL
    if not VPS_LICENSE_BASE_URL:
        return True  # bypass mode — không cần license

    from packages.license_client import get_license_client
    client = get_license_client()
    status = client.validate_cached()

    if status.active:
        _start_heartbeat(window, client)
        return True

    # Chưa kích hoạt hoặc hết hạn → hiện dialog
    dlg = LicenseActivationDialog(window)
    dlg.exec()

    if dlg.was_activated():
        _start_heartbeat(window, get_license_client())
        return True

    return False  # user bấm Thoát


def _start_heartbeat(window, client):
    """Gửi heartbeat mỗi 6 giờ trong background."""
    timer = QTimer(window)
    timer.setInterval(6 * 3600 * 1000)  # 6h

    def _beat():
        def _worker():
            try:
                status = client.heartbeat()
                if not status.active:
                    QTimer.singleShot(0, lambda: _warn_expired(window))
            except Exception:
                pass  # offline — bỏ qua, grace period xử lý
        threading.Thread(target=_worker, daemon=True).start()

    timer.timeout.connect(_beat)
    timer.start()
    window._license_heartbeat_timer = timer  # giữ reference


def _warn_expired(window):
    from app.dialogs import show_warning
    show_warning(
        window,
        "License hết hạn",
        "License đã bị thu hồi hoặc hết hạn.\n"
        "Vui lòng liên hệ 3T Company để gia hạn.",
    )
