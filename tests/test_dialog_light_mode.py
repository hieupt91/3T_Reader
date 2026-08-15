"""3 dialog (License, OCR, Audit-log) hard-code màu dark-mode không có nhánh
light-mode (H4): bug hiển thị thật, không chỉ trùng lặp code - mở dialog khi
app đang Light mode hiện bảng màu tối lệch tông. So sánh với
app/ai_search_dialog.py::_build_style(dark: bool), vốn đã làm đúng."""

import inspect

from app import audit_log_dialog, license_dialog, ocr_dialog


def _assert_has_dark_and_light_branch(module, func_name="_build_style"):
    fn = getattr(module, func_name)
    dark_css = fn(True)
    light_css = fn(False)
    assert dark_css != light_css
    assert "#16162A" in dark_css or "#12122A" in dark_css  # dark background giữ nguyên
    assert "#F8FAFF" in light_css  # light background mới
    # Không hardcode nữa - phải import is_dark() để quyết định nhánh
    src = inspect.getsource(module)
    assert "from styles.theme import is_dark" in src
    assert "_build_style(is_dark())" in src


def test_license_dialog_has_light_mode_branch():
    _assert_has_dark_and_light_branch(license_dialog)


def test_ocr_dialog_has_light_mode_branch():
    _assert_has_dark_and_light_branch(ocr_dialog)


def test_audit_log_dialog_has_light_mode_branch():
    _assert_has_dark_and_light_branch(audit_log_dialog)


def test_license_dialog_status_label_and_font_combo_are_theme_aware_too():
    """Không chỉ setStyleSheet() tổng của dialog - các override trực tiếp lên
    từng widget con (status label, font combo) cũng phải theo theme, nếu
    không sẽ đè lên style đúng đã set ở dialog cha."""
    src = inspect.getsource(license_dialog)
    assert "is_dark()" in inspect.getsource(license_dialog.LicenseActivationDialog._set_status)


def test_ocr_dialog_font_combo_and_status_labels_are_theme_aware():
    src = inspect.getsource(ocr_dialog)
    assert src.count("is_dark()") >= 4  # setStyleSheet chính + font_combo + 2 label trạng thái
