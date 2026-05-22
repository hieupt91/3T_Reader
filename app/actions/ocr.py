"""OCR actions — nhận dạng văn bản tiếng Việt."""
from __future__ import annotations


def _check_ocr_available(window) -> bool:
    """Kiểm tra Tesseract có sẵn không. Nếu không → hướng dẫn cài."""
    import sys
    try:
        from packages.ocr.engine import is_available, has_vietnamese, get_installed_langs
    except ImportError:
        from app.dialogs import show_warning
        show_warning(
            window, "Cần cài thêm thư viện OCR",
            "Thiếu thư viện pytesseract.\n\n"
            "Cài bằng lệnh:\n"
            "  pip install pytesseract\n\n"
            "Sau đó cài Tesseract OCR (xem SETUP_WINDOWS.md)."
        )
        return False

    if not is_available():
        from app.dialogs import show_warning
        if sys.platform == "win32":
            show_warning(
                window, "Cần cài thêm Tesseract OCR",
                "OCR cần Tesseract — một công cụ miễn phí của Google.\n\n"
                "Tải và cài đặt trên Windows:\n"
                "  https://github.com/UB-Mannheim/tesseract/wiki\n\n"
                "Sau khi cài xong, khởi động lại 3T Reader."
            )
        else:
            show_warning(
                window, "Cần cài thêm Tesseract OCR",
                "OCR cần Tesseract — một công cụ miễn phí của Google.\n\n"
                "macOS:  brew install tesseract tesseract-lang\n"
                "Linux:  sudo apt install tesseract-ocr tesseract-ocr-vie\n\n"
                "Sau khi cài xong, khởi động lại 3T Reader."
            )
        return False

    if not has_vietnamese():
        langs = get_installed_langs()
        from app.dialogs import show_warning
        if sys.platform == "win32":
            show_warning(
                window, "Chưa có gói tiếng Việt",
                "Tesseract đã được cài nhưng chưa có gói ngôn ngữ tiếng Việt.\n\n"
                "Tải file vie.traineddata từ:\n"
                "  https://github.com/tesseract-ocr/tessdata\n"
                "Đặt vào thư mục tessdata của Tesseract.\n\n"
                f"Ngôn ngữ đã có: {', '.join(langs) or '(không có)'}\n"
                "(App vẫn chạy OCR bằng tiếng Anh)"
            )
        else:
            show_warning(
                window, "Chưa có gói tiếng Việt",
                "Tesseract đã được cài nhưng chưa có gói ngôn ngữ tiếng Việt.\n\n"
                "macOS:  brew install tesseract-lang\n"
                "Linux:  sudo apt install tesseract-ocr-vie\n\n"
                f"Ngôn ngữ đã có: {', '.join(langs) or '(không có)'}"
            )
    return True  # vẫn cho chạy dù chỉ có eng


def ocr_current_page(window):
    """OCR trang đang xem."""
    if not _check_ocr_available(window):
        return

    state = window._state_or_global()
    pdf_path = state.get("source_path") or state.get("display_path")
    if not pdf_path:
        from app.dialogs import show_warning
        show_warning(window, "Chưa mở tài liệu", "Vui lòng mở một file PDF trước.")
        return

    # Lấy trang hiện tại từ viewer
    viewer = window.viewer
    current_page = 1
    if viewer:
        current_page = getattr(viewer, "_current_page", 1) or 1

    from app.ocr_dialog import OCRDialog
    dlg = OCRDialog(window, pdf_path, pages=[current_page],
                    current_page=current_page, high_quality=False)
    dlg.exec()
    try:
        from packages.audit import log_action, ACT_OCR
        log_action(ACT_OCR, pdf_path, f"page={current_page}")
    except Exception:
        pass


def ocr_full_document(window):
    """OCR toàn bộ tài liệu (Enterprise — chất lượng cao)."""
    if not _check_ocr_available(window):
        return

    state = window._state_or_global()
    pdf_path = state.get("source_path") or state.get("display_path")
    if not pdf_path:
        from app.dialogs import show_warning
        show_warning(window, "Chưa mở tài liệu", "Vui lòng mở một file PDF trước.")
        return

    # Đếm số trang
    try:
        from packages.pdf_engine import get_pdf_engine
        doc = get_pdf_engine().open(pdf_path)
        total = doc.page_count
        doc.close()
    except Exception:
        total = 1

    if total > 50:
        from app.dialogs import show_warning
        from packages.qt_compat.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            window, "Tài liệu dài",
            f"Tài liệu có {total} trang. OCR toàn bộ có thể mất vài phút.\n\nTiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

    pages = list(range(1, total + 1))
    viewer = window.viewer
    current_page = getattr(viewer, "_current_page", 1) if viewer else 1

    from app.ocr_dialog import OCRDialog
    dlg = OCRDialog(window, pdf_path, pages=pages,
                    current_page=current_page, high_quality=True)
    dlg.exec()
