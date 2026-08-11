from __future__ import annotations

"""Dialog "Nhận tài liệu" — nhận PDF từ thiết bị companion (ScanDoc) qua P2P
WebRTC, đối xứng với transfer_send_dialog.py (SendDocumentDialog). Bên gửi
(điện thoại) tạo transfer-session và hiển thị mã/QR; desktop không quét được
QR trên điện thoại nên người dùng dán/gõ mã đó vào đây, desktop join phiên
rồi chạy webrtc_transport.receive_file() ở vai trò answer.
"""

import asyncio
import hashlib
import json
import threading

from packages.qt_compat.QtCore import Qt
from packages.qt_compat import pyqtSignal as Signal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QLineEdit,
)

from app.transfer_send_dialog import _human_size, _STYLE as _SEND_STYLE


_STYLE = _SEND_STYLE + """
QLineEdit#code_input {
    color: #E8EEFF; font-size: 14px; font-family: monospace;
    background: #1E1E38; border: 1px solid #3A3A60; border-radius: 8px;
    padding: 10px 12px;
}
QLineEdit#code_input:focus { border-color: #FF7700; }
"""


def _extract_session_id(raw: str) -> str:
    """Chấp nhận UUID thô hoặc nguyên chuỗi JSON QR payload
    ({"v":1,"transfer_session_id":"..."}) - dán cả 2 dạng đều dùng được."""
    text = raw.strip()
    if not text:
        return ""
    if text.startswith("{"):
        try:
            data = json.loads(text)
            return str(data.get("transfer_session_id", "")).strip()
        except Exception:
            return ""
    return text


def _is_pairing_qr_payload(raw: str) -> bool:
    """True nếu user lỡ dán nhầm mã QR ghép nối thiết bị
    ({"v":1,"pairing_session_id":"..."} từ dialog "Thiết bị ScanDoc") thay
    vì mã nhận tài liệu - 2 QR trông giống hệt nhau với mắt thường, cần báo
    lỗi rõ ràng thay vì chỉ nói chung chung "mã không hợp lệ"."""
    text = raw.strip()
    if not text.startswith("{"):
        return False
    try:
        data = json.loads(text)
    except Exception:
        return False
    return "pairing_session_id" in data and "transfer_session_id" not in data


class ReceiveDocumentDialog(QDialog):
    """Nhận 1 file PDF từ thiết bị companion đã ghép nối với key 3TR-E hiện
    tại, qua mã/QR do phía gửi (điện thoại) cung cấp."""

    _sig_status = Signal(str, dict)
    _sig_progress = Signal(int, int)
    _sig_done = Signal(dict)
    _sig_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._receiving = False
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
            "Dán mã phiên hiển thị trên ScanDoc (điện thoại) để nhận trực tiếp — "
            "không qua máy chủ."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._code_input = QLineEdit()
        self._code_input.setObjectName("code_input")
        self._code_input.setPlaceholderText("Mã phiên hoặc mã QR dán từ ScanDoc...")
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

        self._btn_start = QPushButton("Nhận file")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.clicked.connect(self._on_start_clicked)
        layout.addWidget(self._btn_start)

        self._btn_open = QPushButton("Mở tài liệu")
        self._btn_open.setObjectName("btn_start")
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

        self._received_path = ""

    # ── Bắt đầu nhận ─────────────────────────────────────────────────────

    def _on_start_clicked(self) -> None:
        if self._receiving:
            return
        raw_text = self._code_input.text()
        transfer_session_id = _extract_session_id(raw_text)
        if not transfer_session_id:
            self._restyle(self._status_label, "status_err")
            if _is_pairing_qr_payload(raw_text):
                self._status_label.setText(
                    "Đây là mã ghép nối thiết bị (Thiết bị ScanDoc), không phải mã nhận "
                    "tài liệu. Hãy lấy mã ở màn hình gửi tài liệu trên ScanDoc."
                )
            else:
                self._status_label.setText("Mã không hợp lệ. Dán đúng mã/QR từ ScanDoc.")
            self._status_label.show()
            return

        self._receiving = True
        self._code_input.setEnabled(False)
        self._btn_start.setEnabled(False)
        self._btn_start.setText("Đang nhận...")
        self._restyle(self._status_label, "status_line")
        self._status_label.setText("Đang tham gia phiên truyền...")
        self._status_label.show()

        def on_progress(received, total):
            self._sig_progress.emit(received, total)

        def worker():
            from packages.transfer import get_transfer_client
            from packages.transfer.signaling_client import SignalingClient
            from packages.transfer.webrtc_transport import receive_file
            from packages.transfer.inbox import StagedReceive

            client = get_transfer_client()
            joined = False
            try:
                token, device_id = client.get_credentials()
                client.join_transfer_session(transfer_session_id)
                joined = True
                self._sig_status.emit("joined", {})

                signaling = SignalingClient(client.base_url, transfer_session_id, token, device_id)
                file_name, data = asyncio.run(receive_file(signaling, on_progress=on_progress))

                staged = StagedReceive(file_name)
                staged.write(data)
                final_path = staged.commit()

                client.complete_transfer_session(
                    transfer_session_id, "completed", hashlib.sha256(data).hexdigest()
                )
                self._sig_done.emit({"path": str(final_path)})
            except Exception as exc:  # noqa: BLE001 - báo lỗi lên UI qua signal, không để lộ traceback thô
                if joined:
                    try:
                        client.complete_transfer_session(transfer_session_id, "failed")
                    except Exception:
                        pass
                self._sig_error.emit(str(exc))

        threading.Thread(target=worker, daemon=True, name="transfer-receive").start()

    # ── Callback (đã chuyển an toàn về UI thread qua Qt signal) ─────────

    def _on_status(self, stage: str, data: dict) -> None:
        if stage == "joined":
            self._status_label.setText("Đã tham gia phiên - đang chờ thiết bị gửi kết nối...")

    def _on_progress(self, received: int, total: int) -> None:
        if self._progress_bar.isHidden():
            self._progress_bar.setValue(0)
            self._progress_bar.show()
        if total > 0:
            self._progress_bar.setValue(int(received * 100 / total))
        self._status_label.setText(f"Đã nhận {_human_size(received)} / {_human_size(total)}")

    def _restyle(self, widget, object_name: str) -> None:
        widget.setObjectName(object_name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _on_done(self, result: dict) -> None:
        self._receiving = False
        self._progress_bar.setValue(100)
        self._restyle(self._status_label, "status_ok")
        self._received_path = result.get("path", "")
        import os
        file_name = os.path.basename(self._received_path)
        self._status_label.setText(f"✓ Đã nhận xong: {file_name}")
        self._btn_start.hide()
        if self._received_path.lower().endswith(".pdf"):
            self._btn_open.show()

        # Chỉ đổi label trong dialog là không đủ - nếu cửa sổ "Nhận tài liệu"
        # không đang là cửa sổ active (user đang làm việc khác), họ sẽ không
        # biết file đã nhận xong. Bật thêm popup để không bỏ lỡ (port từ
        # phase1-mac commit e33ac32, xem docs/UPDATE_2026-08-10_transfer_fixes.md).
        from packages.qt_compat.QtWidgets import QMessageBox

        QMessageBox.information(self, "Nhận tài liệu", f"Đã nhận xong: {file_name}")

    def _on_open_clicked(self) -> None:
        parent = self.parent()
        if parent is not None and self._received_path:
            parent.open_document(self._received_path)
        self.accept()

    def _on_error(self, message: str) -> None:
        self._receiving = False
        self._code_input.setEnabled(True)
        self._btn_start.setEnabled(True)
        self._btn_start.setText("Thử lại")
        self._progress_bar.hide()
        self._restyle(self._status_label, "status_err")
        self._status_label.setText(message)
