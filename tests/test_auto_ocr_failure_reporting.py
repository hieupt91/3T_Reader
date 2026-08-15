import inspect

from app.actions import auto_ocr


def test_worker_tracks_failed_pages_instead_of_silently_continuing():
    """except Exception: continue trước đây nuốt lỗi im lặng - không trang nào
    biết bị lỗi, user không có cách nào phát hiện tài liệu OCR thiếu."""
    src = inspect.getsource(auto_ocr._AutoOcrWorker.run)
    assert "failed_pages.append(page_num)" in src
    assert "log_action(ACT_OCR, self._pdf_path" in src
    assert "self.finished.emit(self._pdf_path, done_count, failed_pages)" in src


def test_finished_signal_carries_failed_pages_list():
    worker_src = inspect.getsource(auto_ocr._AutoOcrWorker)
    assert "finished = pyqtSignal(str, int, list)" in worker_src

    relay_src = inspect.getsource(auto_ocr._AutoOcrRelay.onFinished)
    assert "failed_pages" in relay_src
    assert "_on_auto_ocr_finished(self._window, path, count, failed_pages)" in relay_src


def test_on_finished_reports_both_success_and_failure_counts():
    src = inspect.getsource(auto_ocr._on_auto_ocr_finished)
    assert "if ocr_page_count > 0:" in src
    assert "if failed_pages:" in src
    assert "Không nhận diện được" in src
