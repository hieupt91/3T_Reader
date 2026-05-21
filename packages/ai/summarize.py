"""Tóm tắt tài liệu PDF — hợp đồng, đề xuất, biên bản..."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .provider import ask_ai


@dataclass
class SummaryResult:
    summary: str
    doc_type: str = ""
    key_points: list[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.key_points is None:
            self.key_points = []

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.summary)


_DOC_TYPES = {
    "contract":  "hợp đồng",
    "proposal":  "đề xuất / báo giá",
    "minutes":   "biên bản họp",
    "report":    "báo cáo",
    "invoice":   "hóa đơn / chứng từ",
    "legal":     "văn bản pháp lý",
    "general":   "tài liệu thông thường",
}

_SYSTEM = (
    "Bạn là chuyên gia phân tích tài liệu doanh nghiệp Việt Nam. "
    "Tóm tắt ngắn gọn, chính xác, trích dẫn các điểm quan trọng nhất. "
    "Trả lời bằng tiếng Việt, định dạng rõ ràng."
)


def summarize_text(text: str, doc_type: str = "general",
                   language: str = "vi") -> SummaryResult:
    """Tóm tắt đoạn văn bản."""
    if not text.strip():
        return SummaryResult(summary="", error="Văn bản rỗng.")

    type_label = _DOC_TYPES.get(doc_type, doc_type)
    lang_hint = "Trả lời bằng tiếng Việt." if language == "vi" else "Reply in English."

    prompt = (
        f"Đây là nội dung {type_label}. {lang_hint}\n\n"
        f"Hãy:\n"
        f"1. Tóm tắt nội dung chính (3-5 câu)\n"
        f"2. Liệt kê các điểm quan trọng nhất (bullet points)\n"
        f"3. Nêu rõ các điều khoản / số liệu / ngày tháng đáng chú ý (nếu có)\n\n"
        f"Nội dung:\n{text}"
    )

    resp = ask_ai(prompt, system=_SYSTEM, max_tokens=2048)
    if not resp.success:
        return SummaryResult(summary="", error=resp.error)

    return SummaryResult(summary=resp.text.strip(), doc_type=doc_type)


def summarize_pdf(pdf_path: str, doc_type: str = "general",
                  max_pages: int = 20, language: str = "vi") -> SummaryResult:
    """Tóm tắt toàn bộ file PDF (tối đa max_pages trang)."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        try:
            total = doc.page_count
            pages_to_read = min(total, max_pages)
            parts = []
            for i in range(pages_to_read):
                t = doc[i].get_text("text").strip()
                if t:
                    parts.append(f"[Trang {i+1}]\n{t}")
        finally:
            doc.close()
    except Exception as e:
        return SummaryResult(summary="", error=f"Không đọc được PDF: {e}")

    if not parts:
        return SummaryResult(summary="", error="Tài liệu không có văn bản.")

    text = "\n\n".join(parts)
    # Giới hạn 6000 ký tự
    if len(text) > 6000:
        text = text[:6000] + "\n[... nội dung bị cắt bớt ...]"

    return summarize_text(text, doc_type, language)


def extract_contract_data(text: str) -> SummaryResult:
    """Trích xuất dữ liệu có cấu trúc từ hợp đồng: số HĐ, ngày, các bên, giá trị..."""
    if not text.strip():
        return SummaryResult(summary="", error="Văn bản rỗng.")

    prompt = (
        "Trích xuất thông tin từ hợp đồng sau. Trả về dạng danh sách có cấu trúc:\n\n"
        "- Số hợp đồng:\n"
        "- Ngày ký:\n"
        "- Bên A (tên, đại diện, địa chỉ):\n"
        "- Bên B (tên, đại diện, địa chỉ):\n"
        "- Giá trị hợp đồng:\n"
        "- Thuế VAT:\n"
        "- Thời hạn thực hiện:\n"
        "- Điều khoản thanh toán:\n"
        "- Phạt vi phạm (nếu có):\n"
        "- Ngày hiệu lực:\n\n"
        f"Nội dung hợp đồng:\n{text}"
    )

    system = (
        "Bạn là chuyên gia pháp lý. Trích xuất chính xác các thông tin từ hợp đồng. "
        "Nếu thông tin không có trong văn bản, ghi 'Không có'. Trả lời bằng tiếng Việt."
    )

    resp = ask_ai(prompt, system=system, max_tokens=2048)
    if not resp.success:
        return SummaryResult(summary="", doc_type="contract", error=resp.error)

    return SummaryResult(summary=resp.text.strip(), doc_type="contract")
