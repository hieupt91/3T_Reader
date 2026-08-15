"""B52 overload fix: office/LibreOffice convert phải chạy trên thread nền
qua _run_conversion_with_progress, không chặn thẳng main thread Qt (xem
comment trong app/actions/document_converter.py::_ConversionThread và
packages/document_core/office_com.py đầu file)."""
import os
import sys

import pytest

sys.path.insert(0, ".")

from packages.qt_compat.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_run_conversion_with_progress_returns_func_result(qapp):
    from app.actions.document_converter import _run_conversion_with_progress

    window = QWidget()
    calls = []

    def fake_convert(a, b):
        calls.append((a, b))
        return "C:/fake/output.pdf"

    result = _run_conversion_with_progress(window, "Đang xử lý...", fake_convert, "x", "y")

    assert result == "C:/fake/output.pdf"
    assert calls == [("x", "y")]


def test_run_conversion_with_progress_propagates_exception(qapp):
    from app.actions.document_converter import _run_conversion_with_progress

    window = QWidget()

    def failing_convert():
        raise ValueError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _run_conversion_with_progress(window, "Đang xử lý...", failing_convert)


def test_run_conversion_with_progress_does_not_block_caller_thread(qapp):
    """Xác nhận hàm thật sự chạy trên QThread riêng (khác main thread), chứ
    không phải gọi thẳng - đây chính là bug đã sửa (B52 trước đây gọi COM
    thẳng trên main thread khiến app treo lúc mở Word/Excel lần đầu)."""
    import threading

    from app.actions.document_converter import _run_conversion_with_progress

    window = QWidget()
    seen_thread_name = {}

    def fake_convert():
        seen_thread_name["name"] = threading.current_thread().name
        return "ok"

    _run_conversion_with_progress(window, "Đang xử lý...", fake_convert)

    assert seen_thread_name["name"] != threading.current_thread().name


_requires_office = pytest.mark.skipif(
    sys.platform != "win32", reason="COM Automation chỉ có trên Windows"
)
if sys.platform == "win32":
    from packages.document_core.office_com import detect_office_suite
    _requires_office = pytest.mark.skipif(
        detect_office_suite() is None, reason="Không phát hiện MS Office/WPS đã cài trên máy này"
    )


@_requires_office
def test_convert_office_to_pdf_end_to_end_via_background_thread(qapp, tmp_path):
    """Kiểm tra convert_office_to_pdf() (hàm thật đã refactor sang chạy nền)
    vẫn convert đúng 1 file .docx thật sang PDF hợp lệ đầu-cuối, không chỉ
    unit test helper threading riêng lẻ ở trên."""
    import docx

    from app.actions.document_converter import convert_office_to_pdf

    src = tmp_path / "b52_threaded_test.docx"
    doc = docx.Document()
    doc.add_paragraph("B52 threaded conversion end-to-end test.")
    doc.save(str(src))

    window = QWidget()
    result = convert_office_to_pdf(window, str(src))

    assert result
    assert os.path.exists(result)
    assert os.path.getsize(result) > 100
