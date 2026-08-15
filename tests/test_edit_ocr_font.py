"""TC30 "sửa text gốc": _find_pdf_span phải bỏ qua font giả GlyphLessFont mà
Tesseract textonly_pdf ghi vào PDF (auto-OCR, packages/ocr/engine.py), nhưng
vẫn giữ nguyên hành vi cũ cho text thật (không phải OCR)."""
from __future__ import annotations

import os

import pytest


def _skip_if_missing(*packages):
    missing = []
    for pkg in packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        pytest.skip(f"Missing dependencies: {missing}")


def _skip_if_no_tesseract():
    from packages.ocr.engine import is_available
    if not is_available():
        pytest.skip("Tesseract not available on this machine")


def test_find_pdf_span_ignores_ocr_placeholder_font(tmp_path):
    _skip_if_missing("reportlab", "pikepdf", "fitz", "pypdfium2", "PIL")
    _skip_if_no_tesseract()

    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas
    import pikepdf

    from app.actions.edit import _find_pdf_span
    from packages.ocr.engine import ocr_pdf_page_text_layer, merge_text_layer_into_pdf

    page_w_pt, page_h_pt = 612.0, 792.0
    scale = 2.0
    img = Image.new("RGB", (int(page_w_pt * scale), int(page_h_pt * scale)), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    draw.text((100, 100), "Regression Check 321", fill="black", font=font)

    img_path = tmp_path / "scan.png"
    pdf_path = tmp_path / "scan.pdf"
    img.save(img_path)

    c = canvas.Canvas(str(pdf_path), pagesize=(page_w_pt, page_h_pt))
    c.drawImage(str(img_path), 0, 0, width=page_w_pt, height=page_h_pt)
    c.save()

    text_layer_bytes = ocr_pdf_page_text_layer(str(pdf_path), 1, scale=scale)
    assert text_layer_bytes, "OCR did not produce a text layer"

    with pikepdf.open(str(pdf_path), allow_overwriting_input=True) as pdf:
        assert merge_text_layer_into_pdf(pdf, 0, text_layer_bytes)
        pdf.save(str(pdf_path))

    # Chữ vẽ ở pixel (100,100) trong ảnh cao 1584px (scale 2.0, PIL y tính từ
    # trên xuống) -> quy đổi ra điểm PDF (y tính từ dưới lên, gốc trang 792pt):
    # point_y_from_top = 100/2 = 50 -> pdf_y = 792 - 50 = 742 (mép trên chữ).
    span = _find_pdf_span(str(pdf_path), 1, (30.0, 690.0, 400.0, 760.0))

    assert span is not None
    assert span["is_ocr_placeholder_font"] is True
    assert span["font_family"] == ""
    assert span["bold"] is False
    # font_size vẫn phải là số hợp lý (không bị vô hiệu hoá theo font_family/bold)
    assert 10.0 < span["font_size"] < 60.0


def test_sample_background_color_reads_non_white_scan_background(tmp_path):
    """Redact trên ảnh scan phải lấy đúng màu nền thật (không phải trắng
    tinh mặc định), nếu không mảng redact sẽ lộ rõ trên nền ngả màu."""
    _skip_if_missing("reportlab", "PIL", "pypdfium2")

    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas

    from app.actions.edit import _sample_background_color

    page_w_pt, page_h_pt = 612.0, 792.0
    scale = 2.0
    # Giấy "ngả vàng" (cream), khác hẳn trắng tinh (255,255,255).
    cream = (235, 220, 180)
    img = Image.new("RGB", (int(page_w_pt * scale), int(page_h_pt * scale)), cream)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    draw.text((100, 100), "Background Sample Test", fill="black", font=font)

    img_path = tmp_path / "cream_scan.png"
    pdf_path = tmp_path / "cream_scan.pdf"
    img.save(img_path)

    c = canvas.Canvas(str(pdf_path), pagesize=(page_w_pt, page_h_pt))
    c.drawImage(str(img_path), 0, 0, width=page_w_pt, height=page_h_pt)
    c.save()

    # Box quanh chữ (xem test khác để biết cách quy đổi tọa độ pixel->pdf).
    box = (30.0, 690.0, 400.0, 760.0)
    color = _sample_background_color(str(pdf_path), 1, box)

    assert color is not None
    r, g, b = color
    # Phải gần màu cream đã vẽ (dung sai vì render/nén), và rõ ràng KHÔNG
    # phải trắng tinh (1.0, 1.0, 1.0).
    assert abs(r - cream[0] / 255.0) < 0.08
    assert abs(g - cream[1] / 255.0) < 0.08
    assert abs(b - cream[2] / 255.0) < 0.08
    assert not (r > 0.97 and g > 0.97 and b > 0.97)


def test_scan_patch_hides_old_text_without_white_box(tmp_path):
    """Miếng vá ảnh trên trang scan: sau khi vá + rebuild, vùng chữ cũ phải
    (1) không còn pixel chữ đen, (2) KHÔNG phải mảng trắng tinh — phải gần
    màu nền kem của trang scan."""
    _skip_if_missing("reportlab", "PIL", "pypdfium2", "pikepdf", "fitz")

    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas

    from app.actions.edit import _build_scan_patch, _page_is_scan_text
    from packages.pdf_engine import PdfiumEngine

    page_w_pt, page_h_pt = 612.0, 792.0
    scale = 2.0
    cream = (235, 220, 180)
    img = Image.new("RGB", (int(page_w_pt * scale), int(page_h_pt * scale)), cream)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    draw.text((100, 100), "Patch Me Away", fill="black", font=font)

    img_path = tmp_path / "scan.png"
    pdf_path = tmp_path / "scan.pdf"
    out_path = tmp_path / "patched.pdf"
    img.save(img_path)

    c = canvas.Canvas(str(pdf_path), pagesize=(page_w_pt, page_h_pt))
    c.drawImage(str(img_path), 0, 0, width=page_w_pt, height=page_h_pt)
    c.save()

    # Vùng chữ: pixel (100..~450, 100..~150) -> PDF pts: x 50..225, y đo từ
    # đỉnh 50..75 -> pdf_y 717..742.
    text_box = (48.0, 715.0, 230.0, 744.0)
    patch_info = _build_scan_patch(str(pdf_path), 1, text_box)
    assert patch_info is not None
    patch_path, patch_data_url, patch_box = patch_info
    assert os.path.exists(patch_path)
    assert patch_data_url.startswith("data:image/png;base64,")

    ops = [{
        "id": 1,
        "type": "image",
        "page_number": 1,
        "box": patch_box,
        "image_path": patch_path,
        "image_data_url": patch_data_url,
        "rotation": 0,
        "is_scan_patch": True,
    }]
    PdfiumEngine().rebuild_pdf_with_ops(str(pdf_path), str(out_path), ops)

    # Render kết quả và soi pixel vùng chữ cũ.
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(out_path))
    page = doc[0]
    rendered = page.render(scale=scale).to_pil().convert("RGB")
    doc.close()

    # Vùng chữ cũ trong ảnh render (cùng scale với lúc vẽ).
    region = rendered.crop((110, 105, 440, 145))
    pixels = list(region.getdata())
    dark = [p for p in pixels if p[0] < 100 and p[1] < 100 and p[2] < 100]
    white = [p for p in pixels if p[0] > 250 and p[1] > 250 and p[2] > 250]

    # 1) Chữ đen cũ phải biến mất (cho phép <1% pixel tối do viền feather).
    assert len(dark) / len(pixels) < 0.01, f"van con {len(dark)}/{len(pixels)} pixel chu cu"
    # 2) Không được thành mảng trắng tinh.
    assert len(white) / len(pixels) < 0.05, f"bi xoa trang: {len(white)}/{len(pixels)} pixel trang tinh"
    # 3) Màu trung bình vùng vá phải gần màu nền kem.
    avg_r = sum(p[0] for p in pixels) / len(pixels)
    avg_g = sum(p[1] for p in pixels) / len(pixels)
    avg_b = sum(p[2] for p in pixels) / len(pixels)
    assert abs(avg_r - cream[0]) < 20
    assert abs(avg_g - cream[1]) < 20
    assert abs(avg_b - cream[2]) < 20


def test_page_is_scan_text_detects_ocr_only_page(tmp_path):
    _skip_if_missing("reportlab", "PIL", "pypdfium2", "pikepdf", "fitz")
    _skip_if_no_tesseract()

    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas
    import pikepdf

    from app.actions.edit import _page_is_scan_text
    from packages.ocr.engine import ocr_pdf_page_text_layer, merge_text_layer_into_pdf

    page_w_pt, page_h_pt = 612.0, 792.0
    scale = 2.0
    img = Image.new("RGB", (int(page_w_pt * scale), int(page_h_pt * scale)), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    draw.text((100, 100), "Scan Detection 111", fill="black", font=font)

    img_path = tmp_path / "scan.png"
    scan_pdf = tmp_path / "scan.pdf"
    vector_pdf = tmp_path / "vector.pdf"
    img.save(img_path)

    c = canvas.Canvas(str(scan_pdf), pagesize=(page_w_pt, page_h_pt))
    c.drawImage(str(img_path), 0, 0, width=page_w_pt, height=page_h_pt)
    c.save()

    text_layer = ocr_pdf_page_text_layer(str(scan_pdf), 1, scale=scale)
    assert text_layer
    with pikepdf.open(str(scan_pdf), allow_overwriting_input=True) as pdf:
        merge_text_layer_into_pdf(pdf, 0, text_layer)
        pdf.save(str(scan_pdf))

    c = canvas.Canvas(str(vector_pdf), pagesize=(page_w_pt, page_h_pt))
    c.setFont("Helvetica", 24)
    c.drawString(100, 700, "Born digital text")
    c.save()

    assert _page_is_scan_text(str(scan_pdf), 1) is True
    assert _page_is_scan_text(str(vector_pdf), 1) is False


def test_find_pdf_span_keeps_real_font_for_non_ocr_text(tmp_path):
    _skip_if_missing("reportlab", "fitz")

    from reportlab.pdfgen import canvas

    from app.actions.edit import _find_pdf_span

    page_w_pt, page_h_pt = 612.0, 792.0
    pdf_path = tmp_path / "real_text.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=(page_w_pt, page_h_pt))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, 700, "Real Text Not OCR")
    c.save()

    span = _find_pdf_span(str(pdf_path), 1, (95.0, 695.0, 350.0, 725.0))

    assert span is not None
    assert span["is_ocr_placeholder_font"] is False
    assert "helvetica" in span["font_family"].lower()
    assert span["bold"] is True


# ── Màu mực thật cho "sửa text gốc" trên scan (SUA_TEXT_GOC_SCAN plan) ─────────

def _make_scan_pdf_with_rect(tmp_path, rect_px, rect_color,
                             page_w_pt=612.0, page_h_pt=792.0, scale=2.0):
    """Tạo PDF chỉ chứa ảnh (giống scan): nền trắng + 1 khối màu đặc tại
    vị trí pixel `rect_px`. Trả (pdf_path, page_h_pt, scale) để tính box PDF.
    """
    from PIL import Image, ImageDraw
    from reportlab.pdfgen import canvas

    img = Image.new("RGB", (int(page_w_pt * scale), int(page_h_pt * scale)), "white")
    ImageDraw.Draw(img).rectangle(rect_px, fill=rect_color)
    img_path = tmp_path / "scanrect.png"
    pdf_path = tmp_path / "scanrect.pdf"
    img.save(img_path)
    c = canvas.Canvas(str(pdf_path), pagesize=(page_w_pt, page_h_pt))
    c.drawImage(str(img_path), 0, 0, width=page_w_pt, height=page_h_pt)
    c.save()
    return str(pdf_path), page_h_pt, scale


def _px_rect_to_pdf_box(rect_px, page_h_pt, scale):
    """(x0,y0,x1,y1) pixel (gốc trên-trái) -> box PDF (left,bottom,right,top)."""
    x0, y0, x1, y1 = rect_px
    return (x0 / scale, page_h_pt - y1 / scale, x1 / scale, page_h_pt - y0 / scale)


def test_sample_text_ink_color_reads_dark_ink_not_background(tmp_path):
    _skip_if_missing("reportlab", "pypdfium2", "PIL")
    from app.actions.edit import _sample_text_ink_color

    rect_px = (200, 200, 500, 300)
    pdf, page_h, scale = _make_scan_pdf_with_rect(tmp_path, rect_px, (40, 40, 45))
    box = _px_rect_to_pdf_box(rect_px, page_h, scale)

    color = _sample_text_ink_color(pdf, 1, box)
    assert color is not None
    r, g, b = color
    # Phải ra màu MỰC (tối), KHÔNG phải nền trắng.
    assert r < 0.4 and g < 0.4 and b < 0.4, f"quá sáng, dính nền: {color}"
    # Và rõ ràng khác nền trắng (chênh > 0.5 mỗi kênh).
    assert (1.0 - r) > 0.5 and (1.0 - g) > 0.5, f"không tách được khỏi nền: {color}"


def test_sample_text_ink_color_handles_colored_ink(tmp_path):
    _skip_if_missing("reportlab", "pypdfium2", "PIL")
    from app.actions.edit import _sample_text_ink_color

    rect_px = (200, 200, 500, 300)
    # Mực xanh dương đậm — KHÔNG được ép về đen/xám trung tính.
    pdf, page_h, scale = _make_scan_pdf_with_rect(tmp_path, rect_px, (20, 30, 160))
    box = _px_rect_to_pdf_box(rect_px, page_h, scale)

    color = _sample_text_ink_color(pdf, 1, box)
    assert color is not None
    r, g, b = color
    assert b > r and b > g, f"mất sắc xanh, bị ép về trung tính: {color}"
    assert b > 0.4, f"kênh xanh quá thấp: {color}"


def test_sample_text_ink_color_is_position_accurate(tmp_path):
    """Xác nhận hàm tôn trọng ĐÚNG toạ độ box truyền vào (không snap/dời):
    box trùng khối mực -> tối; box ở vùng lề trắng -> sáng."""
    _skip_if_missing("reportlab", "pypdfium2", "PIL")
    from app.actions.edit import _sample_text_ink_color

    rect_px = (200, 200, 500, 300)
    pdf, page_h, scale = _make_scan_pdf_with_rect(tmp_path, rect_px, (30, 30, 30))

    box_on_ink = _px_rect_to_pdf_box(rect_px, page_h, scale)
    box_on_blank = _px_rect_to_pdf_box((800, 800, 1000, 900), page_h, scale)

    ink = _sample_text_ink_color(pdf, 1, box_on_ink)
    blank = _sample_text_ink_color(pdf, 1, box_on_blank)
    assert ink is not None and blank is not None
    assert max(ink) < 0.4, f"box trên mực phải tối: {ink}"
    assert min(blank) > 0.8, f"box trên lề trắng phải sáng: {blank}"
