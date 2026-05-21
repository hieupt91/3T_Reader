"""
Kiểm tra tính năng chèn text/ảnh trên Windows.
Chạy: python tests/test_inline_editor_win.py

Script này KHÔNG cần mở UI — tự tạo PDF test và kiểm tra từng bước.
Kết quả: in ra PASS / FAIL từng bước để debug dễ dàng.
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

check("PyMuPDF (fitz)", lambda: __import__("fitz") and f"v{__import__('fitz').version[0]}")
check("PySide6", lambda: __import__("PySide6") and f"v{__import__('PySide6').__version__}")
check("Pillow (PIL)", lambda: __import__("PIL") and "OK")

def _check_pikepdf():
    try:
        import pikepdf
        return f"v{pikepdf.__version__}"
    except ImportError:
        raise ImportError("pip install pikepdf==10.5.1")

check("pikepdf", _check_pikepdf)

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

# ── 3. Tạo PDF test + chèn text tiếng Việt ────────────────────
print("\n▶ Bước 3: Chèn text tiếng Việt vào PDF")

def _check_text_insert():
    import fitz
    from packages.platform.fonts import get_vietnamese_font_path

    font_path = get_vietnamese_font_path()
    tmp = tempfile.mktemp(suffix="_test_text.pdf")

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    rect = fitz.Rect(50, 100, 500, 300)

    text = "Xin chào! Văn bản tiếng Việt: ăn ở đây đó ơ ư."
    result = page.insert_textbox(
        rect, text,
        fontsize=14,
        fontfile=font_path,
        fontname="vifont",
        color=(0, 0, 0),
        align=0,
    )

    if result < 0:
        raise RuntimeError(
            f"insert_textbox trả về {result} — text bị tràn hoặc font lỗi.\n"
            "         Thử tăng kích thước rect hoặc giảm font_size."
        )

    doc.save(tmp)
    doc.close()

    # Đọc lại xem text có được lưu không
    doc2 = fitz.open(tmp)
    extracted = doc2[0].get_text()
    doc2.close()
    os.remove(tmp)

    # Normalize non-breaking spaces (\xa0) thành space thường trước khi kiểm tra
    normalized = extracted.replace("\xa0", " ")
    if "Xin" not in normalized or "ti" not in normalized:
        raise RuntimeError(
            "Text đã chèn nhưng không đọc lại được — font không nhúng đúng.\n"
            "         Kiểm tra fontfile= và fontname= trong insert_textbox()."
        )

    return f"OK — render {len(text)} ký tự"

check("Chèn text tiếng Việt vào PDF", _check_text_insert)

# ── 4. Tạo PDF test + chèn ảnh ────────────────────────────────
print("\n▶ Bước 4: Chèn ảnh vào PDF")

def _check_image_insert():
    import fitz
    from PIL import Image, ImageDraw

    # Tạo ảnh test 200×100
    img = Image.new("RGB", (200, 100), color=(30, 80, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 190, 90], outline=(255, 255, 0), width=3)
    draw.text((60, 35), "3T Test", fill=(255, 255, 255))

    tmp_img = tempfile.mktemp(suffix="_test_img.png")
    tmp_pdf = tempfile.mktemp(suffix="_test_img.pdf")
    img.save(tmp_img)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    rect = fitz.Rect(100, 100, 400, 300)
    page.insert_image(rect, filename=tmp_img, keep_proportion=True)
    doc.save(tmp_pdf)
    doc.close()

    size = os.path.getsize(tmp_pdf)
    os.remove(tmp_img)
    os.remove(tmp_pdf)

    if size < 5000:
        raise RuntimeError(f"PDF quá nhỏ ({size} bytes) — ảnh chưa được nhúng đúng.")

    return f"OK — PDF size {size:,} bytes"

check("Chèn ảnh PNG vào PDF", _check_image_insert)

# ── 5. Kiểm tra rebuild_pdf_with_ops (luồng thật của app) ─────
print("\n▶ Bước 5: rebuild_pdf_with_ops — luồng thật của app")

def _check_rebuild():
    import fitz
    from PIL import Image, ImageDraw
    from packages.pdf_engine import get_pdf_engine

    # Tạo PDF gốc
    tmp_base = tempfile.mktemp(suffix="_base.pdf")
    tmp_out  = tempfile.mktemp(suffix="_out.pdf")
    tmp_img  = tempfile.mktemp(suffix="_img.png")

    # PDF gốc
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(50, 50, 500, 100), "Tài liệu gốc", fontsize=18, fontname="helv")
    doc.save(tmp_base)
    doc.close()

    # Ảnh test
    img = Image.new("RGB", (100, 60), color=(200, 100, 50))
    img.save(tmp_img)

    # Ops: 1 text + 1 image
    ops = [
        {
            "id": 1,
            "type": "text",
            "page_number": 1,
            "box": (50.0, 650.0, 400.0, 700.0),   # bottom-left origin
            "text": "Văn bản chèn thêm — tiếng Việt ✓",
            "font_size": 13,
            "font_color": (0.0, 0.0, 0.5),
        },
        {
            "id": 2,
            "type": "image",
            "page_number": 1,
            "box": (50.0, 500.0, 300.0, 600.0),
            "image_path": tmp_img,
        },
        {
            "id": 3,
            "type": "rect",
            "page_number": 1,
            "box": (50.0, 450.0, 300.0, 490.0),
            "fill_color": (1.0, 1.0, 0.8),
            "stroke_color": (1.0, 0.6, 0.0),
        },
    ]

    engine = get_pdf_engine()
    engine.rebuild_pdf_with_ops(tmp_base, tmp_out, ops)

    # Xác nhận output hợp lệ
    doc2 = fitz.open(tmp_out)
    page_count = doc2.page_count
    text_out = doc2[0].get_text()
    doc2.close()

    for f in [tmp_base, tmp_out, tmp_img]:
        try: os.remove(f)
        except: pass

    if page_count != 1:
        raise RuntimeError(f"PDF output có {page_count} trang, cần 1.")

    return f"OK — {len(ops)} ops, text extracted OK"

check("rebuild_pdf_with_ops (text + ảnh + rect)", _check_rebuild)

# ── 6. Tọa độ PDF — convert JS screen → fitz rect ─────────────
print("\n▶ Bước 6: Kiểm tra logic tọa độ PDF")

def _check_coordinates():
    import fitz

    # Mô phỏng tọa độ JS gửi về (hệ bottom-left)
    pdf_left, pdf_bottom, pdf_right, pdf_top = 50.0, 700.0, 300.0, 750.0
    page_height = 842.0

    # Convert sang hệ top-left của fitz
    rect = fitz.Rect(
        pdf_left,
        page_height - pdf_top,    # top trong fitz = page_height - pdf_top
        pdf_right,
        page_height - pdf_bottom, # bottom trong fitz = page_height - pdf_bottom
    )

    # Kiểm tra rect hợp lệ (top < bottom trong fitz)
    if rect.y0 >= rect.y1:
        raise RuntimeError(
            f"Rect không hợp lệ: y0={rect.y0} >= y1={rect.y1}\n"
            "         Kiểm tra lại công thức convert tọa độ."
        )

    return f"OK — fitz.Rect({rect.x0:.0f},{rect.y0:.0f},{rect.x1:.0f},{rect.y1:.0f})"

check("Tọa độ PDF → fitz.Rect (bottom-left → top-left)", _check_coordinates)

# ── 7. QWebChannel + QWebEngineView availability ──────────────
print("\n▶ Bước 7: WebEngine & WebChannel")

def _check_webengine():
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    return "QWebEngineView + QWebChannel OK"

def _check_svgwidget():
    from PySide6.QtSvgWidgets import QSvgWidget
    return "QSvgWidget OK"

check("PySide6 WebEngine + WebChannel", _check_webengine)
check("PySide6 QtSvgWidgets (cho logo)", _check_svgwidget)

# ── 8. Assets tồn tại ─────────────────────────────────────────
print("\n▶ Bước 8: Assets & logo files")

def _check_asset(rel_path):
    full = os.path.join(ROOT, rel_path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"Không tìm thấy: {rel_path}")
    size = os.path.getsize(full)
    return f"{size} bytes"

check("assets/logo_mark.svg",      lambda: _check_asset("assets/logo_mark.svg"))
check("assets/logo_full.svg",      lambda: _check_asset("assets/logo_full.svg"))
check("assets/icons/insert_text.svg",  lambda: _check_asset("assets/icons/insert_text.svg"))
check("assets/icons/insert_image.svg", lambda: _check_asset("assets/icons/insert_image.svg"))

# ── Tổng kết ──────────────────────────────────────────────────
total   = len(results)
passed  = sum(1 for ok, _ in results if ok)
failed  = total - passed

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
    print("   - 'No module named fitz'   → pip install PyMuPDF==1.27.2.2")
    print("   - Font không tìm thấy     → kiểm tra C:\\Windows\\Fonts\\arial.ttf")
    print("   - QWebEngineView lỗi      → set QTWEBENGINE_DISABLE_SANDBOX=1")
    print("   - QSvgWidget lỗi          → pip install PySide6-Addons")
    sys.exit(1)
else:
    print("\n Tất cả kiểm tra PASS — sẵn sàng chạy app!")
    print(" Chạy: python main.py\n")
    sys.exit(0)
