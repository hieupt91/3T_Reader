from __future__ import annotations

import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _app_python_files() -> list[Path]:
    return sorted((ROOT / "app").rglob("*.py"))


def test_qwebchannel_is_initialized_only_by_viewer_helper():
    matches: list[str] = []
    qrc_matches: list[str] = []

    for path in _app_python_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        if "new QWebChannel" in text:
            matches.append(rel)
        if "qrc:///qtwebchannel/qwebchannel.js" in text:
            qrc_matches.append(rel)

    assert matches == ["app/pdf_viewer.py"]
    assert qrc_matches == ["app/pdf_viewer.py"]


def test_viewer_pushes_page_and_zoom_state_from_pdfjs_events():
    viewer = _read("app/pdf_viewer.py")

    for event_name in (
        "pagechanging",
        "updateviewarea",
        "scalechanging",
        "scalechanged",
    ):
        assert event_name in viewer

    assert "addEventListener('scroll'" in viewer
    assert "reportPageState(app, 'scroll')" in viewer
    assert "window.__3tWithBridge('pageStateBridge'" in viewer


def test_selection_cache_survives_toolbar_focus_loss():
    viewer = _read("app/pdf_viewer.py")

    assert "window.__3tLastSelectionPayload" in viewer
    assert "window.__3tReadSelectionPayload" in viewer
    assert "document.addEventListener('pointerup'" in viewer
    assert "[0, 60, 160, 320, 640]" in viewer
    assert "area > bestArea" in viewer


def test_text_mark_toolbar_uses_pdfjs_selection_rects_without_prompt_or_search():
    from app.actions import annotate

    highlight_src = inspect.getsource(annotate.highlight_text)
    underline_src = inspect.getsource(annotate.underline_text)
    strikeout_src = inspect.getsource(annotate.strikeout_text)
    selected_mark_src = inspect.getsource(annotate._do_selected_text_mark)
    selection_js = annotate._GET_SELECTION_RECTS_JS

    assert '_do_selected_text_mark(window, "highlight")' in highlight_src
    assert '_do_selected_text_mark(window, "underline")' in underline_src
    assert '_do_selected_text_mark(window, "strikeout")' in strikeout_src

    assert "_get_selection_page_rects_sync(window)" in selected_mark_src
    assert "_search_text_on_page" not in selected_mark_src
    assert "QInputDialog" not in selected_mark_src
    assert "getText" not in selected_mark_src
    assert "__3tReadSelectionPayload" in selection_js
    assert "convertToPdfPoint" not in selection_js
    assert "getClientRects" not in selection_js


def test_inline_edit_scripts_use_shared_bridge_not_private_webchannels():
    inline_editor = _read("app/pdf_inline_editor.py")
    edit_actions = _read("app/actions/edit.py")

    assert "new QWebChannel" not in inline_editor
    assert "new QWebChannel" not in edit_actions
    assert "__3tWithBridge('inlineTextBridge'" in inline_editor
    assert "__3tWithBridge('inlineImageBridge'" in inline_editor
    assert "__3tWithBridge('areaPickBridge'" in edit_actions
