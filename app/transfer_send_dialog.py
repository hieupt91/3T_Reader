from __future__ import annotations

"""Dialog "Chuyển tài liệu" — gửi PDF đang mở sang thiết bị companion qua
P2P WebRTC.

Từ 11/08/2026 (xem docs/PLAN_2026-08-11_reverse_qr_send_flow.md, nhánh
phase1-backend): ScanDoc (điện thoại) mới là bên TẠO PHIÊN + hiện mã/QR khi
người dùng bấm "Nhận tài liệu" trên app - desktop (bên gửi) chỉ cần NHẬP mã
đó vào rồi tham gia phiên (đúng nguyên tắc "bên nhận luôn tạo phiên, bên gửi
luôn kết nối tới bằng mã đó"). Desktop vẫn giữ vai trò WebRTC offerer/đẩy
bytes như trước (webrtc_transport.guest_send_file_async, gọi lại nguyên vẹn
send_file() cũ) - chỉ đổi CÁCH lấy transfer_session_id (nhập tay/dán mã thay
vì tự tạo + hiện QR của mình).
"""

import asyncio
import os
import threading

from packages.qt_compat.QtCore import Qt
from packages.qt_compat import pyqtSignal as Signal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QLineEdit,
)

from app.transfer_pairing_dialog import _extract_session_id, _is_short_code, _is_pairing_qr_payload


_STYLE = """
QDialog { background: #16162A; }
QLabel#title { color: #E8EEFF; font-size: 18px; font-weight: 700; }
QLabel#subtitle { color: #8080B0; font-size: 12px; }
QLabel#file_name { color: #E8EEFF; font-size: 13px; font-weight: 600; }
QLabel#file_meta { color: #8080B0; font-size: 11px; }
QLabel#code_display {
    color: #FF9900; font-size: 26px; font-weight: 800;
    font-family: monospace; letter-spacing: 2px;
    background: #1E1E38; border: 1px solid #3A3A60; border-radius: 8px;
    padding: 14px;
}
QLabel#qr_display {
    background: #FFFFFF; border: 1px solid #3A3A60; border-radius: 8px;
    padding: 10px;
}
QLabel#status_line { color: #8080B0; font-size: 12px; }
QLabel#status_err { color: #E05050; font-size: 12px; }
QLabel#status_ok { color: #34C759; font-size: 13px; font-weight: 700; }
QLineEdit#code_input {
    color: #E8EEFF; font-size: 14px; font-family: monospace;
    background: #1E1E38; border: 1px solid #3A3A60; border-radius: 8px;
    padding: 10px 12px;
}
QLineEdit#code_input:focus { border-color: #FF7700; }
QProgressBar {
    background: #1E1E38; border: 1px solid #3A3A60; border-radius: 6px;
    text-align: center; color: #E8EEFF; height: 20px;
}
QProgressBar::chunk { background: #FF7700; border-radius: 5px; }
QPushButton#btn_start {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FF7700, stop:1 #FF4400);
    color: white; border: none; border-radius: 8px; padding: 10px 20px;
    font-size: 13px; font-weight: 700;
}
QPushButton#btn_start:hover { background: #FF9900; }
QPushButton#btn_start:disabled { background: #553322; color: #886655; }
QPushButton#btn_close {
    background: transparent; color: #6060A0; border: 1px solid #3A3A60;
    border-radius: 8px; padding: 9px 18px; font-size: 13px;
}
QFrame#divider { background: #2A2A4A; }
"""


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


class SendDocumentDialog(QDialog):
    """Gửi 1 file PDF cụ thể (đường dẫn cố định lúc mở dialog) sang thiết bị
    companion đã ghép nối với key 3TR-E hiện tại. Người dùng lấy mã trên
    ScanDoc (đã bấm "Nhận tài liệu") rồi dán vào đây."""

    _sig_status = Signal(str, dict)
    _sig_progress = Signal(int, int)
    _sig_done = Signal(dict)
    _sig_error = Signal(str)

    def __init__(self, parent, file_path: str):
        super().__init__(parent)
        self._file_path = file_path
        self._sending = False
        self.setWindowTitle("Chuyển tài liệu")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_STYLE)
        self._setup_ui()

        self._sig_status.connect(self._on_status)
        self._sig_progress.connect(self._on_progress)
        self._sig_done.connect(self._on_done)
        self._sig_error.connect(self._on_error)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        title = QLabel("Chuyển tài liệu")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Trên điện thoại, mở ScanDoc và bấm \"Nhận tài liệu\" để lấy mã, "
            "sau đó dán mã đó vào đây — gửi trực tiếp, không qua máy chủ."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        file_box = QFrame()
        file_layout = QVBoxLayout(file_box)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(2)
        name_label = QLabel(os.path.basename(self._file_path))
        name_label.setObjectName("file_name")
        name_label.setWordWrap(True)
        file_layout.addWidget(name_label)
        try:
            size_text = _human_size(os.path.getsize(self._file_path))
        except OSError:
            size_text = "?"
        meta_label = QLabel(size_text)
        meta_label.setObjectName("file_meta")
        file_layout.addWidget(meta_label)
        layout.addWidget(file_box)

        self._code_input = QLineEdit()
        self._code_input.setObjectName("code_input")
        self._code_input.setPlaceholderText("Mã hiện trên ScanDoc, vd PJG8-PKQC...")
        layout.addWidget(self._code_input)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setObjectName("status_line")
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        layout.addWidget(self._status_label)

        self._btn_start = QPushButton("Gửi file")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.clicked.connect(self._on_start_clicked)
        layout.addWidget(self._btn_start)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._btn_close = QPushButton("Đóng")
        self._btn_close.setObjectName("btn_close")
        self._btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_close)
        layout.addLayout(btn_row)

    # ── Bắt đầu gửi ──────────────────────────────────────────────────────

    def _on_start_clicked(self) -> None:
        if self._sending:
            return
        raw_text = self._code_input.text()
        entered = _extract_session_id(raw_text)
        if not entered:
            self._restyle(self._status_label, "status_err")
            if _is_pairing_qr_payload(raw_text):
                self._status_label.setText(
                    "Đây là mã ghép nối thiết bị (Thiết bị ScanDoc), không phải mã nhận "
                    "tài liệu. Hãy lấy mã ở màn hình \"Nhận tài liệu\" trên ScanDoc."
                )
            else:
                self._status_label.setText("Mã không hợp lệ. Dán đúng mã/QR từ ScanDoc.")
            self._status_label.show()
            return

        self._sending = True
        self._code_input.setEnabled(False)
        self._btn_start.setEnabled(False)
        self._btn_start.setText("Đang gửi...")
        self._restyle(self._status_label, "status_line")
        self._status_label.setText("Đang tham gia phiên truyền...")
        self._status_label.show()

        file_path = self._file_path

        def on_progress(sent, total):
            self._sig_progress.emit(sent, total)

        def on_connected():
            self._sig_status.emit("connected", {})

        def worker():
            from packages.transfer import get_transfer_client
            from packages.transfer.webrtc_transport import guest_send_file_async

            client = get_transfer_client()
            joined = False
            transfer_session_id = entered

            def on_status(stage, data):
                nonlocal joined
                if stage == "joined":
                    joined = True
                self._sig_status.emit(stage, data)

            try:
                if _is_short_code(entered):
                    resolved = client.resolve_transfer_code(entered)
                    transfer_session_id = resolved["transfer_session_id"]

                asyncio.run(
                    guest_send_file_async(
                        transfer_session_id, file_path,
                        on_progress=on_progress, on_connected=on_connected, on_status=on_status,
                    )
                )

                client.complete_transfer_session(transfer_session_id, "completed")
                self._sig_done.emit({"transfer_session_id": transfer_session_id})
            except Exception as exc:  # noqa: BLE001 - báo lỗi lên UI qua signal, không để lộ traceback thô
                if joined:
                    try:
                        client.complete_transfer_session(transfer_session_id, "failed")
                    except Exception:
                        pass
                self._sig_error.emit(str(exc))

        threading.Thread(target=worker, daemon=True, name="transfer-send").start()

    # ── Callback (đã chuyển an toàn về UI thread qua Qt signal) ─────────

    def _on_status(self, stage: str, data: dict) -> None:
        if stage == "joined":
            self._status_label.setText("Đã tham gia phiên - đang kết nối trực tiếp tới thiết bị...")
        elif stage == "connected":
            self._progress_bar.setValue(0)
            self._progress_bar.show()
            self._status_label.setText("Đã kết nối - đang gửi...")

    def _on_progress(self, sent: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setValue(int(sent * 100 / total))
        self._status_label.setText(f"Đã gửi {_human_size(sent)} / {_human_size(total)}")

    def _restyle(self, widget, object_name: str) -> None:
        """Đổi objectName lúc runtime không tự khiến QSS re-match - phải
        unpolish/polish lại để style theo selector mới (vd #status_ok) áp
        dụng ngay, không cần đóng mở lại dialog."""
        widget.setObjectName(object_name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _on_done(self, result: dict) -> None:
        self._sending = False
        self._progress_bar.setValue(100)
        self._restyle(self._status_label, "status_ok")
        self._status_label.setText("✓ Đã gửi xong, thiết bị nhận đã xác nhận đủ dữ liệu.")
        self._btn_start.hide()
        self._code_input.setEnabled(False)

    def _on_error(self, message: str) -> None:
        self._sending = False
        self._code_input.setEnabled(True)
        self._btn_start.setEnabled(True)
        self._btn_start.setText("Thử lại")
        self._progress_bar.hide()
        self._restyle(self._status_label, "status_err")
        self._status_label.setText(message)
        self._status_label.show()
