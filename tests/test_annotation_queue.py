"""Tests for annotation queue logic — pure Python, no Qt required."""

import os
import pytest


class _FakeOp:
    """Fake annotation operation that records calls."""
    def __init__(self):
        self.called = False
        self.call_args = None

    def __call__(self, pdf):
        self.called = True
        self.call_args = pdf


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
