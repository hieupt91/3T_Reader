"""Dialog chat với PDF — AI Assistant."""
from __future__ import annotations

import threading

from packages.qt_compat.QtCore import Qt, QTimer, QObject, pyqtSignal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QLineEdit, QSizePolicy,
)

_STYLE = """
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
"""

_MSG_USER_TMPL = (
    '<div style="margin:8px 0;padding:10px 14px;background:#1E1E48;'
    'border-radius:8px;border-left:3px solid #6366f1;">'
    '<span style="color:#9090D0;font-size:11px;font-weight:600;">Bạn</span><br>'
    '<span style="color:#E0E8FF;">{text}</span></div>'
)

_MSG_AI_TMPL = (
    '<div style="margin:8px 0;padding:10px 14px;background:#12122A;'
    'border-radius:8px;border-left:3px solid #4fc080;">'
    '<span style="color:#4fc080;font-size:11px;font-weight:600;">AI Assistant</span><br>'
    '<span style="color:#C8D8F8;">{text}</span></div>'
)

_MSG_ERROR_TMPL = (
    '<div style="margin:8px 0;padding:10px 14px;background:#2A1A1A;'
    'border-radius:8px;border-left:3px solid #E05050;">'
    '<span style="color:#E05050;font-size:11px;font-weight:600;">Lỗi</span><br>'
    '<span style="color:#F08080;">{text}</span></div>'
)

_MSG_THINKING = (
    '<div style="margin:8px 0;padding:10px 14px;background:#12122A;'
    'border-radius:8px;border-left:3px solid #4fc080;">'
    '<span style="color:#4fc080;font-size:11px;font-weight:600;">AI Assistant</span><br>'
    '<span style="color:#6070A0;font-style:italic;">AI đang trả lời…</span></div>'
)


class _ChatWorker(QObject):
    finished = pyqtSignal(object)   # ChatResult
    error    = pyqtSignal(str)

    def __init__(self, session, question: str):
        super().__init__()
        self._session  = session
        self._question = question

    def run(self):
        try:
            result = self._session.ask(self._question)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AIChatDialog(QDialog):
    """Dialog chat với PDF — non-modal, giữ nguyên khi đọc."""

    def __init__(self, parent, pdf_path: str):
        super().__init__(parent)
        self.setWindowTitle("Chat với PDF — AI Assistant")
        self.setModal(False)
        self.setMinimumWidth(600)
        self.resize(680, 600)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        self._pdf_path = pdf_path
        self._session  = None
        self._busy     = False

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

    def _append_html(self, html: str):
        self._chat_area.append(html)
        sb = self._chat_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _append_system_msg(self, text: str):
        html = (
            f'<div style="margin:6px 0;color:#6070A0;font-size:11px;font-style:italic;">'
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
                _MSG_ERROR_TMPL.format(
                    text="Chưa cấu hình API key AI. Vào Settings để cài đặt."
                )
            )
            return

        if self._session is None:
            from packages.ai.chat_pdf import PDFChatSession
            self._session = PDFChatSession(self._pdf_path)

        self._input.clear()
        self._append_html(_MSG_USER_TMPL.format(text=self._escape(question)))
        self._append_html(_MSG_THINKING)

        self._busy = True
        self._btn_send.setEnabled(False)
        self._lbl_status.setText("AI đang trả lời…")

        self._worker = _ChatWorker(self._session, question)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        thread = threading.Thread(target=self._worker.run, daemon=True)
        thread.start()

    def _remove_thinking_bubble(self):
        cursor = self._chat_area.document().find(_MSG_THINKING)
        html = self._chat_area.toHtml()
        # Replace the thinking indicator with empty before appending real answer
        # We re-render chat from scratch to keep it clean
        # Simpler: just let new message append after; the thinking bubble stays brief

    def _on_finished(self, result):
        self._busy = False
        self._btn_send.setEnabled(True)

        # Remove thinking bubble by rebuilding from session history
        self._rebuild_chat()

        if result.success:
            self._lbl_status.setStyleSheet("color:#4fc080;font-size:11px")
            self._lbl_status.setText("Sẵn sàng.")
        else:
            self._append_html(
                _MSG_ERROR_TMPL.format(text=self._escape(result.error or "Lỗi không xác định."))
            )
            self._lbl_status.setStyleSheet("color:#E05050;font-size:11px")
            self._lbl_status.setText(f"Lỗi: {result.error}")

    def _on_error(self, msg: str):
        self._busy = False
        self._btn_send.setEnabled(True)
        self._rebuild_chat()
        self._append_html(_MSG_ERROR_TMPL.format(text=self._escape(msg)))
        self._lbl_status.setStyleSheet("color:#E05050;font-size:11px")
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
                        _MSG_USER_TMPL.format(text=self._escape(msg.content))
                    )
                else:
                    self._append_html(
                        _MSG_AI_TMPL.format(text=self._escape(msg.content))
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
        self._chat_area.clear()
        self._append_system_msg(
            f"Tài liệu đã thay đổi: <i>{pdf_path}</i><br>"
            "Session mới được tạo. Hãy đặt câu hỏi."
        )

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
        )
