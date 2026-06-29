from __future__ import annotations

import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_save_edits_without_edit_state_does_not_call_viewer_save_pdf():
    from app.actions import edit

    source = inspect.getsource(edit.save_edits)
    no_state_block = source.split("if not state:", 1)[1].split("working =", 1)[0]

    assert "viewer.save_pdf" not in no_state_block
    assert "Không có thay đổi cần lưu." in no_state_block
    assert "Đã lưu chú thích." in no_state_block


def test_viewer_save_pdf_is_explicit_non_persistence_path():
    source = _read("app/pdf_viewer.py")

    assert "def save_pdf(self) -> bool:" in source
    assert "Viewer không lưu trực tiếp" in source
    assert "return False" in source
