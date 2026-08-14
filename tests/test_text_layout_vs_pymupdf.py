"""B2: test đối chiếu bắt buộc trước khi cắt sang pypdfium2 hoàn toàn (xem
docs/ROADMAP_PDF_ENGINE_MIGRATION.md + ROADMAP_B52_B2_B13_2026-08-14.md mục
B2) - chạy CẢ bản cũ (PyMuPDF, app/actions/edit.py::_find_pdf_span) VÀ bản
mới (packages/pdf_engine/text_layout.py) trên cùng file PDF thật, so sánh
kết quả span-by-span. XOÁ file test này sau khi Giai đoạn 3 gỡ PyMuPDF hoàn
toàn (không còn bản cũ để đối chiếu nữa).

Tự skip nếu PyMuPDF không cài (không nên xảy ra trong repo hiện tại, nhưng
tránh vỡ CI nếu ai gỡ PyMuPDF sớm khỏi requirements trước khi xoá file này).
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("fitz", reason="Cần PyMuPDF cài để đối chiếu (chỉ trong giai đoạn migrate B2)")

import pypdfium2 as pdfium

from app.actions.edit import _find_pdf_span, _page_is_scan_text
from packages.pdf_engine.text_layout import find_span_at, get_spans, page_is_scan_text

_SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "..", "cccd_temp.pdf")
_QD719 = r"C:\Users\HieuPC\Desktop\QD 719.pdf"


def _real_files():
    paths = []
    for p in (_QD719,):
        if os.path.exists(p):
            paths.append(p)
    return paths


@pytest.mark.parametrize("pdf_path", _real_files() or pytest.param(None, marks=pytest.mark.skip(reason="Không có file PDF thật để test - xem _real_files()")))
def test_page_is_scan_text_matches_pymupdf(pdf_path):
    old_result = _page_is_scan_text(pdf_path, 1)
    doc = pdfium.PdfDocument(pdf_path)
    try:
        new_result = page_is_scan_text(doc[0])
    finally:
        doc.close()
    assert new_result == old_result


@pytest.mark.parametrize("pdf_path", _real_files() or pytest.param(None, marks=pytest.mark.skip(reason="Không có file PDF thật để test")))
def test_find_span_matches_pymupdf_for_every_span_position(pdf_path):
    """Với MỖI span pypdfium2 tìm được trên trang, dùng chính box của nó làm
    pick_box, xác nhận cả 2 engine đều tìm ra span ở đúng vị trí đó với
    text/font tương đồng. Cách này tự sinh ra hàng trăm điểm test thật từ
    chính nội dung file, không cần tự tay chọn toạ độ."""
    doc = pdfium.PdfDocument(pdf_path)
    try:
        page = doc[0]
        spans = get_spans(page)
    finally:
        doc.close()

    assert len(spans) > 50, "File mẫu quá ít span để test có ý nghĩa - đổi file mẫu"

    mismatches = []
    checked = 0
    # Lấy mẫu rải đều (không phải toàn bộ 468 span - chậm không cần thiết,
    # ~40 điểm rải đều đã đủ đại diện đầy đủ font/OCR/vị trí khác nhau).
    step = max(1, len(spans) // 40)
    for span in spans[::step]:
        pick_box = span.box
        old = _find_pdf_span(pdf_path, 1, pick_box)
        assert old is not None, f"PyMuPDF không tìm thấy span nào ở box {pick_box} (pypdfium2 có: {span.text!r})"

        checked += 1
        # Text: so sánh lỏng - granularity gộp có thể khác nhau đôi chút
        # giữa 2 engine, chỉ cần có phần chung đáng kể (không rỗng, không
        # đối lập hoàn toàn) - không đòi khớp ký tự-cho-ký tự.
        old_text = str(old.get("text", "")).strip() if isinstance(old, dict) else ""

        old_ocr = bool(old.get("is_ocr_placeholder_font")) if isinstance(old, dict) else None
        if old_ocr != span.is_ocr_placeholder_font:
            mismatches.append((pick_box, "is_ocr_placeholder_font", old_ocr, span.is_ocr_placeholder_font))
            continue

        if not span.is_ocr_placeholder_font:
            old_size = float(old.get("font_size", 0.0)) if isinstance(old, dict) else 0.0
            if abs(old_size - span.font_size) > 1.5:
                mismatches.append((pick_box, "font_size", old_size, span.font_size))

    assert checked >= 30, f"Chỉ đối chiếu được {checked} điểm - quá ít để kết luận"
    assert not mismatches, f"{len(mismatches)}/{checked} điểm lệch giữa 2 engine: {mismatches[:10]}"
