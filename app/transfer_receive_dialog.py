from __future__ import annotations

"""Dialog "Nhận tài liệu" — nhận PDF từ thiết bị companion (ScanDoc) qua P2P
WebRTC (Phase 2, packages/transfer/protocol.py). Cùng phong cách UI với
transfer_send_dialog.py, nhưng đảo chiều: người dùng dán mã/QR JSON do
ScanDoc hiển thị (desktop không quét camera - quyết định UX đã chốt), rồi
tham gia phiên và nhận file.

Luồng: dán mã -> parse -> join_transfer_session -> đợi offer từ ScanDoc
-> trả answer -> mở DataChannel -> nhận file với progress bar -> lưu vào
"Inbox ScanDoc" trong thư mục Documents -> báo hoàn tất + cho mở luôn.
"""

import json
import os

from packages.qt_compat.QtCore import QStandardPaths
from packages.qt_compat import pyqtSignal as Signal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QTextEdit,
)


_STYLE = """
QDialog { background: #16162A; }
QLabel#title { color: #E8EEFF; font-size: 18px; font-weight: 700; }
QLabel#subtitle { color: #8080B0; font-size: 12px; }
QLabel#file_name { color: #E8EEFF; font-size: 13px; font-weight: 600; }
QTextEdit#code_input {
    color: #E8EEFF; font-size: 13px; font-family: monospace;
    background: #1E1E38; border: 1px solid #3A3A60; border-radius: 8px;
    padding: 10px;
}
QTextEdit#code_input:focus { border: 1px solid #FF7700; }
QLabel#status_line { color: #8080B0; font-size: 12px; }
QLabel#status_err { color: #E05050; font-size: 12px; }
QLabel#status_ok { color: #34C759; font-size: 13px; font-weight: 700; }
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
QPushButton#btn_open {
    background: transparent; color: #50B8F0; border: 1px solid #50B8F0;
    border-radius: 8px; padding: 9px 18px; font-size: 13px; font-weight: 700;
}
QPushButton#btn_open:hover { background: rgba(80,184,240,0.12); }
QPushButton#btn_close {
    background: transparent; color: #6060A0; border: 1px solid #3A3A60;
    border-radius: 8px; padding: 9px 18px; font-size: 13px;
}
QFrame#divider { background: #2A2A4A; }
"""

_INBOX_SUBDIR = "Inbox ScanDoc"


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def _default_inbox_dir() -> str:
    docs_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    if not docs_dir:
        docs_dir = os.path.expanduser("~")
    return os.path.join(docs_dir, _INBOX_SUBDIR)


def _parse_transfer_session_id(raw: str) -> str:
    """Người dùng có thể dán nguyên QR JSON ({"v":1,"transfer_session_id":
    "..."}) hoặc dán thẳng mã/ID do ScanDoc hiển thị. Ưu tiên parse JSON,
    nếu không phải JSON hợp lệ thì coi cả chuỗi (đã trim) là session id."""
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("{"):
        try:
            data = json.loads(text)
            sid = str(data.get("transfer_session_id") or "").strip()
            if sid:
                return sid
        except (json.JSONDecodeError, AttributeError):
            pass
    return text


class ReceiveDocumentDialog(QDialog):
    """Nhận 1 file PDF từ thiết bị companion đã ghép nối, qua mã/QR JSON
    người dùng dán tay (không quét camera trên desktop)."""

    _sig_status = Signal(str, dict)
    _sig_progress = Signal(int, int)
    _sig_done = Signal(dict)
    _sig_error = Signal(str)

    def __init__(self, parent, on_open_file=None):
        super().__init__(parent)
        self._on_open_file = on_open_file
        self._receiving = False
        self._received_path = ""
        self.setWindowTitle("Nhận tài liệu")
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

        title = QLabel("Nhận tài liệu")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Mở ScanDoc trên điện thoại đã ghép nối, chọn tài liệu cần gửi, "
            "rồi dán mã hoặc dán nguyên nội dung mã QR vào ô bên dưới."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._code_input = QTextEdit()
        self._code_input.setObjectName("code_input")
        self._code_input.setPlaceholderText('Dán mã hoặc {"v":1,"transfer_session_id":"..."}')
        self._code_input.setFixedHeight(70)
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

        self._btn_start = QPushButton("Bắt đầu nhận")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.clicked.connect(self._on_start_clicked)
        layout.addWidget(self._btn_start)

        self._btn_open = QPushButton("Mở tài liệu vừa nhận")
        self._btn_open.setObjectName("btn_open")
        self._btn_open.clicked.connect(self._on_open_clicked)
        self._btn_open.hide()
        layout.addWidget(self._btn_open)

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

    # ── Bắt đầu nhận ─────────────────────────────────────────────────────

    def _on_start_clicked(self) -> None:
        if self._receiving:
            return

        transfer_session_id = _parse_transfer_session_id(self._code_input.toPlainText())
        if not transfer_session_id:
            self._restyle(self._status_label, "status_err")
            self._status_label.setText("Chưa nhập mã. Dán mã hoặc mã QR do ScanDoc hiển thị.")
            self._status_label.show()
            return

        self._receiving = True
        self._code_input.setEnabled(False)
        self._btn_start.setEnabled(False)
        self._btn_start.setText("Đang nhận...")
        self._restyle(self._status_label, "status_line")
        self._status_label.setText("Đang tham gia phiên truyền...")
        self._status_label.show()

        from packages.transfer import protocol

        save_dir = _default_inbox_dir()

        def on_status(stage, data):
            self._sig_status.emit(stage, data)

        def on_progress(received, total):
            self._sig_progress.emit(received, total)

        def coro_factory():
            return protocol.receive_file_async(
                transfer_session_id, save_dir, on_progress=on_progress, on_status=on_status,
            )

        def on_done(result):
            self._sig_done.emit(result)

        def on_error(exc):
            self._sig_error.emit(str(exc))

        protocol.run_async_in_thread(coro_factory, on_done, on_error)

    # ── Callback (đã chuyển an toàn về UI thread qua Qt signal) ─────────

    def _on_status(self, stage: str, data: dict) -> None:
        if stage == "connected":
            self._progress_bar.setValue(0)
            self._progress_bar.show()
            self._status_label.setText("Đã kết nối - đang nhận...")

    def _on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setValue(int(received * 100 / total))
        self._status_label.setText(f"Đã nhận {_human_size(received)} / {_human_size(total)}")

    def _restyle(self, widget, object_name: str) -> None:
        """Đổi objectName lúc runtime không tự khiến QSS re-match - phải
        unpolish/polish lại để style theo selector mới (vd #status_ok) áp
        dụng ngay, không cần đóng mở lại dialog."""
        widget.setObjectName(object_name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _on_done(self, result: dict) -> None:
        self._receiving = False
        self._received_path = result.get("file_path", "")
        self._progress_bar.setValue(100)
        self._restyle(self._status_label, "status_ok")
        file_name = os.path.basename(self._received_path) if self._received_path else ""
        self._status_label.setText(f"✓ Đã nhận xong: {file_name}")
        self._btn_start.hide()
        if self._received_path:
            self._btn_open.show()

    def _on_error(self, message: str) -> None:
        self._receiving = False
        self._code_input.setEnabled(True)
        self._btn_start.setEnabled(True)
        self._btn_start.setText("Thử lại")
        self._progress_bar.hide()
        self._restyle(self._status_label, "status_err")
        self._status_label.setText(message)

    def _on_open_clicked(self) -> None:
        if self._received_path and self._on_open_file:
            self._on_open_file(self._received_path)
        self.accept()
