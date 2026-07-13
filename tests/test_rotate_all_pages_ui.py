from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_rotate_pages_action_is_exposed_from_page_ui():
    window_source = _read("app/window.py")

    assert "from app.actions.pages import merge_pdfs_action, rotate_pages_action, split_pdf_action" in window_source
    assert "self._act_rotate_pages = make(" in window_source
    assert "lambda: rotate_pages_action(self)" in window_source
    assert "self.g_rot.add(make_action_btn(self._act_rotate_pages, \"Xoay trang\"))" in window_source
    assert "act_rotate_pages = menu_pages.addAction(\"Xoay trang...\")" in window_source


def test_rotate_pages_dialog_keeps_all_pages_entry_point():
    pages_source = _read("app/actions/pages.py")

    assert "apply_all = QPushButton(\"Xoay TẤT CẢ trang\")" in pages_source
    assert "rotations = {pn: deg for pn in range(1, total + 1)}" in pages_source


def test_rotate_pages_runs_viewer_js_on_real_webengine_view():
    pages_source = _read("app/actions/pages.py")

    assert "findChild(QWebEngineView)" in pages_source
    assert "wv.page().runJavaScript(js_code)" in pages_source
    assert "window.viewer.page().runJavaScript(js_code)" not in pages_source


def test_rotate_all_pages_previews_only_visible_sidebar_thumbnails():
    pages_source = _read("app/actions/pages.py")

    assert "preview_rotations = rotations" in pages_source
    assert "if _all_pages[0]:" in pages_source
    assert "window.sidebar._visible_page_range()" in pages_source
    assert "for pn, rdeg in preview_rotations.items():" in pages_source
    assert "for pn, rdeg in rotations.items():" not in pages_source
