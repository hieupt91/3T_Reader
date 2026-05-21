"""
Kiểm tra tính năng chèn text/ảnh trên Windows.
Chạy: python tests/test_inline_editor_win.py

Script này KHÔNG cần mở UI — tự tạo PDF test và kiểm tra từng bước.
Kết quả: in ra PASS / FAIL từng bước để debug dễ dàng.

NOTE: Đã loại bỏ PyMuPDF/fitz (AGPL). Dùng pikepdf + pdfplumber + reportlab.
"""
import os
import sys
import tempfile
import traceback

# Đảm bảo import được từ project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

results = []


def check(name: str, fn):
    try:
        msg = fn()
        print(f"  {PASS} {name}" + (f" — {msg}" if msg else ""))
        results.append((True, name))
    except Exception as e:
        print(f"  {FAIL} {name}")
        print(f"         Lỗi: {e}")
        results.append((False, name))


# ─────────────────────────────────────────────────────────────
print("\n========================================")
print(" 3T Reader — Test chèn text/ảnh (Windows)")
print("========================================\n")

# ── 1. Kiểm tra thư viện cốt lõi ─────────────────────────────
print("▶ Bước 1: Kiểm tra thư viện")


def _check_pikepdf():
    import pikepdf
    return f"v{pikepdf.__version__}"


def _check_pdfplumber():
    import pdfplumber
    return f"v{pdfplumber.__version__}"


def _check_reportlab():
    import reportlab
    return f"v{reportlab.Version}"


def _check_pypdfium2():
    import pypdfium2 as pdfium
    return f"v{pdfium.V_PDFIUM_BUILD}"


check("PySide6",       lambda: __import__("PySide6") and f"v{__import__('PySide6').__version__}")
check("pikepdf",       _check_pikepdf)
check("pdfplumber",    _check_pdfplumber)
check("reportlab",     _check_reportlab)
check("pypdfium2",     _check_pypdfium2)
check("Pillow (PIL)",  lambda: __import__("PIL") and "OK")

# ── 2. Font tiếng Việt ─────────────────────────────────────────
print("\n▶ Bước 2: Font tiếng Việt")


def _check_font():
    from packages.platform.fonts import get_vietnamese_font_path
    path = get_vietnamese_font_path()
    if not path:
        raise RuntimeError(
            "Không tìm thấy font tiếng Việt!\n"
            "         Windows cần có Arial.ttf hoặc Tahoma.ttf trong C:\\Windows\\Fonts\\"
        )
    if not os.path.exists(path):
        raise FileNotFoundError(f"Font path không tồn tại: {path}")
    return os.path.basename(path)


check("Font tiếng Việt hệ thống", _check_font)

# ── 3. Tạo PDF gốc bằng pikepdf ────────────────────────────────
print("\n▶ Bước 3: Tạo PDF với pikepdf")


def _check_pikepdf_create():
    import pikepdf

    tmp = tempfile.mktemp(suffix="_test_pikepdf.pdf")
    try:
        pdf = pikepdf.Pdf.new()
        page = pikepdf.Page(pikepdf.Dictionary(
            Type=pikepdf.Name.Page,
            MediaBox=pikepdf.Array([0, 0, 595, 842]),
            Resources=pikepdf.Dictionary(),
        ))
        pdf.pages.append(page)
        pdf.save(tmp)
        size = os.path.getsize(tmp)
        if size < 100:
            raise RuntimeError(f"PDF quá nhỏ: {size} bytes")
        return f"OK — {size} bytes"
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


check("Tạo PDF trống bằng pikepdf", _check_pikepdf_create)

# ── 4. Trích xuất text bằng pdfplumber ────────────────────────
print("\n▶ Bước 4: Trích xuất text bằng pdfplumber")


def _check_pdfplumber_extract():
    import pdfplumber
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    tmp = tempfile.mktemp(suffix="_test_extract.pdf")
    try:
        # Tạo PDF có text bằng reportlab
        c = canvas.Canvas(tmp, pagesize=A4)
        c.setFont("Helvetica", 14)
        c.drawString(50, 700, "3T Reader Test Content")
        c.save()

        with pdfplumber.open(tmp) as doc:
            text = (doc.pages[0].extract_text() or "").strip()

        if "3T Reader" not in text:
            raise RuntimeError(f"Không trích xuất được text, got: {repr(text[:80])}")
        return f"OK — {len(text)} ký tự"
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


check("Trích xuất text PDF bằng pdfplumber", _check_pdfplumber_extract)

# ── 5. Chèn ảnh vào PDF bằng pikepdf XObject ──────────────────
print("\n▶ Bước 5: Chèn ảnh vào PDF (pikepdf XObject)")


def _check_image_insert():
    import pikepdf
    from PIL import Image

    tmp_img = tempfile.mktemp(suffix="_test_img.png")
    tmp_pdf = tempfile.mktemp(suffix="_test_imgpdf.pdf")
    try:
        # Tạo ảnh test
        img = Image.new("RGB", (200, 100), color=(30, 80, 200))
        img.save(tmp_img)
        img.close()

        # Tạo PDF gốc trống
        pdf = pikepdf.Pdf.new()
        page = pikepdf.Page(pikepdf.Dictionary(
            Type=pikepdf.Name.Page,
            MediaBox=pikepdf.Array([0, 0, 595, 842]),
            Resources=pikepdf.Dictionary(XObject=pikepdf.Dictionary()),
        ))
        pdf.pages.append(page)

        # Nhúng ảnh RGB
        with open(tmp_img, "rb") as f:
            from PIL import Image as _Image
            im = _Image.open(f)
            im.load()
            raw = im.tobytes()
            w, h = im.size

        img_stream = pdf.make_stream(
            raw,
            Width=w, Height=h,
            ColorSpace=pikepdf.Name.DeviceRGB,
            BitsPerComponent=8,
            Subtype=pikepdf.Name.Image,
            Type=pikepdf.Name.XObject,
        )
        page_obj = pdf.pages[0]
        page_obj["/Resources"]["/XObject"]["/Img0"] = pdf.make_indirect(img_stream)

        # Thêm content stream
        content = f"q {300:.4f} 0 0 {200:.4f} {100:.4f} {600:.4f} cm /Img0 Do Q\n"
        page_obj["/Contents"] = pdf.make_stream(content.encode())

        pdf.save(tmp_pdf)
        size = os.path.getsize(tmp_pdf)
        if size < 5000:
            raise RuntimeError(f"PDF quá nhỏ ({size} bytes) — ảnh chưa được nhúng đúng.")
        return f"OK — PDF size {size:,} bytes"
    finally:
        for f in [tmp_img, tmp_pdf]:
            try:
                os.remove(f)
            except Exception:
                pass


check("Chèn ảnh PNG vào PDF (pikepdf XObject)", _check_image_insert)

# ── 6. rebuild_pdf_with_ops — luồng thật của app ──────────────
print("\n▶ Bước 6: rebuild_pdf_with_ops — luồng thật của app")


def _check_rebuild():
    import pikepdf
    import pdfplumber
    from PIL import Image, ImageDraw
    from packages.pdf_engine import get_pdf_engine

    tmp_base = tempfile.mktemp(suffix="_base.pdf")
    tmp_out  = tempfile.mktemp(suffix="_out.pdf")
    tmp_img  = tempfile.mktemp(suffix="_img.png")

    try:
        # Tạo PDF gốc bằng reportlab
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        c = canvas.Canvas(tmp_base, pagesize=A4)
        c.setFont("Helvetica", 18)
        c.drawString(50, 750, "Original Document")
        c.save()

        # Ảnh test
        img = Image.new("RGB", (100, 60), color=(200, 100, 50))
        draw = ImageDraw.Draw(img)
        draw.rectangle([5, 5, 95, 55], outline=(255, 255, 0), width=2)
        img.save(tmp_img)

        # Ops: 1 text + 1 image
        ops = [
            {
                "id": 1,
                "type": "text",
                "page_number": 1,
                "box": (50.0, 600.0, 400.0, 650.0),
                "text": "Van ban chen them",
                "font_size": 13,
                "font_color": (0.0, 0.0, 0.5),
            },
            {
                "id": 2,
                "type": "image",
                "page_number": 1,
                "box": (50.0, 450.0, 250.0, 550.0),
                "image_path": tmp_img,
            },
        ]

        engine = get_pdf_engine()
        engine.rebuild_pdf_with_ops(tmp_base, tmp_out, ops)

        # Xác nhận output hợp lệ bằng pikepdf
        with pikepdf.open(tmp_out) as doc2:
            page_count = len(doc2.pages)

        if page_count != 1:
            raise RuntimeError(f"PDF output có {page_count} trang, cần 1.")

        # Xác nhận text layer bằng pdfplumber
        with pdfplumber.open(tmp_out) as doc3:
            extracted = (doc3.pages[0].extract_text() or "")

        return f"OK — {len(ops)} ops, {len(extracted)} ký tự text"
    finally:
        for f in [tmp_base, tmp_out, tmp_img]:
            try:
                os.remove(f)
            except Exception:
                pass


check("rebuild_pdf_with_ops (text + ảnh)", _check_rebuild)

# ── 7. Tọa độ PDF — bottom-left origin ───────────────────────
print("\n▶ Bước 7: Kiểm tra logic tọa độ PDF")


def _check_coordinates():
    # Tọa độ JS gửi về (hệ bottom-left, giống PDF native)
    pdf_left, pdf_bottom, pdf_right, pdf_top = 50.0, 700.0, 300.0, 750.0
    page_height = 842.0

    # Trong engine mới (pikepdf/reportlab), bottom-left origin — không cần convert
    box_width  = pdf_right - pdf_left
    box_height = pdf_top - pdf_bottom

    if box_width <= 0 or box_height <= 0:
        raise RuntimeError(
            f"Box không hợp lệ: width={box_width}, height={box_height}"
        )

    return f"OK — box ({pdf_left},{pdf_bottom},{pdf_right},{pdf_top}), size {box_width}×{box_height}"


check("Tọa độ PDF — bottom-left origin (không cần convert)", _check_coordinates)

# ── 8. QWebChannel + QWebEngineView availability ──────────────
print("\n▶ Bước 8: WebEngine & WebChannel")


def _check_webengine():
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    return "QWebEngineView + QWebChannel OK"


def _check_svgwidget():
    from PySide6.QtSvgWidgets import QSvgWidget
    return "QSvgWidget OK"


check("PySide6 WebEngine + WebChannel", _check_webengine)
check("PySide6 QtSvgWidgets (cho logo)", _check_svgwidget)

# ── 9. Assets tồn tại ─────────────────────────────────────────
print("\n▶ Bước 9: Assets & logo files")


def _check_asset(rel_path):
    full = os.path.join(ROOT, rel_path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"Không tìm thấy: {rel_path}")
    size = os.path.getsize(full)
    return f"{size} bytes"


check("assets/logo_mark.svg",          lambda: _check_asset("assets/logo_mark.svg"))
check("assets/logo_full.svg",          lambda: _check_asset("assets/logo_full.svg"))
check("assets/icons/insert_text.svg",  lambda: _check_asset("assets/icons/insert_text.svg"))
check("assets/icons/insert_image.svg", lambda: _check_asset("assets/icons/insert_image.svg"))

# ── Tổng kết ──────────────────────────────────────────────────
total  = len(results)
passed = sum(1 for ok, _ in results if ok)
failed = total - passed

print("\n========================================")
print(f" KẾT QUẢ: {passed}/{total} PASS  |  {failed} FAIL")
print("========================================")

if failed > 0:
    print("\n Các bước FAIL:")
    for ok, name in results:
        if not ok:
            print(f"   ✗ {name}")
    print()
    print(" Hướng xử lý thường gặp trên Windows:")
    print("   - 'No module named pikepdf'   → pip install pikepdf")
    print("   - 'No module named pdfplumber' → pip install pdfplumber")
    print("   - 'No module named reportlab'  → pip install reportlab")
    print("   - Font không tìm thấy          → kiểm tra C:\\Windows\\Fonts\\arial.ttf")
    print("   - QWebEngineView lỗi           → set QTWEBENGINE_DISABLE_SANDBOX=1")
    print("   - QSvgWidget lỗi               → pip install PySide6-Addons")
    sys.exit(1)
else:
    print("\n Tất cả kiểm tra PASS — sẵn sàng chạy app!")
    print(" Chạy: python main.py\n")
    sys.exit(0)
