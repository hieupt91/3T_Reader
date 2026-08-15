import inspect

from app.actions import document_converter


def test_itax_installer_wait_has_a_cancel_escape_hatch():
    """_run_itax_installer_silent trước đây setCancelButton(None) + vòng lặp
    while proc.poll() is None không giới hạn thời gian - nếu bộ cài bên thứ
    3 (không do 3T kiểm soát) treo, dialog window-modal khóa cả app vĩnh
    viễn, không có lối thoát nào trong app. Phải có nút Hủy thật, không phải
    None."""
    src = inspect.getsource(document_converter._run_itax_installer_silent)
    assert 'QProgressDialog("Đang cài iTaxViewer ở chế độ nền...", "Hủy", 0, 0, window)' in src
    assert "setCancelButton(None)" not in src


def test_cancelling_the_install_wait_terminates_the_subprocess_and_returns_false():
    src = inspect.getsource(document_converter._run_itax_installer_silent)
    assert "if progress.wasCanceled() and not cancelled:" in src
    assert "proc.terminate()" in src
    assert "if cancelled:\n            return False" in src
