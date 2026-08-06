from __future__ import annotations

"""Dialog "Chuyển tài liệu" — gửi PDF đang mở sang thiết bị companion qua
P2P WebRTC (Phase 2, packages/transfer/protocol.py). Cùng phong cách UI với
transfer_pairing_dialog.py (Phase 1) để nhất quán.

Luồng: tạo transfer-session -> hiện mã/QR (tái dùng cơ chế QR của Phase 1)
-> đợi thiết bị companion quét mã + tham gia -> tự động thương lượng SDP/ICE
-> mở DataChannel -> gửi file với progress bar -> báo hoàn tất.
"""

import os

from packages.qt_compat.QtCore import Qt
from packages.qt_compat import pyqtSignal as Signal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar,
)

from app.transfer_pairing_dialog import _render_qr_pixmap


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
    companion đã/đang ghép nối với key 3TR-E hiện tại."""

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

        subtitle = QLabel("Gửi trực tiếp cho iPhone/iPad đã ghép nối — không qua máy chủ, không cần internet chậm.")
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

        self._qr_label = QLabel("")
        self._qr_label.setObjectName("qr_display")
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.hide()
        layout.addWidget(self._qr_label)

        self._code_label = QLabel("")
        self._code_label.setObjectName("code_display")
        self._code_label.setAlignment(Qt.AlignCenter)
        self._code_label.hide()
        layout.addWidget(self._code_label)

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

        self._btn_start = QPushButton("Bắt đầu gửi")
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
        self._sending = True
        self._btn_start.setEnabled(False)
        self._btn_start.setText("Đang gửi...")
        self._restyle(self._status_label, "status_line")
        self._status_label.setText("Đang tạo phiên truyền...")
        self._status_label.show()

        from packages.transfer import protocol

        file_path = self._file_path

        def on_status(stage, data):
            self._sig_status.emit(stage, data)

        def on_progress(sent, total):
            self._sig_progress.emit(sent, total)

        def coro_factory():
            return protocol.send_file_async(file_path, on_progress=on_progress, on_status=on_status)

        def on_done(result):
            self._sig_done.emit(result)

        def on_error(exc):
            self._sig_error.emit(str(exc))

        protocol.run_async_in_thread(coro_factory, on_done, on_error)

    # ── Callback (đã chuyển an toàn về UI thread qua Qt signal) ─────────

    def _on_status(self, stage: str, data: dict) -> None:
        if stage == "session_created":
            code = data.get("transfer_session_id", "")[:8].upper()
            self._code_label.setText(code)
            self._code_label.show()
            qr_payload = data.get("qr_payload", "")
            pixmap = _render_qr_pixmap(qr_payload) if qr_payload else None
            if pixmap is not None:
                self._qr_label.setPixmap(pixmap)
                self._qr_label.show()
            self._status_label.setText("Mở ScanDoc trên điện thoại đã ghép nối và quét mã để nhận file.")
        elif stage == "connected":
            self._qr_label.hide()
            self._code_label.hide()
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

    def _on_error(self, message: str) -> None:
        self._sending = False
        self._btn_start.setEnabled(True)
        self._btn_start.setText("Thử lại")
        self._qr_label.hide()
        self._code_label.hide()
        self._progress_bar.hide()
        self._restyle(self._status_label, "status_err")
        self._status_label.setText(message)
