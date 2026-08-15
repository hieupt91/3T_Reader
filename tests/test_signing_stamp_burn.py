"""B2: _burn_stamp_onto_pdf() (packages/signing/shared.py) thay PyMuPDF
show_pdf_page() bằng pikepdf add_overlay() cho bước dán ảnh con dấu chữ ký
lên PDF trước khi ký thật bằng pyHanko. Đây là đường KÝ SỐ PHÁP LÝ thật -
test kỹ hơn mức thường: verify cả nội dung nhúng đúng, vị trí đúng (không
lệch/không dính ngoài box), VÀ pyHanko vẫn mở/xử lý được file kết quả không
lỗi (bước tiếp theo thật trong luồng ký)."""

from __future__ import annotations

import os

import pikepdf
import pytest

from packages.signing.shared import _burn_stamp_onto_pdf, build_vietnamese_stamp_style


def _make_target_pdf(path: str, *, rotate: int = 0) -> None:
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))
    if rotate:
        page["/Rotate"] = rotate
    pdf.save(path)
    pdf.close()


def test_burn_stamp_embeds_content_inside_target_box(tmp_path):
    target = str(tmp_path / "target.pdf")
    _make_target_pdf(target)
    box = (50.0, 50.0, 250.0, 120.0)

    _, stamp_pdf = build_vietnamese_stamp_style(
        "Nguyen Van Test", tax_code="0123456789", signed_at="14/08/2026 12:00:00",
        issuer_name="Test CA", cert_serial="ABC123", appearance_box=box,
    )
    assert stamp_pdf and os.path.exists(stamp_pdf)

    burned_path = _burn_stamp_onto_pdf(target, 1, box, stamp_pdf)
    try:
        assert os.path.exists(burned_path)
        with pikepdf.Pdf.open(burned_path) as pdf:
            assert len(pdf.pages) == 1
            page = pdf.pages[0]
            xobj = page.get("/Resources", {}).get("/XObject", {})
            assert xobj and len(xobj) > 0, "Không có XObject nào được nhúng - stamp không được dán"
    finally:
        for p in (burned_path, stamp_pdf):
            if p and os.path.exists(p) and p != target:
                os.remove(p)


def test_burn_stamp_renders_visible_content_at_correct_position(tmp_path):
    """Render vùng box trước/sau bằng pypdfium2, xác nhận: (a) vùng box CÓ
    thay đổi (không còn trắng tinh - stamp thật đã vẽ vào đó), (b) vùng NGOÀI
    box KHÔNG đổi (stamp không tràn ra ngoài vị trí chỉ định)."""
    import pypdfium2 as pdfium

    target = str(tmp_path / "target.pdf")
    _make_target_pdf(target)
    box = (100.0, 100.0, 300.0, 170.0)

    _, stamp_pdf = build_vietnamese_stamp_style(
        "Test Position Check", tax_code="9999999999", signed_at="14/08/2026 12:00:00",
        issuer_name="Test CA", cert_serial="XYZ789", appearance_box=box,
    )

    def _render_gray(path):
        doc = pdfium.PdfDocument(path)
        try:
            bitmap = doc[0].render(scale=1.0)
            return bitmap.to_pil().convert("L")
        finally:
            doc.close()

    before_img = _render_gray(target)
    burned_path = _burn_stamp_onto_pdf(target, 1, box, stamp_pdf)
    try:
        after_img = _render_gray(burned_path)
        assert before_img.size == after_img.size

        # PDF (0,0) = bottom-left; PIL ảnh (0,0) = top-left -> lật trục y.
        h = after_img.size[1]
        inside_before = before_img.crop((int(box[0]) + 5, int(h - box[3]) + 5, int(box[2]) - 5, int(h - box[1]) - 5))
        inside_after = after_img.crop((int(box[0]) + 5, int(h - box[3]) + 5, int(box[2]) - 5, int(h - box[1]) - 5))
        assert list(inside_before.getdata()) != list(inside_after.getdata()), \
            "Vùng trong box không đổi - stamp không được vẽ đúng chỗ"

        # Góc xa box (ngoài hẳn appearance_box) phải vẫn trắng tinh - stamp
        # không tràn/lệch ra ngoài vị trí chỉ định.
        outside_before = before_img.crop((450, 650, 600, 780))
        outside_after = after_img.crop((450, 650, 600, 780))
        assert list(outside_before.getdata()) == list(outside_after.getdata()), \
            "Vùng ngoài box bị thay đổi - stamp tràn ra ngoài vị trí chỉ định"
    finally:
        for p in (burned_path, stamp_pdf):
            if p and os.path.exists(p) and p != target:
                os.remove(p)


def test_burn_stamp_output_still_openable_by_pyhanko_incremental_writer(tmp_path):
    """Bước tiếp theo THẬT trong luồng ký (packages/signing/shared.py, cả
    PKCS11Signer lẫn PFX) mở lại đúng burn_input_path bằng
    IncrementalPdfFileWriter của pyHanko rồi ký - xác nhận file pikepdf vừa
    ghi không làm bước đó lỗi."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    target = str(tmp_path / "target.pdf")
    _make_target_pdf(target)
    box = (50.0, 50.0, 250.0, 120.0)

    _, stamp_pdf = build_vietnamese_stamp_style(
        "Nguyen Van Test", tax_code="0123456789", signed_at="14/08/2026 12:00:00",
        issuer_name="Test CA", cert_serial="ABC123", appearance_box=box,
    )
    burned_path = _burn_stamp_onto_pdf(target, 1, box, stamp_pdf)
    try:
        with open(burned_path, "rb") as f:
            writer = IncrementalPdfFileWriter(f, strict=False)
            assert len(writer.root["/Pages"]["/Kids"]) == 1
    finally:
        for p in (burned_path, stamp_pdf):
            if p and os.path.exists(p) and p != target:
                os.remove(p)


def test_burn_stamp_respects_rotated_target_page():
    """B16: overlay /Rotate phải khớp trang đích TRƯỚC khi merge - test trên
    trang đã xoay 90 độ, xác nhận không lỗi và vẫn nhúng đúng."""
    import tempfile

    target = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    _make_target_pdf(target, rotate=90)
    box = (50.0, 50.0, 250.0, 120.0)
    _, stamp_pdf = build_vietnamese_stamp_style(
        "Rotated Test", appearance_box=box,
    )
    burned_path = None
    try:
        burned_path = _burn_stamp_onto_pdf(target, 1, box, stamp_pdf)
        with pikepdf.Pdf.open(burned_path) as pdf:
            assert int(pdf.pages[0].get("/Rotate", 0)) == 90
            xobj = pdf.pages[0].get("/Resources", {}).get("/XObject", {})
            assert xobj and len(xobj) > 0
    finally:
        for p in (target, burned_path, stamp_pdf):
            if p and os.path.exists(p):
                os.remove(p)
