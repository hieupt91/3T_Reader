from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_line_mark_search_rects_do_not_use_highlight_padding():
    from app.actions.annotate import _merge_rects_by_line

    rect = (10.0, 100.0, 40.0, 112.0)

    highlight_rects = _merge_rects_by_line([rect])
    line_rects = _merge_rects_by_line([rect], pad=False)

    assert highlight_rects == [(10.0, 99.04, 40.0, 112.96)]
    assert line_rects == [rect]


def test_find_mode_underline_and_strikeout_use_unpadded_search_rects():
    source = (ROOT / "app" / "actions" / "annotate.py").read_text(encoding="utf-8")

    assert 'pad=(mark_type == "highlight")' in source
    assert 'pad=(annot_type not in {"underline", "strikeout"})' in source


def test_underline_and_strikeout_can_use_current_search_query_without_selection(monkeypatch):
    from app.actions import annotate

    calls = []

    class SearchInput:
        def text(self):
            return "sua"

    class Window:
        _mark_mode = "select"
        search_input = SearchInput()
        search_query = ""

    monkeypatch.setattr(annotate, "_get_selection_page_rects_sync", lambda _window, **_kwargs: ("", {}))
    monkeypatch.setattr(
        annotate,
        "_mark_keyword_everywhere",
        lambda _window, mark_type, keyword: calls.append((mark_type, keyword)) or True,
    )
    monkeypatch.setattr(annotate, "_do_selected_text_mark", lambda *_args: calls.append(("selection", "")))

    annotate.underline_text.__wrapped__(Window())
    annotate.strikeout_text.__wrapped__(Window())

    assert calls == [("underline", "sua"), ("strikeout", "sua")]


def test_search_mark_status_reports_line_area_and_word_count():
    source = (ROOT / "app" / "actions" / "annotate.py").read_text(encoding="utf-8")

    assert "word_count = len(_tokenize_text(keyword))" in source
    assert "dòng/vùng" in source
    assert "cụm {word_count} từ" in source
