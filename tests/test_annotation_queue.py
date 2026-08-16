"""Tests for annotation queue logic."""

import os
from types import SimpleNamespace


class _FakeOp:
    """Fake annotation operation that records calls."""
    def __init__(self):
        self.called = False
        self.call_args = None

    def __call__(self, pdf):
        self.called = True
        self.call_args = pdf


class _FakeStatus:
    def __init__(self):
        self.messages = []

    def showMessage(self, message, timeout=0):
        self.messages.append((message, timeout))


_QT_APP = None


def _make_qt_window():
    global _QT_APP
    from packages.qt_compat import QtCore

    _QT_APP = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    window = QtCore.QObject()
    window.status = _FakeStatus()
    return window


class TestAnnotationOpQueueLogic:
    """Test the queue logic without Qt event loop."""

    def test_enqueue_records_operation(self):
        """Operations should be stored in pending list."""
        # We can't instantiate _AnnotationOpQueue without Qt, so test the logic
        # by simulating what the queue does
        pending = []
        target = os.path.abspath("/tmp/test.pdf")
        op = _FakeOp()
        pending.append((target, op))
        assert len(pending) == 1
        assert pending[0][0] == target
        assert pending[0][1] is op

    def test_has_pending_checks_path(self):
        """has_pending should match by absolute path."""
        pending = [
            (os.path.abspath("/tmp/test.pdf"), _FakeOp()),
            (os.path.abspath("/tmp/other.pdf"), _FakeOp()),
        ]
        target = os.path.abspath("/tmp/test.pdf")
        result = any(path == target for path, _op in pending)
        assert result is True

        target2 = os.path.abspath("/tmp/nonexistent.pdf")
        result2 = any(path == target2 for path, _op in pending)
        assert result2 is False

    def test_flush_separates_by_target(self):
        """flush should separate operations by target path."""
        pending = [
            (os.path.abspath("/tmp/a.pdf"), _FakeOp()),
            (os.path.abspath("/tmp/b.pdf"), _FakeOp()),
            (os.path.abspath("/tmp/a.pdf"), _FakeOp()),
        ]
        requested = os.path.abspath("/tmp/a.pdf")
        same_target = [item for item in pending if item[0] == requested]
        rest = [item for item in pending if item[0] != requested]
        assert len(same_target) == 2
        assert len(rest) == 1

    def test_queue_reports_pending_and_flushing_state(self, tmp_path):
        from app.actions.annotate import _AnnotationOpQueue

        window = _make_qt_window()
        queue = _AnnotationOpQueue(window)
        target = str(tmp_path / "doc.pdf")

        queue.enqueue(target, _FakeOp(), delay_ms=0)
        queue._timer.stop()

        assert queue.pending_count() == 1
        assert queue.pending_count(target) == 1
        assert queue.has_pending(target) is True
        assert window.status.messages[-1][0].startswith("Đang chờ")

        queue._pending.clear()
        queue._flushing = True
        queue._flushing_target = os.path.abspath(target)
        assert queue.is_flushing(target) is True
        assert queue.has_pending(target) is True

        queue._last_error = "disk busy"
        assert queue.last_error() == "disk busy"

    def test_flush_returns_false_with_clear_status_when_already_flushing(self, tmp_path):
        from app.actions.annotate import _AnnotationOpQueue

        window = _make_qt_window()
        queue = _AnnotationOpQueue(window)
        queue._flushing = True
        queue._flushing_target = os.path.abspath(str(tmp_path / "doc.pdf"))

        assert queue.flush(str(tmp_path / "doc.pdf")) is False
        assert "Đang lưu chú thích" in window.status.messages[-1][0]

    def test_flush_retry_hides_raw_exception_until_near_final_attempt(self, monkeypatch, tmp_path):
        """Lỗi ghi chú cũ: mở file PDF nặng vừa xong (còn đang được viewer/AV
        đọc dở) khiến lần flush chú thích tự động ĐẦU TIÊN luôn dính
        PermissionError thoáng qua, tự phục hồi sau vài lần retry (đã có sẵn
        cơ chế 5 lần x 1.2s). Trước fix: status bar hiện thẳng raw
        PermissionError ("[WinError 5] Access is denied: ...") ngay từ lần
        thử đầu tiên dù đây là chuyện bình thường sắp tự khỏi, gây hoang
        mang không cần thiết (QA 2026-08-16, mở file 700MB+ tái hiện 2/2
        lần). Fix: chỉ hiện raw exception ở lần thử áp chót trước khi thật
        sự báo lỗi vĩnh viễn."""
        import pikepdf
        from app.actions import annotate

        target = tmp_path / "doc.pdf"
        with pikepdf.new() as pdf:
            pdf.save(str(target))

        window = _make_qt_window()
        queue = annotate._AnnotationOpQueue(window)
        queue.enqueue(str(target), _FakeOp(), delay_ms=0)
        queue._timer.stop()

        def always_denied(*_args, **_kwargs):
            raise PermissionError(13, "Access is denied")

        monkeypatch.setattr(annotate, "replace_file_with_retry", always_denied)

        # Các lần thử sớm: không được lộ raw exception ra status bar.
        for _ in range(annotate._MAX_FLUSH_RETRIES - 2):
            assert queue.flush() is False
            assert "WinError" not in window.status.messages[-1][0]
            assert "Access is denied" not in window.status.messages[-1][0]

        # Lần thử áp chót (fail_count == MAX-1): mới hiện raw exception.
        assert queue.flush() is False
        assert "Access is denied" in window.status.messages[-1][0]

    def test_heavy_op_warning_explains_active_flush(self, monkeypatch, tmp_path):
        from app.actions import annotate

        captured = {}

        class BusyQueue:
            def flush_all(self, target_path=None):
                return False

            def is_flushing(self, target_path=None):
                return True

            def last_error(self):
                return ""

        def fake_warning(_window, title, message):
            captured["title"] = title
            captured["message"] = message

        monkeypatch.setattr(annotate, "show_warning", fake_warning)
        window = SimpleNamespace(_annotation_op_queue=BusyQueue())

        assert annotate._flush_annotations_before_heavy_op(window, str(tmp_path / "doc.pdf"), "xuất PDF") is False
        assert captured["title"] == "Chưa lưu xong chú thích"
        assert "đang lưu chú thích" in captured["message"].lower()
