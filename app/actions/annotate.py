import os
import tempfile
import uuid

import pikepdf

from packages.qt_compat.QtWidgets import (
    QInputDialog, QLineEdit, QFileDialog, QMessageBox
)
from app.actions._guard import require_document
from app.dialogs import show_warning, show_info


def _get_current_page(window) -> int:
    try:
        return max(1, window.viewer.get_current_page())
    except Exception:
        return 1


def _save_pikepdf_reload(window, pdf: pikepdf.Pdf, *, keep_page: bool = True):
    """Save pikepdf doc to temp file and reload viewer."""
    tmp_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(tmp_dir, exist_ok=True)
    out_path = os.path.join(tmp_dir, f"op_{uuid.uuid4().hex[:8]}.pdf")
    pdf.save(out_path)
    page = _get_current_page(window) if keep_page else 1
    window.current_path = out_path
    window.viewer.load_pdf(out_path, page=page, zoom="page-width")


def _search_text_on_page(pdf_path: str, page_no: int, text: str) -> list[tuple]:
    """Search text with pypdfium2. Returns [(left, bottom, right, top)] in PDF points."""
    import pypdfium2 as pdfium
    rects = []
    doc = pdfium.PdfDocument(pdf_path)
    try:
        page = doc[page_no - 1]
        textpage = page.get_textpage()
        searcher = textpage.search(text, match_case=False, match_whole_word=False)
        while True:
            res = searcher.get_next()
            if res is None:
                break
            for r in res:
                rects.append((float(r[0]), float(r[1]), float(r[2]), float(r[3])))
    finally:
        doc.close()
    return rects


def _add_pdf_annotation(pdf: pikepdf.Pdf, page_idx: int, subtype: str,
                         rects: list[tuple], color: list[float],
                         content: str = ""):
    """Add Highlight/Underline/StrikeOut/Text annotation using pikepdf."""
    _SUBTYPE = {
        "Highlight":  "/Highlight",
        "Underline":  "/Underline",
        "StrikeOut":  "/StrikeOut",
        "Text":       "/Text",
    }
    page = pdf.pages[page_idx]
    new_annots = []

    for (left, bottom, right, top) in rects:
        d = pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name(_SUBTYPE[subtype]),
            Rect=pikepdf.Array([left, bottom, right, top]),
            C=pikepdf.Array([float(c) for c in color]),
            F=4,
        )
        if subtype in ("Highlight", "Underline", "StrikeOut"):
            d["/QuadPoints"] = pikepdf.Array([
                left, top,    right, top,
                left, bottom, right, bottom,
            ])
        if content:
            d["/Contents"] = pikepdf.String(content)
        if subtype == "Text":
            d["/Open"] = False
        new_annots.append(pdf.make_indirect(d))

    if "/Annots" not in page:
        page["/Annots"] = pikepdf.Array(new_annots)
    else:
        for a in new_annots:
            page["/Annots"].append(a)


# ── Highlight ─────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def highlight_text(window):
    """Highlight selected or searched text on current page."""
    wv = window._get_webview()

    def _apply(sel_text):
        text = (sel_text or "").strip()
        if not text:
            text, ok = QInputDialog.getText(
                window, "Tô sáng văn bản",
                "Nhập từ/cụm từ cần tô sáng:",
                QLineEdit.EchoMode.Normal,
            )
            if not ok or not text.strip():
                return
            text = text.strip()
        _do_highlight(window, text)

    if wv:
        wv.page().runJavaScript("window.getSelection().toString()", _apply)
    else:
        _apply("")


def _do_highlight(window, text: str):
    path = window.current_path
    page_no = _get_current_page(window)
    rects = _search_text_on_page(path, page_no, text)
    if not rects:
        show_warning(window, "Không tìm thấy",
            f'Không tìm thấy "{text}" trên trang {page_no}.')
        return
    try:
        with pikepdf.open(path) as pdf:
            _add_pdf_annotation(pdf, page_no - 1, "Highlight", rects, [1.0, 1.0, 0.0])
            _save_pikepdf_reload(window, pdf)
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã tô sáng {len(rects)} chỗ: \"{text}\"", 3000)
    except Exception as e:
        show_warning(window, "Lỗi tô sáng", str(e))


# ── Rotate ────────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def rotate_page_cw(window):
    """Rotate current page 90° clockwise."""
    _rotate_page(window, 90)


@require_document(show_message=True)
def rotate_page_ccw(window):
    """Rotate current page 90° counter-clockwise."""
    _rotate_page(window, -90)


def _rotate_page(window, degrees: int):
    path = window.current_path
    page_no = _get_current_page(window)
    try:
        with pikepdf.open(path) as pdf:
            page = pdf.pages[page_no - 1]
            try:
                current_rot = int(page["/Rotate"])
            except (KeyError, AttributeError):
                current_rot = 0
            page["/Rotate"] = (current_rot + degrees) % 360
            _save_pikepdf_reload(window, pdf)
        if hasattr(window, "status"):
            direction = "thuận chiều kim đồng hồ" if degrees > 0 else "ngược chiều kim đồng hồ"
            window.status.showMessage(f"Đã xoay trang {page_no} {direction}", 2000)
    except Exception as e:
        show_warning(window, "Lỗi xoay trang", str(e))


# ── Delete page ───────────────────────────────────────────────────────────────

@require_document(show_message=True)
def delete_current_page(window):
    """Delete the current page from the PDF."""
    path = window.current_path
    page_no = _get_current_page(window)
    try:
        with pikepdf.open(path) as pdf:
            total = len(pdf.pages)
            if total <= 1:
                show_warning(window, "Không thể xóa",
                    "Tài liệu chỉ có 1 trang, không thể xóa.")
                return
            reply = QMessageBox.question(
                window, "Xóa trang",
                f"Xóa trang {page_no}/{total}? Thao tác không thể hoàn tác.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            del pdf.pages[page_no - 1]
            _save_pikepdf_reload(window, pdf, keep_page=False)
        if hasattr(window, "status"):
            window.status.showMessage(f"Đã xóa trang {page_no}", 2000)
    except Exception as e:
        show_warning(window, "Lỗi xóa trang", str(e))


# ── Merge PDF ─────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def merge_pdf(window):
    """Append another PDF to the current document."""
    other_path, _ = QFileDialog.getOpenFileName(
        window, "Chọn PDF cần ghép vào cuối", "", "PDF Files (*.pdf)"
    )
    if not other_path:
        return
    path = window.current_path
    try:
        with pikepdf.open(path) as pdf:
            with pikepdf.open(other_path) as other:
                pdf.pages.extend(other.pages)
            _save_pikepdf_reload(window, pdf, keep_page=False)
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã ghép PDF: {os.path.basename(other_path)}", 3000)
    except Exception as e:
        show_warning(window, "Lỗi ghép PDF", str(e))


# ── Extract pages ─────────────────────────────────────────────────────────────

@require_document(show_message=True)
def extract_pages(window):
    """Extract a range of pages to a new PDF file."""
    path = window.current_path
    with pikepdf.open(path) as _tmp:
        total = len(_tmp.pages)

    range_text, ok = QInputDialog.getText(
        window, "Trích xuất trang",
        f"Nhập trang cần trích (VD: 1-3,5,7-9). Tổng: {total} trang:",
        QLineEdit.EchoMode.Normal,
    )
    if not ok or not range_text.strip():
        return

    pages = _parse_page_range(range_text, total)
    if not pages:
        show_warning(window, "Lỗi", "Dải trang không hợp lệ.")
        return

    out_path, _ = QFileDialog.getSaveFileName(
        window, "Lưu trang trích xuất", "", "PDF Files (*.pdf)"
    )
    if not out_path:
        return

    try:
        dst = pikepdf.Pdf.new()
        with pikepdf.open(path) as src:
            for p in pages:
                dst.pages.append(src.pages[p - 1])
        dst.save(out_path)
        dst.close()
        show_info(window, "Trích xuất thành công",
            f"Đã lưu {len(pages)} trang vào:\n{out_path}")
    except Exception as e:
        show_warning(window, "Lỗi trích xuất", str(e))


def _parse_page_range(text: str, max_page: int) -> list[int]:
    pages = []
    for part in text.replace(" ", "").split(","):
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                start, end = max(1, int(a)), min(max_page, int(b))
                if start > end:
                    start, end = end, start
                pages.extend(range(start, end + 1))
            except ValueError:
                pass
        else:
            try:
                p = int(part)
                if 1 <= p <= max_page:
                    pages.append(p)
            except ValueError:
                pass
    return sorted(set(pages))


# ── Underline / Strikeout ─────────────────────────────────────────────────────

def _do_line_annot(window, text: str, annot_type: str):
    path = window.current_path
    page_no = _get_current_page(window)
    rects = _search_text_on_page(path, page_no, text)
    if not rects:
        show_warning(window, "Không tìm thấy",
            f'Không tìm thấy "{text}" trên trang {page_no}.')
        return
    try:
        subtype = "Underline" if annot_type == "underline" else "StrikeOut"
        color   = [0.0, 0.0, 1.0] if annot_type == "underline" else [1.0, 0.0, 0.0]
        with pikepdf.open(path) as pdf:
            _add_pdf_annotation(pdf, page_no - 1, subtype, rects, color)
            _save_pikepdf_reload(window, pdf)
        label = "gạch dưới" if annot_type == "underline" else "gạch ngang"
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã {label} {len(rects)} chỗ: \"{text}\"", 3000)
    except Exception as e:
        show_warning(window, "Lỗi chú thích", str(e))


@require_document(show_message=True)
def underline_text(window):
    """Gạch dưới văn bản được chọn hoặc nhập."""
    wv = window._get_webview()

    def _apply(sel_text):
        text = (sel_text or "").strip()
        if not text:
            text, ok = QInputDialog.getText(
                window, "Gạch dưới văn bản",
                "Nhập từ/cụm từ cần gạch dưới:",
                QLineEdit.EchoMode.Normal,
            )
            if not ok or not text.strip():
                return
            text = text.strip()
        _do_line_annot(window, text, "underline")

    if wv:
        wv.page().runJavaScript("window.getSelection().toString()", _apply)
    else:
        _apply("")


@require_document(show_message=True)
def strikeout_text(window):
    """Gạch ngang (strikeout) văn bản được chọn hoặc nhập."""
    wv = window._get_webview()

    def _apply(sel_text):
        text = (sel_text or "").strip()
        if not text:
            text, ok = QInputDialog.getText(
                window, "Gạch ngang văn bản",
                "Nhập từ/cụm từ cần gạch ngang:",
                QLineEdit.EchoMode.Normal,
            )
            if not ok or not text.strip():
                return
            text = text.strip()
        _do_line_annot(window, text, "strikeout")

    if wv:
        wv.page().runJavaScript("window.getSelection().toString()", _apply)
    else:
        _apply("")


# ── Comment (sticky note) ─────────────────────────────────────────────────────

@require_document(show_message=True)
def add_comment(window):
    """Thêm ghi chú (sticky note) vào trang hiện tại."""
    content, ok = QInputDialog.getMultiLineText(
        window, "Thêm ghi chú", "Nội dung ghi chú:"
    )
    if not ok or not content.strip():
        return

    path = window.current_path
    page_no = _get_current_page(window)
    try:
        with pikepdf.open(path) as pdf:
            page = pdf.pages[page_no - 1]
            mb = page.mediabox
            page_w = float(mb[2]) - float(mb[0])
            page_h = float(mb[3]) - float(mb[1])
            # Đặt note góc trên phải
            x0, y0 = page_w - 40, page_h - 40
            x1, y1 = page_w - 10, page_h - 10
            _add_pdf_annotation(pdf, page_no - 1, "Text",
                                 [(x0, y0, x1, y1)], [1.0, 1.0, 0.0],
                                 content=content.strip())
            _save_pikepdf_reload(window, pdf)
        if hasattr(window, "status"):
            window.status.showMessage("Đã thêm ghi chú vào trang", 3000)
    except Exception as e:
        show_warning(window, "Lỗi thêm ghi chú", str(e))
