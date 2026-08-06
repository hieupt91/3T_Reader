import inspect

from app.actions import document_converter


def test_download_thread_uses_cooperative_cancel_flag():
    """QThread.terminate() giết thread ngay tại lệnh đang chạy (kể cả giữa
    network I/O) - có thể để lại state hỏng hoặc crash tiến trình. run() phải
    tự kiểm tra cờ _cancelled giữa các chunk và tự thoát sạch."""
    run_src = inspect.getsource(document_converter.DownloadThread.run)
    assert "if self._cancelled:" in run_src

    cancel_src = inspect.getsource(document_converter.DownloadThread.cancel)
    assert "self._cancelled = True" in cancel_src


def test_no_terminate_call_left_anywhere_in_module():
    """2 luồng tải riêng biệt trong file này (LibreOffice, iTaxViewer) từng
    dùng chung 1 lỗi terminate() - đảm bảo cả 2 đã được sửa, không sót chỗ
    nào."""
    src = inspect.getsource(document_converter)
    assert "thread.terminate()" not in src


def test_libreoffice_download_cancel_path_uses_cancel_not_terminate():
    src = inspect.getsource(document_converter.download_and_extract_libreoffice)
    assert "thread.cancel()" in src
    assert "cancelled = True" in src


def test_itaxviewer_download_cancel_path_uses_cancel_not_terminate():
    src = inspect.getsource(document_converter.handle_xml_itax)
    assert "thread.cancel()" in src
    assert "cancelled = True" in src
