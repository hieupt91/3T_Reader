from __future__ import annotations

import inspect
import os
import time

from app.actions import _pdf_save
from app.actions import edit


class _FakeViewer:
    def __init__(self, page: int = 1):
        self._page = page
        self._zoom = "100"
        self.loaded = []

    def get_current_page(self):
        return self._page

    def load_pdf(self, path, page=1, zoom="page-width"):
        self.loaded.append((path, page, zoom))
        self._page = page


class _FakeSoftReloadViewer(_FakeViewer):
    def __init__(self, page: int = 1, zoom: str = "175"):
        super().__init__(page)
        self._zoom = zoom
        self.soft_loaded = []

    def reload_soft(self, path, zoom="100", page=None, ops_json="[]", erase_json="[]"):
        self.soft_loaded.append((path, page, zoom))
        if page is not None:
            self._page = page


class _FakeWindow:
    def __init__(self, source_path: str, *, display_path: str | None = None, temp_path: str | None = None, page: int = 2):
        self.viewer = _FakeViewer(page)
        self._state = {
            "source_path": source_path,
            "display_path": display_path or source_path,
            "temp_path": temp_path,
            "_pdf_edit_state": None,
        }

    def _state_or_global(self):
        return self._state

    def _active_state(self):
        return self._state

    @property
    def current_path(self):
        return self._state["source_path"]

    @current_path.setter
    def current_path(self, value):
        self._state["source_path"] = value

    def get_display_path(self):
        return self._state.get("display_path")


def test_make_staged_pdf_path_uses_target_directory(tmp_path):
    target = tmp_path / "doc.pdf"
    staged = _pdf_save.make_staged_pdf_path(str(target))

    assert os.path.dirname(staged) == str(tmp_path)
    assert os.path.exists(staged)

    _pdf_save.remove_path_quietly(staged)


def test_replace_document_with_staged_updates_state_and_cleans_old_temp(tmp_path):
    target = tmp_path / "doc.pdf"
    target.write_bytes(b"old")
    old_temp = tmp_path / "old_temp.pdf"
    old_temp.write_bytes(b"temp")
    staged = _pdf_save.make_staged_pdf_path(str(target))
    with open(staged, "wb") as fh:
        fh.write(b"new")

    window = _FakeWindow(str(target), temp_path=str(old_temp), page=3)

    _pdf_save.replace_document_with_staged(
        window,
        staged,
        target_path=str(target),
        display_path=str(target),
        temp_path=None,
    )

    assert target.read_bytes() == b"new"
    assert window.current_path == str(target)
    assert window.get_display_path() == str(target)
    assert window._state["temp_path"] is None
    assert not old_temp.exists()
    assert window.viewer.loaded == [(str(target), 3, "100")]


def test_replace_document_with_staged_prefers_soft_reload_and_keeps_zoom(tmp_path):
    target = tmp_path / "doc.pdf"
    target.write_bytes(b"old")
    staged = _pdf_save.make_staged_pdf_path(str(target))
    with open(staged, "wb") as fh:
        fh.write(b"new")

    window = _FakeWindow(str(target), temp_path=None, page=4)
    window.viewer = _FakeSoftReloadViewer(page=4, zoom="175")
    window.viewer._path = str(target)

    _pdf_save.replace_document_with_staged(
        window,
        staged,
        target_path=str(target),
        display_path=str(target),
        temp_path=None,
    )

    assert target.read_bytes() == b"new"
    assert window.viewer.soft_loaded == [(str(target), 4, "175")]
    assert window.viewer.loaded == []


def test_ensure_edit_state_prefers_display_path_over_legacy_op_temp(tmp_path, monkeypatch):
    temp_root = tmp_path / "reader_pdf_edit"
    temp_root.mkdir()
    legacy_temp = temp_root / "op_12345678.pdf"
    display_pdf = tmp_path / "original.pdf"
    display_bytes = b"%PDF-1.4\n%original"
    display_pdf.write_bytes(display_bytes)
    legacy_temp.write_bytes(b"legacy")

    monkeypatch.setattr(edit.tempfile, "gettempdir", lambda: str(tmp_path))

    window = _FakeWindow(str(legacy_temp), display_path=str(display_pdf))
    state = edit._ensure_edit_state(window)

    assert state is not None
    assert state["original_path"] == str(display_pdf)
    with open(state["base_snapshot"], "rb") as fh:
        assert fh.read() == display_bytes
    with open(state["working_file"], "rb") as fh:
        assert fh.read() == display_bytes

    edit._reset_edit_state(window)


def test_pick_context_matches_rejects_tab_switch(tmp_path):
    source = tmp_path / "doc-a.pdf"
    source.write_bytes(b"a")
    other = tmp_path / "doc-b.pdf"
    other.write_bytes(b"b")

    window = _FakeWindow(str(source), display_path=str(source))
    expected_state = window._active_state()
    assert edit._pick_context_matches(window, expected_state, str(source)) is True

    window._state = {
        "source_path": str(other),
        "display_path": str(other),
        "temp_path": None,
        "_pdf_edit_state": None,
    }
    assert edit._pick_context_matches(window, expected_state, str(source)) is False


# --- Additional unit tests for _pdf_save helpers ---


def test_atomic_copy_file_copies_content(tmp_path):
    src = tmp_path / "source.pdf"
    dst = tmp_path / "dest.pdf"
    src.write_bytes(b"PDF content here")
    _pdf_save.atomic_copy_file(str(src), str(dst))
    assert dst.read_bytes() == b"PDF content here"


def test_atomic_copy_file_cleans_staged_on_failure(tmp_path):
    src = tmp_path / "source.pdf"
    src.write_bytes(b"content")
    dst = str(tmp_path / "nonexistent_dir" / "dest.pdf")
    try:
        _pdf_save.atomic_copy_file(str(src), dst)
    except Exception:
        pass
    # Staged files should be cleaned up
    staged_files = [f for f in tmp_path.glob(".3t_stage_*")]
    assert len(staged_files) == 0


def test_replace_file_with_retry_replaces(tmp_path):
    src = tmp_path / "src.pdf"
    dst = tmp_path / "dst.pdf"
    src.write_bytes(b"new")
    dst.write_bytes(b"old")
    _pdf_save.replace_file_with_retry(str(src), str(dst), attempts=3)
    assert dst.read_bytes() == b"new"
    assert not src.exists()


def test_remove_path_quietly_removes(tmp_path):
    f = tmp_path / "to_delete.pdf"
    f.write_bytes(b"delete me")
    _pdf_save.remove_path_quietly(str(f))
    assert not f.exists()


def test_remove_path_quietly_no_error_on_missing(tmp_path):
    _pdf_save.remove_path_quietly(str(tmp_path / "nonexistent.pdf"))


def test_remove_path_quietly_no_error_on_none():
    _pdf_save.remove_path_quietly(None)


def test_prune_stale_app_temp_files_keeps_active_and_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(_pdf_save.tempfile, "gettempdir", lambda: str(tmp_path))

    edit_dir = tmp_path / "reader_pdf_edit"
    sign_dir = tmp_path / "reader_pdf_sig"
    edit_dir.mkdir()
    sign_dir.mkdir()

    stale_base = edit_dir / "base_stale.pdf"
    active_work = edit_dir / "work_active.pdf"
    recent_work = edit_dir / "work_recent.pdf"
    stale_sig = sign_dir / "sig_stale.png"
    unrelated = edit_dir / "notes.txt"
    for path in (stale_base, active_work, recent_work, stale_sig, unrelated):
        path.write_bytes(b"x")

    old_ts = time.time() - _pdf_save.STALE_TEMP_MAX_AGE_SECONDS - 60
    for path in (stale_base, active_work, stale_sig, unrelated):
        os.utime(path, (old_ts, old_ts))

    removed = _pdf_save.prune_stale_app_temp_files(active_paths=[str(active_work)])

    assert removed == 2
    assert not stale_base.exists()
    assert active_work.exists()
    assert recent_work.exists()
    assert not stale_sig.exists()
    assert unrelated.exists()


def test_make_staged_pdf_path_prunes_old_staged_pdf_in_target_dir(tmp_path):
    stale_stage = tmp_path / ".3t_stage_old.pdf"
    unrelated = tmp_path / ".3t_stage_notes.txt"
    target = tmp_path / "document.pdf"
    stale_stage.write_bytes(b"old")
    unrelated.write_bytes(b"keep")

    old_ts = time.time() - _pdf_save.STALE_TEMP_MAX_AGE_SECONDS - 60
    os.utime(stale_stage, (old_ts, old_ts))
    os.utime(unrelated, (old_ts, old_ts))

    staged = _pdf_save.make_staged_pdf_path(str(target))

    assert not stale_stage.exists()
    assert unrelated.exists()
    assert os.path.exists(staged)
    _pdf_save.remove_path_quietly(staged)


def test_document_ops_password_and_pagenum_regressions_are_guarded_in_source():
    from app.actions import document_ops

    set_password_src = inspect.getsource(document_ops.set_pdf_password)
    compress_src = inspect.getsource(document_ops.compress_pdf)
    add_page_numbers_src = inspect.getsource(document_ops.add_page_numbers)
    remove_page_numbers_src = inspect.getsource(document_ops.remove_page_numbers)
    remove_pagenum_src = inspect.getsource(document_ops._remove_pagenums)

    assert "_document_read_and_target_paths(window)" in set_password_src
    assert "with pikepdf.open(read_path) as doc:" in set_password_src
    assert "replace_file_with_retry(out, src, window=window)" in set_password_src

    assert "_document_read_and_target_paths(window)" in compress_src
    assert "os.path.abspath(str(read_path)) != os.path.abspath(str(target_path))" in compress_src
    assert "show_warning(" in compress_src

    assert "_document_read_and_target_paths(window)" in add_page_numbers_src
    assert "_document_read_and_target_paths(window)" in remove_page_numbers_src

    assert "if remaining_marker > 1:" in remove_pagenum_src
    assert 'page.obj[_PAGENUM_MARKER_KEY] = remaining_marker - 1' in remove_pagenum_src
