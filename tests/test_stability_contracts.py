from __future__ import annotations

import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_ai_summarize_shortcut_does_not_conflict_with_save_as():
    source = _read("app/window.py")
    assert 'AI_SUMMARIZE_SHORTCUT = "Ctrl+Alt+S"' in source
    assert "act_ai_summarize.setShortcut(QKeySequence(AI_SUMMARIZE_SHORTCUT))" in source
    assert '"Ctrl+Shift+S", lambda: open_summarize_dialog' not in source


def test_token_monitor_runs_in_background_worker():
    source = _read("app/window.py")
    assert "class _TokenPresenceWorker" in source
    assert "timer.timeout.connect(self._check_token_presence)" in source
    assert "worker.moveToThread(thread)" in source
    assert "subprocess.run" not in source


def test_handwritten_signature_path_does_not_import_fitz():
    source = _read("app/actions/sign.py")
    assert "import fitz" not in source
    assert "rebuild_pdf_with_ops" in source


def test_save_edits_quiet_does_not_reload_viewer():
    from app.actions import edit

    source = inspect.getsource(edit.save_edits_quiet)
    assert "reload_document" not in source
    assert "reload_viewer=False" in source


def test_object_actions_use_typed_webchannel_bridge():
    edit_source = _read("app/actions/edit.py")
    webchannel_source = _read("app/webchannel.py")

    assert "objectActionBridge" in edit_source
    assert "class _ObjectActionBridgeProxy" in webchannel_source
    assert "window.__3tPendingAction" not in edit_source
    assert "poll_timer" not in edit_source


def test_signature_flows_do_not_reopen_placement_dialog():
    from app.actions import sign

    assert "SignaturePlacementDialog(" not in inspect.getsource(sign.sign_handwritten)
    assert "SignaturePlacementDialog(" not in inspect.getsource(sign.sign_with_pfx)
    assert "SignaturePlacementDialog(" not in inspect.getsource(sign.sign_document)


def test_app_update_ui_uses_current_updater_package():
    app_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "app").glob("*.py")
    )

    assert "packages.updater" in app_sources
    assert "packages.update_client" not in app_sources


def test_currentcolor_svg_icons_rasterize_for_mark_buttons():
    from app.icon_utils import _recolor_svg_data

    svg = '<svg color="currentColor"><path stroke="currentColor"/></svg>'
    recolored = _recolor_svg_data(svg, "#2563eb")

    assert "currentColor" not in recolored
    assert 'color="#2563eb"' in recolored
    assert 'stroke="#2563eb"' in recolored
