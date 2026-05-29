import os
import tempfile
import uuid
import re

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


def _normalize_text(value: str) -> str:
    return " ".join((value or "").replace("\u00a0", " ").split())


def _tokenize_text(value: str) -> list[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []
    return [part for part in re.split(r"\s+", normalized) if part]


def _extract_words_with_pdfplumber(pdf_path: str, page_no: int) -> list[dict]:
    try:
        import pdfplumber
    except ImportError:
        return []

    words: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_no - 1]
        page_height = float(getattr(page, "height", 0.0) or 0.0)
        raw_words = page.extract_words(
            use_text_flow=False,
            keep_blank_chars=False,
            extra_attrs=["size"],
        ) or []
        for item in raw_words:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            left = float(item.get("x0", 0.0))
            right = float(item.get("x1", left))
            top_from_top = float(item.get("top", 0.0))
            bottom_from_top = float(item.get("bottom", top_from_top))
            if page_height > 0:
                top = page_height - top_from_top
                bottom = page_height - bottom_from_top
                if bottom > top:
                    bottom, top = top, bottom
            else:
                top = top_from_top
                bottom = bottom_from_top
            words.append({
                "text": text,
                "text_key": text.casefold(),
                "x0": left,
                "x1": right,
                "top": top,
                "bottom": bottom,
                "mid": (top + bottom) / 2.0,
                "size": float(item.get("size") or max(1.0, bottom - top)),
            })
    return words


def _line_rect_from_words(words: list[dict]) -> tuple[float, float, float, float]:
    left = min(float(word["x0"]) for word in words)
    right = max(float(word["x1"]) for word in words)
    bottom = min(float(word["bottom"]) for word in words)
    top = max(float(word["top"]) for word in words)
    return left, bottom, right, top


def _search_words_across_lines(words: list[dict], query_tokens: list[str]) -> list[tuple]:
    if not words or not query_tokens:
        return []

    normalized_words = [str(word["text_key"]) for word in words]
    matches: list[list[dict]] = []
    qlen = len(query_tokens)
    i = 0
    while i <= len(normalized_words) - qlen:
        if normalized_words[i:i + qlen] == query_tokens:
            matches.append(words[i:i + qlen])
            i += qlen
        else:
            i += 1

    rects: list[tuple] = []
    for match in matches:
        line_groups: list[list[dict]] = []
        current_group: list[dict] = []
        current_mid = None
        current_tol = 3.0

        for word in match:
            mid = float(word["mid"])
            tol = max(3.0, float(word["size"]) * 0.7)
            if current_group and current_mid is not None and abs(mid - current_mid) > max(current_tol, tol):
                line_groups.append(current_group)
                current_group = [word]
                current_mid = mid
                current_tol = tol
                continue

            current_group.append(word)
            if current_mid is None:
                current_mid = mid
                current_tol = tol
            else:
                count = len(current_group)
                current_mid = ((current_mid * (count - 1)) + mid) / count
                current_tol = max(current_tol, tol)

        if current_group:
            line_groups.append(current_group)

        for group in line_groups:
            if group:
                rects.append(_line_rect_from_words(group))

    return rects


def _search_text_on_page(pdf_path: str, page_no: int, text: str) -> list[tuple]:
    """Search text with pypdfium2. Returns [(left, bottom, right, top)] in PDF points."""
    import pypdfium2 as pdfium
    query_tokens = [token.casefold() for token in _tokenize_text(text)]
    if not query_tokens:
        return []

    words = _extract_words_with_pdfplumber(pdf_path, page_no)
    if words:
        rects = _search_words_across_lines(words, query_tokens)
        if rects:
            return rects

    rects = []
    doc = pdfium.PdfDocument(pdf_path)
    try:
        page = doc[page_no - 1]
        textpage = page.get_textpage()
        search_text = _normalize_text(text)
        if not search_text:
            return []
        searcher = textpage.search(search_text, match_case=False, match_whole_word=False)
        while True:
            res = searcher.get_next()
            if res is None:
                break
            # pypdfium2 v5+: get_next() returns (start_index, char_count)
            # Use count_rects + get_rect to get bounding boxes
            start, count = res
            n = textpage.count_rects(start, count)
            for i in range(n):
                r = textpage.get_rect(i)
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
        elif subtype == "Text":
            d["/Name"] = pikepdf.Name("/Note")
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
    """Thêm ghi chú (sticky note) — bám theo text đang chọn hoặc dòng đầu trang."""
    wv = window._get_webview()

    def _apply(sel_text):
        sel_text = (sel_text or "").strip()

        content, ok = QInputDialog.getMultiLineText(
            window, "Thêm ghi chú",
            f"Ghi chú cho: \"{sel_text[:60]}…\"" if sel_text else "Nội dung ghi chú:",
        )
        if not ok or not content.strip():
            return
        _do_add_comment(window, content.strip(), sel_text)

    if wv:
        wv.page().runJavaScript("window.getSelection().toString()", _apply)
    else:
        _apply("")


def _do_add_comment(window, content: str, anchor_text: str = ""):
    path = window.current_path
    page_no = _get_current_page(window)
    try:
        with pikepdf.open(path) as pdf:
            page = pdf.pages[page_no - 1]
            mb = page.mediabox
            page_w = float(mb[2]) - float(mb[0])
            page_h = float(mb[3]) - float(mb[1])

            icon_w = 18.0
            icon_h = 18.0
            margin = 8.0

            # Vị trí mặc định: góc trên phải, sát lề nhưng vẫn nằm trong trang
            note_x = max(margin, page_w - icon_w - margin)
            note_y = max(icon_h + margin, page_h - margin)

            # Nếu có text được chọn, đặt note bên phải dòng đầu tiên của text đó
            if anchor_text:
                rects = _search_text_on_page(path, page_no, anchor_text)
                if rects:
                    first = rects[0]  # (left, bottom, right, top)
                    note_x = min(page_w - icon_w - margin, max(margin, first[2] + 6))
                    note_y = min(page_h - margin, max(icon_h + margin, first[3] + 6))

            x0, y0 = note_x, max(0.0, note_y - icon_h)
            x1, y1 = note_x + icon_w, note_y

            _add_pdf_annotation(pdf, page_no - 1, "Text",
                                 [(x0, y0, x1, y1)], [1.0, 1.0, 0.0],
                                 content=content)
            _save_pikepdf_reload(window, pdf)
        if hasattr(window, "status"):
            window.status.showMessage("Đã thêm ghi chú vào trang", 3000)
    except Exception as e:
        show_warning(window, "Lỗi thêm ghi chú", str(e))
