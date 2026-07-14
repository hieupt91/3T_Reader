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
            "user": {
                "bg": "#1E1E48",
                "border": "#6366f1",
                "header_color": "#9090D0",
                "header": "Bạn",
                "text_color": "#E0E8FF",
            },
            "ai": {
                "bg": "#12122A",
                "border": "#4fc080",
                "header_color": "#4fc080",
                "header": "AI Assistant",
                "text_color": "#C8D8F8",
            },
            "error": {
                "bg": "#2A1A1A",
                "border": "#E05050",
                "header_color": "#E05050",
                "header": "Lỗi",
                "text_color": "#F08080",
            },
            "thinking": {
                "bg": "#12122A",
                "border": "#4fc080",
                "header_color": "#4fc080",
                "header": "AI Assistant",
                "text_color": "#6070A0",
                "text": "<i>AI đang trả lời…</i>",
            },
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
        "user": {
            "bg": "#EEF2FF",
            "border": "#2563EB",
            "header_color": "#1D4ED8",
            "header": "Bạn",
            "text_color": "#0F172A",
        },
        "ai": {
            "bg": "#F8FAFC",
            "border": "#059669",
            "header_color": "#059669",
            "header": "AI Assistant",
            "text_color": "#0F172A",
        },
        "error": {
            "bg": "#FEF2F2",
            "border": "#DC2626",
            "header_color": "#DC2626",
            "header": "Lỗi",
            "text_color": "#B91C1C",
        },
        "thinking": {
            "bg": "#F8FAFC",
            "border": "#059669",
            "header_color": "#059669",
            "header": "AI Assistant",
            "text_color": "#64748B",
            "text": "<i>AI đang trả lời…</i>",
        },
        "system": "#64748B",
    }

class AIChatDialog(QDialog):
    """Dialog chat với PDF - non-modal, giữ nguyên khi đọc."""

    def __init__(self, parent, pdf_path: str, history_identity_path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Chat với PDF — AI Assistant")
        self.setModal(False)
        self.setMinimumWidth(600)
        self.resize(680, 600)
        self._theme = _build_theme(is_dark())
        self.setStyleSheet(self._theme["dialog_style"])

        self._pdf_path = pdf_path
        self._history_identity_path = history_identity_path or pdf_path
        from packages.ai.chat_pdf import PDFChatSession
        self._session = PDFChatSession(self._pdf_path, max_history_messages=100, history_identity_path=self._history_identity_path)
        self._busy     = False
        self._request_seq = 0
        self._active_request_id = 0
        self._task_thread = None
        self._task_worker = None
        # Nguồn sự thật để render chat: danh sách (role, text) với role trong
        # {"user","ai","error","thinking"}. Luôn setHtml lại từ list này — KHÔNG
        # thao tác cursor theo vị trí ký tự (cách cũ xóa nhầm bong bóng user,
        # dính tin nhắn, mất câu đầu — TC51).
        self._messages: list[tuple[str, str]] = []

        self._build_ui()
        self._rebuild_chat()

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
        self._btn_clear.setAutoDefault(False)
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
        self._btn_send.setAutoDefault(True)
        self._btn_send.setDefault(True)
        self._btn_send.clicked.connect(self._on_send)
        input_row.addWidget(self._btn_send)
        root.addLayout(input_row)

    def _set_stays_on_top(self, enabled: bool):
        chat_html = self._chat_area.toHtml()
        input_text = self._input.text()
        status_text = self._lbl_status.text()
        status_style = self._lbl_status.styleSheet()
        send_enabled = self._btn_send.isEnabled()
        scroll_value = self._chat_area.verticalScrollBar().value()

        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            # ~ trên enum flag của PySide6 chỉ đảo trong độ rộng enum -> làm rớt
            # các bit cao như WindowCloseButtonHint (0x08000000), khiến nút đóng
            # bị disable sau khi tắt luôn nổi (TC37). Đảo trên int đầy đủ.
            flags &= ~int(Qt.WindowType.WindowStaysOnTopHint)
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        self._chat_area.setHtml(chat_html)
        self._input.setText(input_text)
        self._lbl_status.setText(status_text)
        self._lbl_status.setStyleSheet(status_style)
        self._btn_send.setEnabled(send_enabled)
        self._chat_area.verticalScrollBar().setValue(scroll_value)
        if was_visible:
            self.show()
            if enabled:
                self.raise_()
                self.activateWindow()

    def _intro_html(self, note: str = "") -> str:
        body = (
            f"Đã tải tài liệu: <i>{self._escape(self._pdf_path)}</i><br>"
            + (note or "Hãy đặt câu hỏi về nội dung tài liệu.")
        )
        return (
            f'<div style="margin:6px 0 10px 0;color:{self._theme["system"]};'
            f'font-size:11px;font-style:italic;">{body}</div>'
        )

    def _bubble_html(self, role: str, text: str) -> str:
        """Một bong bóng chat. User nằm bên phải, AI/lỗi/đang-trả-lời bên trái.
        Bỏ thẻ div, áp dụng background và styling trực tiếp lên thẻ td của bảng con.
        Điều này đảm bảo QTextEdit sẽ bo khít (shrink-to-fit) một cách hoàn hảo nhất."""
        style = self._theme[role]
        bg = style["bg"]
        border = style["border"]
        hc = style["header_color"]
        header = style["header"]
        tc = style["text_color"]
        
        if role == "thinking":
            content_text = style["text"]
        else:
            content_text = self._escape(text)

        # Style inline cho thẻ td
        td_style = f"background-color: {bg}; padding: 10px 14px; border-left: 3px solid {border}; border-radius: 8px;"
        
        inner_html = (
            f'<td style="{td_style}">'
            f'<span style="color:{hc}; font-size:11px; font-weight:600;">{header}</span><br>'
            f'<span style="color:{tc};">{content_text}</span>'
            f'</td>'
        )
            
        if role == "user":
            return (
                '<table width="100%" border="0" cellspacing="0" cellpadding="0">'
                '<tr><td align="right">'
                '<table border="0" cellspacing="0" cellpadding="0" style="margin:4px 0 4px 60px;">'
                f'<tr>{inner_html}</tr>'
                '</table></td></tr></table>'
            )
        return (
            '<table width="100%" border="0" cellspacing="0" cellpadding="0">'
            '<tr><td align="left">'
            '<table border="0" cellspacing="0" cellpadding="0" style="margin:4px 60px 4px 0;">'
            f'<tr>{inner_html}</tr>'
            '</table></td></tr></table>'
        )

    def _render(self, intro_note: str = "") -> None:
        """Dựng lại toàn bộ khung chat từ self._messages rồi cuộn xuống đáy.
        setHtml (không thao tác cursor) nên không bao giờ xóa nhầm tin nhắn."""
        parts = []
        if not self._messages or intro_note:
            parts.append(self._intro_html(intro_note))
        
        for role, text in self._messages:
            parts.append(self._bubble_html(role, text))
            
        self._chat_area.setHtml("".join(parts))
        sb = self._chat_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_send(self):
        if self._busy:
            return
        question = self._input.text().strip()
        if not question:
            return

        from packages.ai.provider import is_ai_available
        if not is_ai_available():
            self._messages.append(
                ("error", "Chưa cấu hình API key AI. Vào Settings để cài đặt.")
            )
            self._render()
            return

        if self._session is None:
            from packages.ai.chat_pdf import PDFChatSession
            self._session = PDFChatSession(self._pdf_path, max_history_messages=100, history_identity_path=self._history_identity_path)

        self._input.clear()
        # Hiện NGAY câu hỏi của người dùng + bong bóng "đang trả lời" trước khi
        # gọi AI, để tin nhắn đầu tiên không bị "biến mất" (TC51).
        self._messages.append(("user", question))
        self._messages.append(("thinking", ""))
        self._render()

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
            self._resolve_thinking("error", "Đang có một yêu cầu AI khác đang chạy.")
            self._lbl_status.setText("Đang có một yêu cầu AI khác đang chạy.")

    def _resolve_thinking(self, role: str, text: str) -> None:
        """Thay bong bóng 'đang trả lời' cuối cùng bằng câu trả lời/ lỗi thật."""
        if self._messages and self._messages[-1][0] == "thinking":
            self._messages.pop()
        self._messages.append((role, text))
        self._render()

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

        if error_message:
            self._resolve_thinking("error", error_message)
            self._lbl_status.setStyleSheet("color:#DC2626;font-size:11px")
            self._lbl_status.setText(f"Lỗi: {error_message}")
        elif result.success:
            self._resolve_thinking("ai", result.answer)
            self._lbl_status.setStyleSheet("color:#059669;font-size:11px")
            self._lbl_status.setText("Sẵn sàng.")
        else:
            self._resolve_thinking("error", result.error or "Lỗi không xác định.")
            self._lbl_status.setStyleSheet("color:#DC2626;font-size:11px")
            self._lbl_status.setText(f"Lỗi: {result.error}")

    def _on_runner_error(self, msg: str, _tb: str):
        self._busy = False
        self._btn_send.setEnabled(True)
        self._resolve_thinking("error", msg)
        self._lbl_status.setStyleSheet("color:#DC2626;font-size:11px")
        self._lbl_status.setText(f"Lỗi: {msg}")

    def _rebuild_chat(self, intro_note: str = ""):
        self._messages = []
        if self._session:
            for msg in self._session.history:
                self._messages.append(
                    ("user" if msg.role == "user" else "ai", msg.content)
                )
        self._render(intro_note)

    def _on_clear(self):
        if self._session:
            self._session.reset()
        self._messages = []
        self._lbl_status.setText("Sẵn sàng.")
        self._lbl_status.setStyleSheet("")
        self._render("Lịch sử đã được xóa. Hãy đặt câu hỏi mới.")

    def set_pdf(self, pdf_path: str, history_identity_path: str | None = None):
        """Cập nhật khi PDF thay đổi - tạo session mới."""
        identity_path = history_identity_path or pdf_path
        if pdf_path == self._pdf_path and identity_path == self._history_identity_path:
            return
        self._pdf_path = pdf_path
        self._history_identity_path = identity_path
        from packages.ai.chat_pdf import PDFChatSession
        self._session = PDFChatSession(self._pdf_path, max_history_messages=100, history_identity_path=self._history_identity_path)
        self._active_request_id = self._request_seq + 1
        self._request_seq = self._active_request_id
        self._busy = False
        self._btn_send.setEnabled(True)
        self._lbl_status.setStyleSheet("")
        self._lbl_status.setText("Sẵn sàng.")
        self._rebuild_chat()

    def closeEvent(self, event):
        event.accept()
        self.hide()

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
        )
