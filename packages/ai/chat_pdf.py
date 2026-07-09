"""Chat với PDF — hỏi đáp nội dung tài liệu."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from .provider import ask_ai


@dataclass
class ChatMessage:
    role: str   # "user" | "assistant"
    content: str


@dataclass
class ChatResult:
    answer: str
    citations: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.answer)


_SYSTEM = (
    "Bạn là trợ lý AI phân tích tài liệu. Người dùng sẽ cung cấp nội dung PDF và đặt câu hỏi. "
    "Hãy trả lời dựa trên nội dung tài liệu, trích dẫn phần liên quan khi cần. "
    "Nếu thông tin không có trong tài liệu, hãy nói rõ. "
    "Trả lời bằng tiếng Việt, ngắn gọn và chính xác."
)


class PDFChatSession:
    """Session chat với một file PDF. Giữ lịch sử hội thoại."""

    def __init__(self, pdf_path: str, max_context_chars: int = 6000):
        # Lock identity to the resolved source path at open time.
        # Temp/auto-saved paths must NOT replace this — otherwise history
        # is lost when the file is reload-saved to a temp location.
        self.pdf_path = pdf_path
        self._chat_identity_path = os.path.realpath(pdf_path)
        self.max_context_chars = max_context_chars
        self.history: list[ChatMessage] = []
        self._pdf_text: Optional[str] = None

    def _load_text(self) -> str:
        if self._pdf_text is not None:
            return self._pdf_text
        try:
            import pdfplumber
            parts = []
            with pdfplumber.open(self.pdf_path) as doc:
                for i, page in enumerate(doc.pages):
                    t = (page.extract_text() or "").strip()
                    if t:
                        parts.append(f"[Trang {i+1}]\n{t}")
            text = "\n\n".join(parts)
            if len(text) > self.max_context_chars:
                text = text[:self.max_context_chars] + "\n\n[... tài liệu bị cắt bớt ...]"
            self._pdf_text = text
        except Exception as e:
            self._pdf_text = f"[Không đọc được tài liệu: {e}]"
        return self._pdf_text

    def ask(self, question: str) -> ChatResult:
        if not question.strip():
            return ChatResult(answer="", error="Câu hỏi rỗng.")

        pdf_text = self._load_text()
        if not pdf_text.strip():
            return ChatResult(answer="", error="Tài liệu không có văn bản.")

        # Xây dựng prompt với context PDF + lịch sử
        history_text = ""
        if self.history:
            lines = []
            for msg in self.history[-6:]:  # Giữ 6 tin nhắn gần nhất
                prefix = "Người dùng" if msg.role == "user" else "Trợ lý"
                lines.append(f"{prefix}: {msg.content}")
            history_text = "\n".join(lines) + "\n\n"

        prompt = (
            f"Nội dung tài liệu:\n{pdf_text}\n\n"
            f"{history_text}"
            f"Câu hỏi: {question}"
        )

        resp = ask_ai(prompt, system=_SYSTEM, max_tokens=1024)
        if not resp.success:
            return ChatResult(answer="", error=resp.error)

        answer = resp.text.strip()
        self.history.append(ChatMessage(role="user", content=question))
        self.history.append(ChatMessage(role="assistant", content=answer))

        return ChatResult(answer=answer)

    def reset(self):
        self.history.clear()
        self._pdf_text = None
