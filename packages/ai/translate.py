"""Dịch thuật Việt ↔ Anh cho tài liệu PDF."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .provider import ask_ai, AIResponse


@dataclass
class TranslationResult:
    original: str
    translated: str
    source_lang: str
    target_lang: str
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.translated)


_SYSTEM_VI_EN = (
    "Bạn là chuyên gia dịch thuật tài liệu pháp lý và kinh doanh tiếng Việt sang tiếng Anh. "
    "Dịch chính xác, giữ nguyên thuật ngữ chuyên ngành, định dạng và số liệu. "
    "Chỉ trả về bản dịch, không giải thích."
)

_SYSTEM_EN_VI = (
    "You are an expert translator for legal and business documents from English to Vietnamese. "
    "Translate accurately, preserving technical terms, formatting and numbers. "
    "Return only the translation, no explanation."
)


def translate_text(text: str, source_lang: str = "vi", target_lang: str = "en") -> TranslationResult:
    """Dịch đoạn văn bản. source_lang/target_lang: 'vi' hoặc 'en'."""
    if not text.strip():
        return TranslationResult(original=text, translated="", source_lang=source_lang,
                                 target_lang=target_lang, error="Văn bản rỗng.")

    if source_lang == "vi" and target_lang == "en":
        system = _SYSTEM_VI_EN
        prompt = f"Dịch đoạn văn sau sang tiếng Anh:\n\n{text}"
    elif source_lang == "en" and target_lang == "vi":
        system = _SYSTEM_EN_VI
        prompt = f"Translate the following text to Vietnamese:\n\n{text}"
    else:
        return TranslationResult(original=text, translated="", source_lang=source_lang,
                                 target_lang=target_lang,
                                 error=f"Chưa hỗ trợ cặp ngôn ngữ {source_lang}→{target_lang}.")

    resp = ask_ai(prompt, system=system, max_tokens=4096)
    if not resp.success:
        return TranslationResult(original=text, translated="", source_lang=source_lang,
                                 target_lang=target_lang, error=resp.error)

    return TranslationResult(original=text, translated=resp.text.strip(),
                             source_lang=source_lang, target_lang=target_lang)


def translate_pdf_page(pdf_path: str, page_num: int,
                       source_lang: str = "vi", target_lang: str = "en") -> TranslationResult:
    """Trích xuất văn bản trang PDF rồi dịch."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        try:
            page = doc[page_num - 1]
            text = page.get_text("text").strip()
        finally:
            doc.close()
    except Exception as e:
        return TranslationResult(original="", translated="", source_lang=source_lang,
                                 target_lang=target_lang, error=f"Không đọc được PDF: {e}")

    if not text:
        return TranslationResult(original="", translated="", source_lang=source_lang,
                                 target_lang=target_lang, error="Trang không có văn bản.")

    # Giới hạn 3000 ký tự để tránh vượt context
    if len(text) > 3000:
        text = text[:3000] + "\n[... nội dung bị cắt bớt ...]"

    return translate_text(text, source_lang, target_lang)
