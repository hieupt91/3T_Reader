"""B2: đọc span văn bản (text + font/size/color/vị trí) từ PDF bằng
pypdfium2 (PDFium, BSD-3-Clause), thay thế PyMuPDF (AGPL-3.0) cho
`app/actions/edit.py::_find_pdf_span`/`_page_is_scan_text`.

Viết từ API công khai của pypdfium2 + hiểu biết cấu trúc PDF (ISO 32000-2),
KHÔNG đọc/tham khảo mã nguồn MuPDF/PyMuPDF lúc viết - xem
docs/ROADMAP_PDF_ENGINE_MIGRATION.md và
docs/ROADMAP_B52_B2_B13_2026-08-14.md mục B2 để biết đầy đủ bối cảnh pháp lý
+ lý do không chỉ "vá 2 hàm cho xong AGPL".

Toạ độ trả về đều ở không gian PDF gốc (bottom-up, gốc góc trái-dưới trang) -
pypdfium2's get_bounds() đã trả đúng hệ này sẵn, KHÔNG cần lật trục y như
PyMuPDF (PyMuPDF dùng hệ top-down riêng của nó, phải tự lật lại "page_h - y").
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field

_OCR_PLACEHOLDER_MARKER = "glyphless"


@dataclass
class Span:
    text: str
    box: tuple[float, float, float, float]  # left, bottom, right, top (PDF gốc, bottom-up)
    baseline: tuple[float, float]
    font_size: float
    font_family: str
    font_color: tuple[float, float, float]
    bold: bool
    italic: bool
    is_ocr_placeholder_font: bool = field(default=False)


def _get_fill_color(textobj) -> tuple[float, float, float]:
    """Màu tô chữ - pypdfium2 chưa bọc method cấp cao cho việc này (đã tự
    kiểm tra trực tiếp, xem ROADMAP_B52_B2_B13...), phải gọi thẳng hàm C
    FPDFTextObj_GetFillColor qua pdfium.raw (binding ctypes chính thức mà
    pypdfium2 luôn expose cho mọi hàm PDFium, kể cả hàm chưa có wrapper)."""
    try:
        import pypdfium2.raw as pdfium_c

        r, g, b, a = (ctypes.c_uint() for _ in range(4))
        ok = pdfium_c.FPDFTextObj_GetFillColor(
            textobj.raw, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b), ctypes.byref(a)
        )
        if ok:
            return (r.value / 255.0, g.value / 255.0, b.value / 255.0)
    except Exception:
        pass
    return (0.0, 0.0, 0.0)


def _text_object_baseline(textobj) -> tuple[float, float]:
    """Điểm gốc (baseline start) của text object - suy từ thành phần dịch
    chuyển (e, f) của ma trận biến đổi, đúng với trường hợp PDF thường
    (không xoay/nghiêng phức tạp text object). Đây là xấp xỉ hợp lý, giống
    quy ước "origin" mà PyMuPDF cũng dùng."""
    try:
        matrix = textobj.get_matrix()
        # pypdfium2 PdfMatrix có thuộc tính a,b,c,d,e,f theo đúng chuẩn PDF.
        return (float(matrix.e), float(matrix.f))
    except Exception:
        bounds = textobj.get_bounds()
        return (float(bounds[0]), float(bounds[1]))


def _font_info(textobj) -> tuple[str, bool, bool]:
    """Trả (font_family, bold, italic)."""
    try:
        font = textobj.get_font()
        name = str(font.get_base_name() or font.get_family_name() or "")
        weight = int(font.get_weight() or 400)
    except Exception:
        return "", False, False
    name_lower = name.lower()
    bold = weight >= 600 or "bold" in name_lower
    italic = "italic" in name_lower or "oblique" in name_lower
    return name, bold, italic


def _iter_text_objects(page, textpage):
    """`textpage` PHẢI được gán vào mỗi PdfTextObj trước khi gọi
    `.extract()` - không tự động có sẵn khi lấy qua `page.get_objects()`,
    thiếu bước này `FPDFTextObj_GetText` (bên trong `.extract()`) luôn thất
    bại (đã tự kiểm tra trực tiếp, không có trong tài liệu chính thức rõ
    ràng)."""
    import pypdfium2 as pdfium

    for obj in page.get_objects():
        if isinstance(obj, pdfium.PdfTextObj):
            obj.textpage = textpage
            yield obj


def _span_from_object(textobj) -> Span | None:
    try:
        text = textobj.extract()
    except Exception:
        return None
    if not text or not text.strip():
        return None
    try:
        bounds = textobj.get_bounds()
        font_size = float(textobj.get_font_size() or 0.0)
    except Exception:
        return None
    font_family, bold, italic = _font_info(textobj)
    is_ocr = _OCR_PLACEHOLDER_MARKER in font_family.lower()
    return Span(
        text=text,
        box=(float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])),
        baseline=_text_object_baseline(textobj),
        font_size=font_size,
        font_family="" if is_ocr else font_family,
        font_color=_get_fill_color(textobj),
        bold=False if is_ocr else bold,
        italic=False if is_ocr else italic,
        is_ocr_placeholder_font=is_ocr,
    )


def get_spans(page) -> list[Span]:
    """Duyệt toàn bộ text object trên `page` (đối tượng pypdfium2 PdfPage),
    trả 1 Span cho mỗi text object có nội dung khác rỗng. KHÔNG gộp nhiều
    object liền kề thành 1 span lớn hơn (khác PyMuPDF `get_text("dict")`,
    vốn tự gộp theo "line") - hầu hết PDF generator đã phát ra 1 lệnh vẽ text
    (`Tj`/`TJ`) cho mỗi đoạn có định dạng đồng nhất, nên trong thực tế mỗi
    text object PDFium trả ra hầu như đã tương đương 1 "span" - đủ dùng cho
    mục đích ban đầu (tìm span khớp vị trí click để lấy font/size/color).
    Việc gộp thêm (nếu cần chính xác hơn cho các file PDF generator tách
    text object bất thường) để lại làm sau, dựa trên test đối chiếu thật
    (xem ROADMAP) chứ không đoán trước."""
    textpage = page.get_textpage()
    try:
        spans: list[Span] = []
        for textobj in _iter_text_objects(page, textpage):
            span = _span_from_object(textobj)
            if span is not None:
                spans.append(span)
        return spans
    finally:
        textpage.close()


def _inter_area(a: tuple, b: tuple) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _center_distance(a: tuple, b: tuple) -> float:
    ax, ay = (a[0] + a[2]) / 2.0, (a[1] + a[3]) / 2.0
    bx, by = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def find_span_at(spans: list[Span], pick_box: tuple[float, float, float, float]) -> Span | None:
    """Tìm span khớp nhất với `pick_box` (toạ độ PDF gốc) - cùng logic chấm
    điểm (overlap trước, khoảng cách tâm sau) mà edit.py::_find_pdf_span bản
    PyMuPDF cũ đang dùng, cổng nguyên vẹn thuật toán chọn nhưng đổi nguồn dữ
    liệu span. Trả None nếu không có span nào đủ gần (không overlap VÀ cách
    xa hơn 5pt - dung sai cho lệch nhỏ giữa rect text-layer pdf.js và bbox
    span thật)."""
    best: Span | None = None
    best_score: tuple[float, float] | None = None
    best_overlap = 0.0
    for span in spans:
        overlap = _inter_area(pick_box, span.box)
        distance = _center_distance(pick_box, span.box)
        score = (-overlap, distance)
        if best_score is None or score < best_score:
            best = span
            best_score = score
            best_overlap = overlap
    if best is not None and best_overlap <= 0.0:
        bb = best.box
        gap_x = max(0.0, max(pick_box[0], bb[0]) - min(pick_box[2], bb[2]))
        gap_y = max(0.0, max(pick_box[1], bb[1]) - min(pick_box[3], bb[3]))
        if max(gap_x, gap_y) > 5.0:
            return None
    return best


def page_is_scan_text(page) -> bool:
    """True nếu text trên trang chủ yếu là lớp OCR vô hình (font
    "glyphless" do Tesseract textonly_pdf sinh ra, xem packages/ocr/engine.py)
    VÀ trang có ít nhất 1 ảnh - tức trang là ảnh scan, chữ nhìn thấy đều là
    pixel của ảnh, không phải PDF text thật. Cổng lại logic
    edit.py::_page_is_scan_text, đổi nguồn dữ liệu sang pypdfium2."""
    import pypdfium2 as pdfium

    ocr_count = 0
    total_count = 0
    has_image = False
    textpage = page.get_textpage()
    try:
        for obj in page.get_objects():
            if isinstance(obj, pdfium.PdfImage):
                has_image = True
            elif isinstance(obj, pdfium.PdfTextObj):
                obj.textpage = textpage
                try:
                    text = obj.extract()
                except Exception:
                    continue
                if not text or not text.strip():
                    continue
                total_count += 1
                font_family, _, _ = _font_info(obj)
                if _OCR_PLACEHOLDER_MARKER in font_family.lower():
                    ocr_count += 1
    finally:
        textpage.close()

    if total_count == 0:
        return False
    # Đa số span là OCR vô hình (không đòi 100% - vài span thật lẫn vào,
    # vd số trang đóng dấu/header, không được làm hỏng kết luận cả trang).
    if ocr_count / total_count < 0.6:
        return False
    return has_image
