"""Dialog chat với PDF — AI Assistant."""
from __future__ import annotations

from packages.qt_compat.QtCore import Qt
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QLineEdit, QSizePolicy, QApplication,
    QCheckBox,
)
from app.ai_task_runner import dialog_task_running, start_dialog_task
from styles.theme import is_dark


def _build_theme(dark: bool):
    if dark:
        return {
            "dialog_style": """
QDialog { background: #16162A; }
QLabel#title  { color: #E8EEFF; font-size: 15px; font-weight: 700; }
QLabel#status { color: #8080B0; font-size: 11px; }
QTextEdit#chat_area {
    background: #12122A;
    color: #D0D8F8;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    font-size: 13px;
    padding: 12px;
    line-height: 1.6;
}
QLineEdit {
    background: #1E1E38;
    color: #E0E8FF;
    border: 1px solid #3A3A60;
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus { border-color: #6060C0; }
QPushButton {
    background: #1E1E38;
    color: #B0B8E0;
    border: 1px solid #3A3A60;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover  { background: #2A2A50; border-color: #6060C0; }
QPushButton:disabled { color: #444466; border-color: #2A2A44; }
QPushButton#btn_send {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #8b5cf6);
    color: white; border: none;
    min-width: 70px;
}
QPushButton#btn_send:hover { background: #7374f8; }
QPushButton#btn_clear {
    background: #2A1A1A;
    color: #f07878;
    border-color: #603030;
}
QPushButton#btn_clear:hover { background: #3A1A1A; border-color: #804040; }
QFrame#divider { background: #2A2A4A; }
""",
            "user": '<div style="margin:8px 0;padding:10px 14px;background:#1E1E48;border-radius:8px;border-left:3px solid #6366f1;"><span style="color:#9090D0;font-size:11px;font-weight:600;">Bạn</span><br><span style="color:#E0E8FF;">{text}</span></div>',
            "ai": '<div style="margin:8px 0;padding:10px 14px;background:#12122A;border-radius:8px;border-left:3px solid #4fc080;"><span style="color:#4fc080;font-size:11px;font-weight:600;">AI Assistant</span><br><span style="color:#C8D8F8;">{text}</span></div>',
            "error": '<div style="margin:8px 0;padding:10px 14px;background:#2A1A1A;border-radius:8px;border-left:3px solid #E05050;"><span style="color:#E05050;font-size:11px;font-weight:600;">Lỗi</span><br><span style="color:#F08080;">{text}</span></div>',
            "thinking": '<div style="margin:8px 0;padding:10px 14px;background:#12122A;border-radius:8px;border-left:3px solid #4fc080;"><span style="color:#4fc080;font-size:11px;font-weight:600;">AI Assistant</span><br><span style="color:#6070A0;font-style:italic;">AI đang trả lời…</span></div>',
            "system": "#6070A0",
        }
    return {
        "dialog_style": """
QDialog { background: #F8FAFF; }
QLabel#title  { color: #0F172A; font-size: 15px; font-weight: 700; }
QLabel#status { color: #475569; font-size: 11px; }
QTextEdit#chat_area {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    font-size: 13px;
    padding: 12px;
    line-height: 1.6;
}
QLineEdit {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus { border-color: #2563EB; }
QPushButton {
    background: #E2E8F0;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover  { background: #CBD5E1; border-color: #94A3B8; }
QPushButton:disabled { color: #94A3B8; border-color: #CBD5E1; }
QPushButton#btn_send {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #7C3AED);
    color: white; border: none;
    min-width: 70px;
}
QPushButton#btn_send:hover { background: #3B82F6; }
QPushButton#btn_clear {
    background: #FEF2F2;
    color: #B91C1C;
    border-color: #FCA5A5;
}
QPushButton#btn_clear:hover { background: #FEE2E2; border-color: #F87171; }
QFrame#divider { background: #E2E8F0; }
""",
        "user": '<div style="margin:8px 0;padding:10px 14px;background:#EEF2FF;border-radius:8px;border-left:3px solid #2563EB;"><span style="color:#1D4ED8;font-size:11px;font-weight:600;">Bạn</span><br><span style="color:#0F172A;">{text}</span></div>',
        "ai": '<div style="margin:8px 0;padding:10px 14px;background:#F8FAFC;border-radius:8px;border-left:3px solid #059669;"><span style="color:#059669;font-size:11px;font-weight:600;">AI Assistant</span><br><span style="color:#0F172A;">{text}</span></div>',
        "error": '<div style="margin:8px 0;padding:10px 14px;background:#FEF2F2;border-radius:8px;border-left:3px solid #DC2626;"><span style="color:#DC2626;font-size:11px;font-weight:600;">Lỗi</span><br><span style="color:#B91C1C;">{text}</span></div>',
        "thinking": '<div style="margin:8px 0;padding:10px 14px;background:#F8FAFC;border-radius:8px;border-left:3px solid #059669;"><span style="color:#059669;font-size:11px;font-weight:600;">AI Assistant</span><br><span style="color:#64748B;font-style:italic;">AI đang trả lời…</span></div>',
        "system": "#64748B",
    }

class AIChatDialog(QDialog):
    """Dialog chat với PDF — non-modal, giữ nguyên khi đọc."""

    def __init__(self, parent, pdf_path: str):
        super().__init__(parent)
        self.setWindowTitle("Chat với PDF — AI Assistant")
        self.setModal(False)
        self.setMinimumWidth(600)
        self.resize(680, 600)
        self._theme = _build_theme(is_dark())
        self.setStyleSheet(self._theme["dialog_style"])

        self._pdf_path = pdf_path
        self._session  = None
        self._busy     = False
        self._request_seq = 0
        self._active_request_id = 0
        self._task_thread = None
        self._task_worker = None

        self._build_ui()
        self._append_system_msg(
            f"Đã tải tài liệu: <i>{pdf_path}</i><br>"
            "Hãy đặt câu hỏi về nội dung tài liệu."
        )

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Chat với PDF — AI Assistant")
        title.setObjectName("title")
        hdr.addWidget(title)
        hdr.addStretch()

        self._chk_stays_on_top = QCheckBox("Luôn nổi")
        self._chk_stays_on_top.setToolTip("Giữ cửa sổ chat nổi trên cửa sổ đọc PDF")
        self._chk_stays_on_top.toggled.connect(self._set_stays_on_top)
        hdr.addWidget(self._chk_stays_on_top)

        self._btn_clear = QPushButton("Xóa lịch sử")
        self._btn_clear.setObjectName("btn_clear")
        self._btn_clear.clicked.connect(self._on_clear)
        hdr.addWidget(self._btn_clear)
        root.addLayout(hdr)

        self._lbl_status = QLabel("Sẵn sàng.")
        self._lbl_status.setObjectName("status")
        root.addWidget(self._lbl_status)

        # Chat area
        self._chat_area = QTextEdit()
        self._chat_area.setObjectName("chat_area")
        self._chat_area.setReadOnly(True)
        self._chat_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._chat_area)

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        root.addWidget(div)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Nhập câu hỏi về tài liệu…")
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input, 1)

        self._btn_send = QPushButton("Gửi")
        self._btn_send.setObjectName("btn_send")
        self._btn_send.clicked.connect(self._on_send)
        input_row.addWidget(self._btn_send)
        root.addLayout(input_row)

    def _set_stays_on_top(self, enabled: bool):
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()

    def _append_html(self, html: str):
        self._chat_area.append(html)
        sb = self._chat_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _append_system_msg(self, text: str):
        html = (
            f'<div style="margin:6px 0;color:{self._theme["system"]};font-size:11px;font-style:italic;">'
            f'{text}</div>'
        )
        self._append_html(html)

    def _on_send(self):
        if self._busy:
            return
        question = self._input.text().strip()
        if not question:
            return

        from packages.ai.provider import is_ai_available
        if not is_ai_available():
            self._append_html(
                self._theme["error"].format(
                    text="Chưa cấu hình API key AI. Vào Settings để cài đặt."
                )
            )
            return

        if self._session is None:
            from packages.ai.chat_pdf import PDFChatSession
            self._session = PDFChatSession(self._pdf_path)

        self._input.clear()
        self._append_html(self._theme["user"].format(text=self._escape(question)))
        self._append_html(self._theme["thinking"])

        self._busy = True
        self._btn_send.setEnabled(False)
        self._lbl_status.setText("Đã gửi câu hỏi. AI đang đọc tài liệu và trả lời…")
        QApplication.processEvents()

        request_id = self._request_seq + 1
        self._request_seq = request_id
        self._active_request_id = request_id
        session = self._session

        started = start_dialog_task(
            self,
            lambda: self._run_request(request_id, session, question),
            on_success=self._on_finished,
            on_error=self._on_runner_error,
        )
        if not started:
            self._busy = False
            self._btn_send.setEnabled(True)
            self._lbl_status.setText("Đang có một yêu cầu AI khác đang chạy.")

    def _remove_thinking_bubble(self):
        cursor = self._chat_area.document().find(_MSG_THINKING)
        html = self._chat_area.toHtml()
        # Replace the thinking indicator with empty before appending real answer
        # We re-render chat from scratch to keep it clean
        # Simpler: just let new message append after; the thinking bubble stays brief

    def _run_request(self, request_id: int, session, question: str):
        try:
            return request_id, session, session.ask(question), ""
        except Exception as exc:
            return request_id, session, None, str(exc)

    def _on_finished(self, payload):
        request_id, session, result, error_message = payload
        if request_id != self._active_request_id or session is not self._session:
            return
        self._busy = False
        self._btn_send.setEnabled(True)

        # Remove thinking bubble by rebuilding from session history
        self._rebuild_chat()

        if error_message:
            self._append_html(self._theme["error"].format(text=self._escape(error_message)))
            self._lbl_status.setStyleSheet("color:#DC2626;font-size:11px")
            self._lbl_status.setText(f"Lỗi: {error_message}")
        elif result.success:
            self._lbl_status.setStyleSheet("color:#059669;font-size:11px")
            self._lbl_status.setText("Sẵn sàng.")
        else:
            self._append_html(
                self._theme["error"].format(text=self._escape(result.error or "Lỗi không xác định."))
            )
            self._lbl_status.setStyleSheet("color:#DC2626;font-size:11px")
            self._lbl_status.setText(f"Lỗi: {result.error}")

    def _on_runner_error(self, msg: str, _tb: str):
        self._busy = False
        self._btn_send.setEnabled(True)
        self._rebuild_chat()
        self._append_html(self._theme["error"].format(text=self._escape(msg)))
        self._lbl_status.setStyleSheet("color:#DC2626;font-size:11px")
        self._lbl_status.setText(f"Lỗi: {msg}")

    def _rebuild_chat(self):
        self._chat_area.clear()
        self._append_system_msg(
            f"Đã tải tài liệu: <i>{self._pdf_path}</i><br>"
            "Hãy đặt câu hỏi về nội dung tài liệu."
        )
        if self._session:
            for msg in self._session.history:
                if msg.role == "user":
                    self._append_html(
                        self._theme["user"].format(text=self._escape(msg.content))
                    )
                else:
                    self._append_html(
                        self._theme["ai"].format(text=self._escape(msg.content))
                    )

    def _on_clear(self):
        if self._session:
            self._session.reset()
        self._chat_area.clear()
        self._lbl_status.setText("Sẵn sàng.")
        self._lbl_status.setStyleSheet("")
        self._append_system_msg(
            f"Đã tải tài liệu: <i>{self._pdf_path}</i><br>"
            "Lịch sử đã được xóa. Hãy đặt câu hỏi mới."
        )

    def set_pdf(self, pdf_path: str):
        """Cập nhật khi PDF thay đổi — tạo session mới."""
        if pdf_path == self._pdf_path:
            return
        self._pdf_path = pdf_path
        self._session  = None
        self._active_request_id = self._request_seq + 1
        self._request_seq = self._active_request_id
        self._busy = False
        self._btn_send.setEnabled(True)
        self._chat_area.clear()
        self._lbl_status.setStyleSheet("")
        self._lbl_status.setText("Sẵn sàng.")
        self._append_system_msg(
            f"Tài liệu đã thay đổi: <i>{pdf_path}</i><br>"
            "Session mới được tạo. Hãy đặt câu hỏi."
        )

    def closeEvent(self, event):
        if dialog_task_running(self) or self._busy:
            self._lbl_status.setStyleSheet("color:#DC2626;font-size:11px")
            self._lbl_status.setText("Đang chờ AI trả lời. Hãy đóng lại sau khi tác vụ hoàn tất.")
            event.ignore()
            return
        parent = self.parent()
        if parent is not None and getattr(parent, "_ai_chat_dialog", None) is self:
            parent._ai_chat_dialog = None
        super().closeEvent(event)

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
        )
