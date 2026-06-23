from __future__ import annotations

import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _app_python_files() -> list[Path]:
    return sorted((ROOT / "app").rglob("*.py"))


def test_qwebchannel_is_initialized_only_by_viewer_helper():
    """QWebChannel code lives in the external JS file, loaded by pdf_viewer.py."""
    js_hooks = _read("assets/js/pdfjs_ui_hooks.js")
    assert "new QWebChannel" in js_hooks
    assert "qrc:///qtwebchannel/qwebchannel.js" in js_hooks
    # Verify pdf_viewer.py loads the JS file
    viewer = _read("app/pdf_viewer.py")
    assert "pdfjs_ui_hooks.js" in viewer


def test_viewer_pushes_page_and_zoom_state_from_pdfjs_events():
    """Event hooks are in the external JS file, loaded by pdf_viewer.py."""
    js_hooks = _read("assets/js/pdfjs_ui_hooks.js")

    for event_name in (
        "pagechanging",
        "updateviewarea",
        "scalechanging",
        "scalechanged",
    ):
        assert event_name in js_hooks

    assert "addEventListener('scroll'" in js_hooks
    assert "reportPageState(app, 'scroll')" in js_hooks
    assert "window.__3tWithBridge('pageStateBridge'" in js_hooks


def test_selection_cache_survives_toolbar_focus_loss():
    """Selection cache logic is in the external JS file."""
    js_hooks = _read("assets/js/pdfjs_ui_hooks.js")

    assert "window.__3tLastSelectionPayload" in js_hooks
    assert "window.__3tReadSelectionPayload" in js_hooks
    assert "document.addEventListener('pointerup'" in js_hooks
    assert "[0, 60, 160, 320, 640]" in js_hooks
    assert "area > bestArea" in js_hooks


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


def test_annotation_overlay_renderer_is_page_scoped_and_defines_page_element():
    from app.actions import annotate

    js = annotate._ARM_NOTE_TOOLS_JS

    assert "function removeOldOverlays(pageNumber)" in js
    assert "function renderPage(pageNumber)" in js
    assert "var pageNumber = event && event.pageNumber ? Number(event.pageNumber) : 0;" in js
    assert "renderStickyNoteIcon(viewer" not in js
    assert "pageEl.appendChild(node)" in js
    assert js.index("var pageEl = pageView.div;") < js.index("pageEl.appendChild(node)")
    assert "removeOldOverlays();\n            noteItems.forEach" not in js


def test_annotation_selection_falls_back_to_qt_selected_text(monkeypatch):
    from app.actions import annotate

    class Window:
        current_path = "sample.pdf"

    monkeypatch.setattr(annotate, "_get_current_page", lambda _window: 3)
    monkeypatch.setattr(annotate, "_search_text_on_page", lambda path, page, text: [(10, 20, 30, 40)])

    payload = annotate._fallback_selection_payload_from_text(Window(), "Van phong Dang uy")

    assert payload["source"] == "qt_selected_text_search"
    assert payload["text"] == "Van phong Dang uy"
    assert payload["rects"] == [{"page_number": 3, "rect": [10.0, 18.4, 30.0, 41.6]}]


def test_inline_edit_scripts_use_shared_bridge_not_private_webchannels():
    """Bridge code lives in external JS files, loaded by pdf_inline_editor.py."""
    inline_text_js = _read("assets/js/inline_text_bridge.js")
    inline_image_js = _read("assets/js/inline_image_bridge.js")
    area_pick_js = _read("assets/js/area_pick.js")
    inline_editor = _read("app/pdf_inline_editor.py")
    edit_actions = _read("app/actions/edit.py")

    # Verify JS files use shared bridge helper
    assert "__3tWithBridge('inlineTextBridge'" in inline_text_js
    assert "__3tWithBridge('inlineImageBridge'" in inline_image_js
    assert "__3tWithBridge('areaPickBridge'" in area_pick_js
    # Verify no private QWebChannel in JS files
    assert "new QWebChannel" not in inline_text_js
    assert "new QWebChannel" not in inline_image_js
    assert "new QWebChannel" not in area_pick_js
    # Verify Python files load from external JS
    assert "inline_text_bridge.js" in inline_editor
    assert "inline_image_bridge.js" in inline_editor
    assert "area_pick.js" in edit_actions


def test_inline_image_preview_is_more_visible_and_guided():
    inline_image_js = _read("assets/js/inline_image_bridge.js")

    assert "PNG trong suot" in inline_image_js
    assert "Keo de di chuyen" in inline_image_js
    assert "data-3t-img-hud" in inline_image_js
    assert "data-3t-img-body" in inline_image_js
    assert "data-3t-img-ghost" in inline_image_js
    assert "checker.style.cssText" in inline_image_js
    assert "mix-blend-mode:normal" in inline_image_js
    assert "transparentImage" in inline_image_js


def test_background_rotate_uses_atomic_replace_not_shutil_move():
    from app.actions import annotate, pages

    annotate_src = inspect.getsource(annotate._rotate_page)
    pages_src = inspect.getsource(pages.rotate_pages_action)

    assert "replace_file_with_retry(tmp, path, attempts=12)" in annotate_src
    assert "shutil.move(tmp, path)" not in annotate_src
    assert "replace_file_with_retry(tmp, path, attempts=12)" in pages_src
    assert "shutil.move(tmp, path)" not in pages_src
