import os
import tempfile
import uuid

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


def _save_and_reload(window, doc, *, keep_page: bool = True):
    """Save fitz doc to temp file, close it, and reload viewer."""
    tmp_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(tmp_dir, exist_ok=True)
    out_path = os.path.join(tmp_dir, f"op_{uuid.uuid4().hex[:8]}.pdf")
    doc.save(out_path)
    doc.close()
    page = _get_current_page(window) if keep_page else 1
    window.current_path = out_path
    window.viewer.load_pdf(out_path, page=page, zoom="page-width")


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
    import fitz
    path = window.current_path
    page_no = _get_current_page(window)
    doc = None
    try:
        doc = fitz.open(path)
        page = doc[page_no - 1]
        instances = page.search_for(text)
        if not instances:
            doc.close()
            show_warning(window, "Không tìm thấy",
                f'Không tìm thấy "{text}" trên trang {page_no}.')
            return
        for rect in instances:
            annot = page.add_highlight_annot(rect)
            annot.set_colors(stroke=(1.0, 1.0, 0.0))
            annot.update()
        _save_and_reload(window, doc)
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã tô sáng {len(instances)} chỗ: \"{text}\"", 3000)
    except Exception as e:
        try:
            if doc:
                doc.close()
        except Exception:
            pass
        show_warning(window, "Lỗi tô sáng", str(e))


@require_document(show_message=True)
def rotate_page_cw(window):
    """Rotate current page 90° clockwise."""
    _rotate_page(window, 90)


@require_document(show_message=True)
def rotate_page_ccw(window):
    """Rotate current page 90° counter-clockwise."""
    _rotate_page(window, -90)


def _rotate_page(window, degrees: int):
    import fitz
    path = window.current_path
    page_no = _get_current_page(window)
    try:
        doc = fitz.open(path)
        page = doc[page_no - 1]
        page.set_rotation((page.rotation + degrees) % 360)
        _save_and_reload(window, doc)
        if hasattr(window, "status"):
            direction = "thuận chiều kim đồng hồ" if degrees > 0 else "ngược chiều kim đồng hồ"
            window.status.showMessage(f"Đã xoay trang {page_no} {direction}", 2000)
    except Exception as e:
        show_warning(window, "Lỗi xoay trang", str(e))


@require_document(show_message=True)
def delete_current_page(window):
    """Delete the current page from the PDF."""
    import fitz
    path = window.current_path
    page_no = _get_current_page(window)
    try:
        doc = fitz.open(path)
        if doc.page_count <= 1:
            doc.close()
            show_warning(window, "Không thể xóa",
                "Tài liệu chỉ có 1 trang, không thể xóa.")
            return
        reply = QMessageBox.question(
            window, "Xóa trang",
            f"Xóa trang {page_no}/{doc.page_count}? Thao tác không thể hoàn tác.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            doc.close()
            return
        doc.delete_page(page_no - 1)
        _save_and_reload(window, doc, keep_page=False)
        if hasattr(window, "status"):
            window.status.showMessage(f"Đã xóa trang {page_no}", 2000)
    except Exception as e:
        show_warning(window, "Lỗi xóa trang", str(e))


@require_document(show_message=True)
def merge_pdf(window):
    """Append another PDF to the current document."""
    import fitz
    other_path, _ = QFileDialog.getOpenFileName(
        window, "Chọn PDF cần ghép vào cuối", "", "PDF Files (*.pdf)"
    )
    if not other_path:
        return
    path = window.current_path
    try:
        doc = fitz.open(path)
        other = fitz.open(other_path)
        doc.insert_pdf(other)
        other.close()
        _save_and_reload(window, doc, keep_page=False)
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã ghép PDF: {os.path.basename(other_path)}", 3000)
    except Exception as e:
        try:
            doc.close()
        except Exception:
            pass
        show_warning(window, "Lỗi ghép PDF", str(e))


@require_document(show_message=True)
def extract_pages(window):
    """Extract a range of pages to a new PDF file."""
    import fitz
    path = window.current_path
    doc = fitz.open(path)
    total = doc.page_count
    doc.close()

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
        src = fitz.open(path)
        dst = fitz.open()
        for p in pages:
            dst.insert_pdf(src, from_page=p - 1, to_page=p - 1)
        src.close()
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
    """Thêm gạch dưới (underline) hoặc gạch ngang (strikeout) cho text."""
    import fitz
    path = window.current_path
    page_no = _get_current_page(window)
    doc = None
    try:
        doc = fitz.open(path)
        page = doc[page_no - 1]
        instances = page.search_for(text)
        if not instances:
            doc.close()
            show_warning(window, "Không tìm thấy",
                f'Không tìm thấy "{text}" trên trang {page_no}.')
            return
        for rect in instances:
            if annot_type == "underline":
                annot = page.add_underline_annot(rect)
                annot.set_colors(stroke=(0.0, 0.0, 1.0))
            else:
                annot = page.add_strikeout_annot(rect)
                annot.set_colors(stroke=(1.0, 0.0, 0.0))
            annot.update()
        _save_and_reload(window, doc)
        label = "gạch dưới" if annot_type == "underline" else "gạch ngang"
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã {label} {len(instances)} chỗ: \"{text}\"", 3000)
    except Exception as e:
        try:
            if doc:
                doc.close()
        except Exception:
            pass
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


# ── Note / Comment ────────────────────────────────────────────────────────────

@require_document(show_message=True)
def add_comment(window):
    """Thêm ghi chú (sticky note) vào trang hiện tại."""
    import fitz
    content, ok = QInputDialog.getMultiLineText(
        window, "Thêm ghi chú", "Nội dung ghi chú:"
    )
    if not ok or not content.strip():
        return

    path = window.current_path
    page_no = _get_current_page(window)
    doc = None
    try:
        doc = fitz.open(path)
        page = doc[page_no - 1]
        # Đặt note ở góc trên bên phải
        rect = fitz.Rect(page.rect.width - 40, 10, page.rect.width - 10, 40)
        annot = page.add_text_annot(rect.tl, content.strip())
        annot.set_colors(stroke=(1.0, 1.0, 0.0), fill=(1.0, 1.0, 0.8))
        annot.update()
        _save_and_reload(window, doc)
        if hasattr(window, "status"):
            window.status.showMessage("Đã thêm ghi chú vào trang", 3000)
    except Exception as e:
        try:
            if doc:
                doc.close()
        except Exception:
            pass
        show_warning(window, "Lỗi thêm ghi chú", str(e))
