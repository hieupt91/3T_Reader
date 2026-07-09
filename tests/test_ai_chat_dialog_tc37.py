from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app" / "ai_chat_dialog.py").read_text(encoding="utf-8")


def test_stays_on_top_toggle_preserves_visible_chat_state():
    source = _source()
    start = source.index("    def _set_stays_on_top")
    end = source.index("\n    def _append_html", start)
    body = source[start:end]

    assert "chat_html = self._chat_area.toHtml()" in body
    assert "input_text = self._input.text()" in body
    assert "self._chat_area.setHtml(chat_html)" in body
    assert "self._input.setText(input_text)" in body
    assert "self._rebuild_chat()" not in body


def test_chat_close_event_accepts_after_topmost_toggle():
    source = _source()
    start = source.index("    def closeEvent")
    body = source[start:]

    assert "event.accept()" in body
    assert "event.ignore()" not in body
