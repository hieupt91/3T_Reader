"""pdf_write_slot (H1 fix): serialize read-modify-write across every PDF
writer without using a plain threading.Lock, which would deadlock the whole
UI the first time a writer's own event-pumping (wait_for_thumbnail_idle,
release_viewer_file_lock's processEvents) re-enters another writer for the
SAME file on the SAME thread (e.g. the debounced annotation-autosave QTimer
firing mid-write). These tests exercise the real context manager, not just
its source text - the deadlock-safety property especially needs a real
runtime check, not a string match.
"""

import inspect
import threading
import time

from app.actions import annotate, document_ops, edit, pages, sign
from app.actions._pdf_save import _active_pdf_writes, _normalise_path, pdf_write_slot


def test_marks_path_busy_during_block_and_clears_after(tmp_path):
    path = str(tmp_path / "a.pdf")
    key = _normalise_path(path)
    assert key not in _active_pdf_writes
    with pdf_write_slot(path):
        assert key in _active_pdf_writes
    assert key not in _active_pdf_writes


def test_busy_marker_cleared_even_on_exception(tmp_path):
    path = str(tmp_path / "a.pdf")
    key = _normalise_path(path)
    try:
        with pdf_write_slot(path):
            raise ValueError("boom")
    except ValueError:
        pass
    assert key not in _active_pdf_writes


def test_reentrant_call_on_same_path_times_out_without_deadlocking(tmp_path):
    """The exact scenario that made a plain threading.Lock unsafe here: a
    writer already holding the slot triggers (via pumped Qt events) another
    writer for the SAME file on the SAME thread. This must resolve (by
    timing out and proceeding) rather than hang the test/UI forever."""
    path = str(tmp_path / "a.pdf")
    started = time.monotonic()
    with pdf_write_slot(path):
        # Reentrant on the same thread - must not block forever.
        with pdf_write_slot(path, timeout_s=0.3):
            pass
    elapsed = time.monotonic() - started
    assert elapsed < 3.0  # bounded by the short timeout, not hung


def test_different_paths_do_not_block_each_other(tmp_path):
    path_a = str(tmp_path / "a.pdf")
    path_b = str(tmp_path / "b.pdf")
    started = time.monotonic()
    with pdf_write_slot(path_a):
        with pdf_write_slot(path_b, timeout_s=5.0):
            pass
    elapsed = time.monotonic() - started
    assert elapsed < 1.0  # no wait at all expected - independent files


def test_second_writer_on_a_different_thread_waits_then_proceeds_after_first_releases(tmp_path):
    """Cross-thread case (the original motivation for _PDF_SAVE_LOCK): one
    real OS thread holds the slot while doing work; another thread wanting
    the same file must wait for it to finish, not race past it."""
    path = str(tmp_path / "a.pdf")
    events: list[str] = []
    release_after = 0.3

    def writer_a():
        with pdf_write_slot(path):
            events.append("a_acquired")
            time.sleep(release_after)
            events.append("a_released")

    thread_a = threading.Thread(target=writer_a)
    thread_a.start()
    time.sleep(0.05)  # let thread_a acquire first

    with pdf_write_slot(path, timeout_s=5.0):
        events.append("b_acquired")
    thread_a.join(timeout=5.0)

    assert events == ["a_acquired", "a_released", "b_acquired"]


def test_old_non_reentrant_lock_fully_retired_from_every_writer_module():
    """_PDF_SAVE_LOCK (threading.Lock, not reentrant) must not linger
    anywhere - leaving it defined but unused would be confusing, and if any
    caller still imported/used it there would be two parallel, non-cooperating
    synchronization mechanisms (defeats the whole point: a writer using the
    old lock and one using pdf_write_slot would not see each other's "busy"
    state)."""
    for mod in (annotate, pages, sign, edit, document_ops):
        assert "_PDF_SAVE_LOCK" not in inspect.getsource(mod), mod.__name__


def test_every_writer_module_imports_pdf_write_slot():
    for mod in (annotate, pages, sign, edit, document_ops):
        assert "pdf_write_slot" in inspect.getsource(mod), mod.__name__
