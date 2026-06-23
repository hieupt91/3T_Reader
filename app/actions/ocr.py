"""OCR actions - recognize text from PDF pages."""
from __future__ import annotations

from app.language_manager import get_selected_language, get_translation


def _ocr_installer_url() -> str:
    import os
    try:
        from app.config import OCR_TESSERACT_INSTALLER_URL
    except Exception:
        OCR_TESSERACT_INSTALLER_URL = ""
    return (
        os.environ.get("OCR_TESSERACT_INSTALLER_URL")
        or OCR_TESSERACT_INSTALLER_URL
        or "https://github.com/UB-Mannheim/tesseract/wiki"
    )


def _ocr_tessdata_url(lang_code: str) -> str:
    import os
    try:
        from app.config import OCR_TESSDATA_BASE_URL
    except Exception:
        OCR_TESSDATA_BASE_URL = ""
    base = os.environ.get("OCR_TESSDATA_BASE_URL") or OCR_TESSDATA_BASE_URL
    if base:
        return f"{base.rstrip('/')}/{lang_code}.traineddata"
    return f"https://github.com/tesseract-ocr/tessdata/raw/main/{lang_code}.traineddata"


def _download_tessdata_lang(window, lang_code: str, tessdata_dir: str) -> bool:
    import os
    import urllib.request

    from app.dialogs import show_info, show_warning

    if not tessdata_dir:
        show_warning(window, "Không tìm thấy tessdata", "Không xác định được thư mục tessdata của Tesseract.")
        return False

    try:
        os.makedirs(tessdata_dir, exist_ok=True)
        url = _ocr_tessdata_url(lang_code)
        dest = os.path.join(tessdata_dir, f"{lang_code}.traineddata")
        show_info(window, "Đang tải gói OCR", f"3T Reader sẽ tải gói OCR '{lang_code}' vào:\n{tessdata_dir}")
        urllib.request.urlretrieve(url, dest)
        show_info(window, "Đã cài gói OCR", "Đã tải xong gói ngôn ngữ OCR. Hãy chạy lại OCR.")
        return True
    except Exception as exc:
        show_warning(
            window,
            "Không tải được gói OCR",
            f"Không tải được {lang_code}.traineddata.\n\nChi tiết: {exc}\n\n"
            "Bạn có thể tải thủ công từ https://github.com/tesseract-ocr/tessdata",
        )
        return False


def _download_and_launch_ocr_installer(window, url: str) -> None:
    import os
    import subprocess
    import tempfile
    import urllib.request

    from app.dialogs import show_info, show_warning

    if not url.lower().endswith((".exe", ".msi")):
        from packages.qt_compat.QtCore import QUrl
        from packages.qt_compat.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(url))
        return

    try:
        suffix = ".msi" if url.lower().endswith(".msi") else ".exe"
        dest = os.path.join(tempfile.gettempdir(), f"3TReader_Tesseract_OCR{suffix}")
        show_info(window, "Đang tải OCR", "3T Reader sẽ tải bộ cài Tesseract OCR rồi mở trình cài đặt.")
        urllib.request.urlretrieve(url, dest)
        if suffix == ".msi":
            subprocess.Popen(["msiexec", "/i", dest])
        else:
            subprocess.Popen([dest])
    except Exception as exc:
        show_warning(
            window,
            "Không tải được OCR",
            f"Không tải/cài được Tesseract tự động.\n\nChi tiết: {exc}\n\nBạn vẫn có thể mở trang tải và cài thủ công.",
        )


def _show_ocr_install_prompt(window, title: str, message: str, url: str | None = None) -> None:
    from packages.qt_compat.QtCore import QUrl
    from packages.qt_compat.QtGui import QDesktopServices
    from packages.qt_compat.QtWidgets import QApplication, QMessageBox

    lang = get_selected_language()
    _t = lambda key, fallback: get_translation(lang, key, fallback)

    box = QMessageBox(window)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(_t("ocr.install.title", title))
    box.setText(message)
    box.setTextFormat(box.textFormat())
    box.setInformativeText(
        "Sau khi cài xong, khởi động lại 3T Reader.\n"
        "Bản cài mới đã có thể dùng Tesseract đi kèm nếu bundle OCR có sẵn.\n"
        "Nếu đã cài Tesseract ở vị trí khác, đặt OCR_TESSERACT_CMD trỏ tới file tesseract.exe."
    )

    open_btn = None
    copy_btn = None
    auto_btn = None
    if url:
        auto_btn = box.addButton(_t("ocr.install.auto", "Tải và cài tự động"), QMessageBox.ButtonRole.ActionRole)
        open_btn = box.addButton(_t("ocr.install.open", "Mở trang tải"), QMessageBox.ButtonRole.ActionRole)
        copy_btn = box.addButton(_t("ocr.install.copy", "Sao chép link"), QMessageBox.ButtonRole.ActionRole)
    box.addButton(_t("dialog.cancel", "Đóng"), QMessageBox.ButtonRole.RejectRole)

    box.exec()

    clicked = box.clickedButton()
    if url and clicked == auto_btn:
        _download_and_launch_ocr_installer(window, url)
    elif url and clicked == open_btn:
        QDesktopServices.openUrl(QUrl(url))
    elif url and clicked == copy_btn:
        QApplication.clipboard().setText(url)


def _show_missing_vietnamese_prompt(window, langs: list[str], tessdata_dir: str) -> None:
    from packages.qt_compat.QtCore import QUrl
    from packages.qt_compat.QtGui import QDesktopServices
    from packages.qt_compat.QtWidgets import QApplication, QMessageBox

    box = QMessageBox(window)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Chưa có gói tiếng Việt")
    box.setText(
        "Tesseract đã được cài nhưng chưa có gói ngôn ngữ tiếng Việt.\n\n"
        f"Ngôn ngữ đã có: {', '.join(langs) or '(không có)'}"
    )
    box.setInformativeText(
        "App vẫn có thể chạy OCR bằng tiếng Anh, nhưng tài liệu tiếng Việt sẽ nhận dạng kém.\n"
        "Bấm tải gói tiếng Việt để cài vie.traineddata vào thư mục tessdata."
    )
    install_btn = box.addButton("Tải gói tiếng Việt", QMessageBox.ButtonRole.ActionRole)
    open_btn = box.addButton("Mở trang tessdata", QMessageBox.ButtonRole.ActionRole)
    copy_btn = box.addButton("Sao chép link", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
    box.exec()

    clicked = box.clickedButton()
    url = _ocr_tessdata_url("vie")
    if clicked == install_btn:
        _download_tessdata_lang(window, "vie", tessdata_dir)
    elif clicked == open_btn:
        QDesktopServices.openUrl(QUrl("https://github.com/tesseract-ocr/tessdata"))
    elif clicked == copy_btn:
        QApplication.clipboard().setText(url)


def _check_ocr_available(window) -> bool:
    """Validate OCR runtime and show a helpful message if missing."""
    import sys

    try:
        from packages.ocr.engine import is_available, has_vietnamese, get_installed_langs, runtime_status
    except ImportError:
        from app.dialogs import show_warning
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)
        show_warning(
            window,
            _t("ocr.install.title", "Cần cài thêm thư viện OCR"),
            "Thiếu thư viện pytesseract.\n\n"
            "Cài bằng lệnh:\n"
            "  pip install pytesseract\n\n"
            "Sau đó cài Tesseract OCR hoặc dùng bản portable đi kèm bộ cài.",
        )
        return False

    if not is_available():
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)
        if sys.platform == "win32":
            _show_ocr_install_prompt(
                window,
                _t("ocr.install.title", "Cần cài thêm Tesseract OCR"),
                "OCR cần Tesseract để hoạt động.\n\n"
                "Bạn có thể:\n"
                "  - dùng bản portable/bundled đi kèm bộ cài, hoặc\n"
                "  - cài Tesseract theo bộ cài Windows thông thường.\n\n"
                "Đường dẫn mặc định thường là:\n"
                "  C:\\Program Files\\Tesseract-OCR\\tesseract.exe\n\n"
                "Nếu bạn đã cài ở chỗ khác, hãy đặt biến môi trường OCR_TESSERACT_CMD "
                "trỏ tới file tesseract.exe.\n\n"
                "Nếu chưa có Tesseract, bấm 'Tải và cài tự động' hoặc mở trang tải.\n\n"
                "Sau khi cài xong, khởi động lại 3T Reader.",
                url=_ocr_installer_url(),
            )
        else:
            _show_ocr_install_prompt(
                window,
                _t("ocr.install.title", "Cần cài thêm Tesseract OCR"),
                "OCR cần Tesseract để hoạt động.\n\n"
                "macOS:  brew install tesseract tesseract-lang\n"
                "Linux:  sudo apt install tesseract-ocr tesseract-ocr-vie\n\n"
                "Nếu đã cài ở vị trí khác, đặt OCR_TESSERACT_CMD trỏ tới tesseract.\n\n"
                "Sau khi cài xong, khởi động lại 3T Reader.",
            )
        return False

    if not has_vietnamese():
        langs = get_installed_langs()
        status = runtime_status()
        from app.dialogs import show_warning
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)

        if sys.platform == "win32":
            _show_missing_vietnamese_prompt(window, langs, status.tessdata_dir)
        else:
            show_warning(
                window,
                _t("ocr.install.vi_missing", "Chưa có gói tiếng Việt"),
                "Tesseract đã được cài nhưng chưa có gói ngôn ngữ tiếng Việt.\n\n"
                "macOS:  brew install tesseract-lang\n"
                "Linux:  sudo apt install tesseract-ocr-vie\n\n"
                f"Ngôn ngữ đã có: {', '.join(langs) or '(không có)'}",
            )
    return True


def _raise_active_ocr_dialog(window) -> bool:
    existing = getattr(window, "_active_ocr_dialog", None)
    if existing is None:
        return False
    try:
        running = bool(getattr(existing, "is_running", lambda: False)())
        if hasattr(existing, "isVisible") and not existing.isVisible() and not running:
            window._active_ocr_dialog = None
            return False
        if hasattr(existing, "show"):
            existing.show()
        existing.raise_()
        existing.activateWindow()
        window.status.showMessage("OCR dang chay, vui long cho hoac dong cua so OCR hien tai.", 4000)
        return True
    except RuntimeError:
        window._active_ocr_dialog = None
        return False


def _show_ocr_dialog(window, pdf_path: str, pages: list[int], current_page: int, *, high_quality: bool):
    if _raise_active_ocr_dialog(window):
        return None

    from app.ocr_dialog import OCRDialog

    dlg = OCRDialog(
        window,
        pdf_path,
        pages=pages,
        current_page=current_page,
        high_quality=high_quality,
        modal=False,
    )

    def _clear_active(*_args):
        if getattr(window, "_active_ocr_dialog", None) is dlg:
            window._active_ocr_dialog = None

    dlg.finished.connect(_clear_active)
    dlg.destroyed.connect(_clear_active)
    window._active_ocr_dialog = dlg
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()


    return dlg


def _legacy_ocr_current_page(window):
    """OCR current page."""
    existing = getattr(window, "_active_ocr_dialog", None)
    if existing is not None:
        try:
            existing.raise_()
            existing.activateWindow()
            window.status.showMessage("OCR đang chạy, vui lòng chờ hoặc đóng cửa sổ OCR hiện tại.", 4000)
            return
        except RuntimeError:
            window._active_ocr_dialog = None

    if not _check_ocr_available(window):
        return

    state = window._state_or_global()
    pdf_path = state.get("source_path") or state.get("display_path")
    if not pdf_path:
        from app.dialogs import show_warning
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)
        show_warning(window, _t("search.no_file", "Chưa mở tài liệu"), _t("search.no_file", "Vui lòng mở một file PDF trước."))
        return

    viewer = window.viewer
    current_page = 1
    if viewer:
        current_page = getattr(viewer, "_current_page", 1) or 1

    from app.ocr_dialog import OCRDialog
    dlg = OCRDialog(window, pdf_path, pages=[current_page], current_page=current_page, high_quality=False, modal=True)
    window._active_ocr_dialog = dlg
    try:
        dlg.exec()
    finally:
        window._active_ocr_dialog = None
    try:
        from packages.audit import log_action, ACT_OCR
        log_action(ACT_OCR, pdf_path, f"page={current_page}")
    except Exception:
        pass


def _legacy_ocr_full_document(window):
    """OCR whole document (enterprise flow)."""
    existing = getattr(window, "_active_ocr_dialog", None)
    if existing is not None:
        try:
            existing.raise_()
            existing.activateWindow()
            window.status.showMessage("OCR đang chạy, vui lòng chờ hoặc đóng cửa sổ OCR hiện tại.", 4000)
            return
        except RuntimeError:
            window._active_ocr_dialog = None

    if not _check_ocr_available(window):
        return

    state = window._state_or_global()
    pdf_path = state.get("source_path") or state.get("display_path")
    if not pdf_path:
        from app.dialogs import show_warning
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)
        show_warning(window, _t("search.no_file", "Chưa mở tài liệu"), _t("search.no_file", "Vui lòng mở một file PDF trước."))
        return

    try:
        from packages.pdf_engine import get_pdf_engine
        doc = get_pdf_engine().open(pdf_path)
        total = doc.page_count
        doc.close()
    except Exception:
        total = 1

    if total > 50:
        from packages.qt_compat.QtWidgets import QMessageBox
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)
        reply = QMessageBox.question(
            window,
            _t("ocr.install.long_doc", "Tài liệu dài"),
            _t("ocr.install.long_doc_text", f"Tài liệu có {total} trang. OCR toàn bộ có thể mất vài phút.\n\nTiếp tục?").format(total=total),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

    pages = list(range(1, total + 1))
    viewer = window.viewer
    current_page = getattr(viewer, "_current_page", 1) if viewer else 1

    from app.ocr_dialog import OCRDialog
    dlg = OCRDialog(window, pdf_path, pages=pages, current_page=current_page, high_quality=True, modal=False)
    dlg.finished.connect(lambda _code: setattr(window, "_active_ocr_dialog", None))
    window._active_ocr_dialog = dlg
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()


# Effective OCR handlers. They intentionally override the legacy modal
# definitions above so both OCR buttons use one non-modal dialog instance.
def ocr_current_page(window):
    """OCR current page without opening a modal overlay."""
    from app.license_dialog import require_plan
    if not require_plan(window, "Nhận dạng chữ (OCR) trang hiện tại", ["personal", "enterprise"]):
        return

    if _raise_active_ocr_dialog(window):
        return

    if not _check_ocr_available(window):
        return

    state = window._state_or_global()
    pdf_path = state.get("source_path") or state.get("display_path")
    if not pdf_path:
        from app.dialogs import show_warning
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)
        show_warning(window, _t("search.no_file", "Chua mo tai lieu"), _t("search.no_file", "Vui long mo mot file PDF truoc."))
        return

    viewer = window.viewer
    current_page = 1
    if viewer:
        current_page = getattr(viewer, "_current_page", 1) or 1

    _show_ocr_dialog(
        window,
        pdf_path,
        pages=[current_page],
        current_page=current_page,
        high_quality=False,
    )
    try:
        from packages.audit import log_action, ACT_OCR
        log_action(ACT_OCR, pdf_path, f"page={current_page}")
    except Exception:
        pass


def ocr_full_document(window):
    """OCR whole document without stacking modal overlays."""
    from app.license_dialog import require_plan
    if not require_plan(window, "Nhận dạng chữ (OCR) toàn bộ tài liệu", ["enterprise"]):
        return

    if _raise_active_ocr_dialog(window):
        return

    if not _check_ocr_available(window):
        return

    state = window._state_or_global()
    pdf_path = state.get("source_path") or state.get("display_path")
    if not pdf_path:
        from app.dialogs import show_warning
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)
        show_warning(window, _t("search.no_file", "Chua mo tai lieu"), _t("search.no_file", "Vui long mo mot file PDF truoc."))
        return

    try:
        from packages.pdf_engine import get_pdf_engine
        doc = get_pdf_engine().open(pdf_path)
        total = doc.page_count
        doc.close()
    except Exception:
        total = 1

    if total > 50:
        from packages.qt_compat.QtWidgets import QMessageBox
        lang = get_selected_language()
        _t = lambda key, fallback: get_translation(lang, key, fallback)
        reply = QMessageBox.question(
            window,
            _t("ocr.install.long_doc", "Tai lieu dai"),
            _t(
                "ocr.install.long_doc_text",
                f"Tai lieu co {total} trang. OCR toan bo co the mat vai phut.\n\nTiep tuc?",
            ).format(total=total),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

    pages = list(range(1, total + 1))
    viewer = window.viewer
    current_page = getattr(viewer, "_current_page", 1) if viewer else 1

    _show_ocr_dialog(
        window,
        pdf_path,
        pages=pages,
        current_page=current_page,
        high_quality=True,
    )
