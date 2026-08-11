from __future__ import annotations

"""Dialog "Nhận tài liệu" — nhận PDF từ thiết bị companion (ScanDoc) qua P2P
WebRTC, đối xứng với transfer_send_dialog.py (SendDocumentDialog).

Từ 11/08/2026 (xem docs/PLAN_2026-08-11_reverse_qr_send_flow.md, nhánh
phase1-backend): mở dialog là TỰ ĐỘNG tạo phiên + hiện QR ngay (đúng
nguyên tắc "bên nhận luôn tạo phiên", đối xứng với ghép nối thiết bị) -
desktop vẫn đóng vai trò webrtc_transport.receive_file() (answerer, nhận
bytes) như trước, chỉ đổi CÁCH lấy transfer_session_id (tự tạo thay vì
đợi người dùng gõ tay mã ScanDoc hiện ra). Đường dán mã thủ công cũ vẫn
giữ lại làm phương án dự phòng (quyết định UX đã chốt 11/08/2026) - bấm
"Nhập mã thủ công" để chuyển qua.
"""

import hashlib
import threading

from packages.qt_compat.QtCore import Qt, QTimer
from packages.qt_compat import pyqtSignal as Signal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QLineEdit,
)

from app.transfer_pairing_dialog import (
    _render_qr_pixmap, _extract_session_id, _is_short_code, _is_pairing_qr_payload,
)
from app.transfer_send_dialog import _human_size, _STYLE as _SEND_STYLE


_STYLE = _SEND_STYLE + """
QLineEdit#code_input {
    color: #E8EEFF; font-size: 14px; font-family: monospace;
    background: #1E1E38; border: 1px solid #3A3A60; border-radius: 8px;
    padding: 10px 12px;
}
QLineEdit#code_input:focus { border-color: #FF7700; }
QPushButton#btn_link {
    background: transparent; color: #7A88C0; border: none;
    font-size: 12px; text-decoration: underline; padding: 2px;
}
QPushButton#btn_link:hover { color: #FF9900; }
"""


def _seconds_until(expires_at_iso: str) -> int:
    try:
        from datetime import datetime, timezone
        exp = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
        return max(0, int((exp - datetime.now(timezone.utc)).total_seconds()))
    except Exception:
        return 0


class ReceiveDocumentDialog(QDialog):
    """Nhận 1 file PDF từ thiết bị companion đã ghép nối với key 3TR-E hiện
    tại. Mặc định tự tạo phiên + hiện QR ngay khi mở; có thể chuyển sang
    nhập mã thủ công (mã do ScanDoc hiển thị) làm phương án dự phòng."""

    _sig_status = Signal(str, dict)
    _sig_progress = Signal(int, int)
    _sig_done = Signal(dict)
    _sig_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._receiving = False
        self._manual_mode = False
        self._received_path = ""
        self._seconds_left = 0
        self.setWindowTitle("Nhận tài liệu")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setStyleSheet(_STYLE)
        self._setup_ui()

        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick_countdown)

        self._sig_status.connect(self._on_status)
        self._sig_progress.connect(self._on_progress)
        self._sig_done.connect(self._on_done)
        self._sig_error.connect(self._on_error)

        self._start_qr_flow()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        title = QLabel("Nhận tài liệu")
        title.setObjectName("title")
        layout.addWidget(title)

        self._subtitle = QLabel(
            "Mở ScanDoc trên điện thoại đã ghép nối, quét mã QR bên dưới để "
            "gửi tài liệu trực tiếp — không qua máy chủ."
        )
        self._subtitle.setObjectName("subtitle")
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

        # ── Chế độ QR (mặc định) ────────────────────────────────────────
        self._qr_label = QLabel("")
        self._qr_label.setObjectName("qr_display")
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.hide()
        layout.addWidget(self._qr_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._code_label = QLabel("")
        self._code_label.setObjectName("code_display")
        self._code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._code_label.hide()
        layout.addWidget(self._code_label)

        self._countdown_label = QLabel("")
        self._countdown_label.setObjectName("subtitle")
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.hide()
        layout.addWidget(self._countdown_label)

        self._btn_new_code = QPushButton("Tạo mã mới")
        self._btn_new_code.setObjectName("btn_start")
        self._btn_new_code.clicked.connect(self._start_qr_flow)
        self._btn_new_code.hide()
        layout.addWidget(self._btn_new_code)

        self._btn_toggle_manual = QPushButton("Nhập mã thủ công thay vì quét QR")
        self._btn_toggle_manual.setObjectName("btn_link")
        self._btn_toggle_manual.clicked.connect(self._toggle_manual_mode)
        layout.addWidget(self._btn_toggle_manual, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ── Chế độ nhập mã thủ công (dự phòng) ──────────────────────────
        self._code_input = QLineEdit()
        self._code_input.setObjectName("code_input")
        self._code_input.setPlaceholderText("Mã phiên hoặc mã QR dán từ ScanDoc...")
        self._code_input.hide()
        layout.addWidget(self._code_input)

        self._btn_start = QPushButton("Nhận file")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.clicked.connect(self._on_manual_start_clicked)
        self._btn_start.hide()
        layout.addWidget(self._btn_start)

        # ── Chung cho cả 2 chế độ ────────────────────────────────────────
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

    # ── Chuyển đổi QR / nhập tay ─────────────────────────────────────────

    def _toggle_manual_mode(self) -> None:
        if self._receiving:
            return
        self._manual_mode = not self._manual_mode
        if self._manual_mode:
            self._countdown_timer.stop()
            self._qr_label.hide()
            self._code_label.hide()
            self._countdown_label.hide()
            self._btn_new_code.hide()
            self._subtitle.setText(
                "Dán mã phiên hiển thị trên ScanDoc (điện thoại) để nhận trực tiếp — "
                "không qua máy chủ."
            )
            self._btn_toggle_manual.setText("Dùng mã QR thay vì nhập tay")
            self._code_input.show()
            self._btn_start.show()
            self._status_label.hide()
        else:
            self._code_input.hide()
            self._btn_start.hide()
            self._subtitle.setText(
                "Mở ScanDoc trên điện thoại đã ghép nối, quét mã QR bên dưới để "
                "gửi tài liệu trực tiếp — không qua máy chủ."
            )
            self._btn_toggle_manual.setText("Nhập mã thủ công thay vì quét QR")
            self._start_qr_flow()

    # ── Chế độ QR: tự tạo phiên ──────────────────────────────────────────

    def _start_qr_flow(self) -> None:
        if self._receiving or self._manual_mode:
            return
        self._receiving = True
        self._btn_new_code.hide()
        self._btn_toggle_manual.setEnabled(False)
        self._restyle(self._status_label, "status_line")
        self._status_label.setText("Đang tạo mã...")
        self._status_label.show()

        def on_progress(received, total):
            self._sig_progress.emit(received, total)

        def on_status(stage, data):
            self._sig_status.emit(stage, data)

        def worker():
            from packages.transfer import get_transfer_client
            from packages.transfer.webrtc_transport import host_receive_file_async
            from packages.transfer.inbox import StagedReceive

            client = get_transfer_client()
            transfer_session_id = ""

            def on_status_capture(stage, data):
                nonlocal transfer_session_id
                if stage == "created":
                    transfer_session_id = data.get("transfer_session_id", "")
                on_status(stage, data)

            try:
                import asyncio
                file_name, data = asyncio.run(
                    host_receive_file_async(on_progress=on_progress, on_status=on_status_capture)
                )

                staged = StagedReceive(file_name)
                staged.write(data)
                final_path = staged.commit()

                client.complete_transfer_session(
                    transfer_session_id, "completed", hashlib.sha256(data).hexdigest()
                )
                self._sig_done.emit({"path": str(final_path)})
            except Exception as exc:  # noqa: BLE001 - báo lỗi lên UI qua signal, không để lộ traceback thô
                if transfer_session_id:
                    try:
                        client.complete_transfer_session(transfer_session_id, "failed")
                    except Exception:
                        pass
                self._sig_error.emit(str(exc))

        threading.Thread(target=worker, daemon=True, name="transfer-receive-host").start()

    # ── Chế độ nhập tay ──────────────────────────────────────────────────

    def _on_manual_start_clicked(self) -> None:
        if self._receiving:
            return
        raw_text = self._code_input.text()
        entered = _extract_session_id(raw_text)
        if not entered:
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
        self._btn_toggle_manual.setEnabled(False)
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
            import asyncio

            client = get_transfer_client()
            joined = False
            transfer_session_id = entered
            try:
                if _is_short_code(entered):
                    resolved = client.resolve_transfer_code(entered)
                    transfer_session_id = resolved["transfer_session_id"]
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

        threading.Thread(target=worker, daemon=True, name="transfer-receive-manual").start()

    # ── Callback (đã chuyển an toàn về UI thread qua Qt signal) ─────────

    def _on_status(self, stage: str, data: dict) -> None:
        if stage == "created":
            self._btn_toggle_manual.setEnabled(True)
            code = data.get("code") or data.get("transfer_session_id", "")[:8].upper()
            self._code_label.setText(code)
            self._code_label.show()
            qr_payload = data.get("qr_payload", "")
            pixmap = _render_qr_pixmap(qr_payload) if qr_payload else None
            if pixmap is not None:
                self._qr_label.setPixmap(pixmap)
                self._qr_label.show()
            self._status_label.setText("Đang chờ ScanDoc quét mã...")

            self._seconds_left = _seconds_until(data.get("expires_at", "")) or 300
            self._countdown_label.show()
            self._tick_countdown()
            self._countdown_timer.start(1000)
        elif stage == "joined":
            self._status_label.setText("Đã tham gia phiên - đang chờ thiết bị gửi kết nối...")
        elif stage == "connected":
            self._countdown_timer.stop()
            self._qr_label.hide()
            self._code_label.hide()
            self._countdown_label.hide()
            self._progress_bar.setValue(0)
            self._progress_bar.show()
            self._status_label.setText("Đã kết nối - đang nhận...")

    def _tick_countdown(self) -> None:
        if self._seconds_left <= 0:
            self._countdown_timer.stop()
            self._countdown_label.setText("Mã đã hết hạn.")
            self._qr_label.hide()
            self._code_label.hide()
            self._receiving = False
            self._btn_new_code.show()
            self._btn_toggle_manual.setEnabled(True)
            self._status_label.setText("Mã đã hết hạn - bấm \"Tạo mã mới\" để thử lại.")
            return
        mins, secs = divmod(self._seconds_left, 60)
        self._countdown_label.setText(f"Mã hết hạn sau {mins:02d}:{secs:02d}")
        self._seconds_left -= 1

    def _on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setValue(int(received * 100 / total))
        self._status_label.setText(f"Đã nhận {_human_size(received)} / {_human_size(total)}")

    def _restyle(self, widget, object_name: str) -> None:
        widget.setObjectName(object_name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _on_done(self, result: dict) -> None:
        self._receiving = False
        self._countdown_timer.stop()
        self._progress_bar.setValue(100)
        self._restyle(self._status_label, "status_ok")
        self._received_path = result.get("path", "")
        import os
        file_name = os.path.basename(self._received_path)
        self._status_label.setText(f"✓ Đã nhận xong: {file_name}")
        self._btn_start.hide()
        self._btn_new_code.hide()
        self._btn_toggle_manual.hide()
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
        self._countdown_timer.stop()
        self._code_input.setEnabled(True)
        self._btn_start.setEnabled(True)
        self._btn_start.setText("Thử lại")
        self._btn_toggle_manual.setEnabled(True)
        self._qr_label.hide()
        self._code_label.hide()
        self._countdown_label.hide()
        self._progress_bar.hide()
        if not self._manual_mode:
            self._btn_new_code.show()
        self._restyle(self._status_label, "status_err")
        self._status_label.setText(message)
        self._status_label.show()
