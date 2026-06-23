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


def test_token_monitor_skips_during_signing():
    source = _read("app/window.py")
    assert "signing_thread = getattr(self, \"_signing_thread\", None)" in source
    assert "if signing_thread is not None and signing_thread.isRunning()" in source
    assert "self._token_monitor_suspended = True" in source
    assert "def _pause_token_monitor" in source
    assert "def _resume_token_monitor" in source


def test_recent_menu_refresh_handles_deleted_menu():
    source = _read("app/window.py")
    assert "menu = getattr(self, \"menu_recent\", None)" in source
    assert "except RuntimeError:" in source
    assert "_populate_recent_menu(menu, self)" in source


def test_close_event_waits_for_signing_thread():
    source = _read("app/window.py")
    assert "signing_thread = getattr(self, \"_signing_thread\", None)" in source
    assert "signing_thread.quit()" in source
    assert '\"Đang ký số\"' in source


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


def test_signature_flows_confirm_before_committing():
    from app.actions import sign

    source = inspect.getsource(sign)
    assert "def _confirm_signature_selection" in source
    assert source.count("_confirm_signature_selection(window)") >= 3
    assert "Bạn có đồng ý ký văn bản này tại vị trí đã chọn không?" in source
    assert "prompt.accept()" in source
    assert "prompt.reject()" in source


def test_usb_signature_preview_scales_with_overlay_size():
    source = _read("app/actions/sign.py")
    assert "syncPreviewTypography" in source
    assert "state.textDiv = textDiv;" in source
    assert "_signature_preview_scale(" in source


def test_usb_sign_flow_does_not_reopen_token_for_display_name():
    from app.actions import sign

    source = inspect.getsource(sign.sign_document)
    assert "get_token_info(pin)" not in source
    assert "_run_usb_signing_task(" in source
    assert "_run_usb_signing_subprocess(" in source


def test_usb_signing_task_avoids_qthread_parent_cleanup():
    from app.actions import sign

    source = inspect.getsource(sign._run_usb_signing_task)
    assert "_pause_token_monitor" in source
    assert "_resume_token_monitor" in source
    assert "QThread" not in source
    assert "fn()" in source


def test_signing_task_pauses_usb_monitor_while_working():
    from app.actions import sign

    source = inspect.getsource(sign._run_signing_task)
    assert "_pause_token_monitor" in source
    assert "_resume_token_monitor" in source


def test_vietnamese_stamp_uses_unicode_font_when_available(monkeypatch):
    from packages.signing import shared

    monkeypatch.setattr(
        "packages.platform.fonts.get_vietnamese_font_path",
        lambda bold=False: r"C:\\Windows\\Fonts\\arial.ttf",
    )

    style = shared.build_vietnamese_stamp_style("Nguyen Van A", signed_at="01/01/2026 10:00:00")

    assert style.background is not None
    assert style.background_opacity == 1.0
    assert style.stamp_text.strip() == ""


def test_signature_preview_for_png_remains_transparent():
    source = _read("app/actions/sign.py")
    assert "box.style.background = 'transparent';" in source
    assert "overlay.style.background = 'transparent';" in source
    assert "box.style.background = '#ffffff';" not in source
    assert "overlay.style.background = '#ffffff';" not in source


def test_signature_widget_css_does_not_hide_appearance_content():
    source = _read("assets/css/pdfjs_overrides.css")
    assert ".annotationLayer .signatureWidgetAnnotation *" not in source
    assert ".annotationLayer .signatureWidgetAnnotation input," in source
    assert "opacity: 0 !important;" not in source
    assert "pointer-events: none !important;" in source


def test_signature_widget_click_opens_signature_info_bridge():
    js_source = _read("assets/js/pdfjs_ui_hooks.js")
    viewer_source = _read("app/pdf_viewer.py")
    webchannel_source = _read("app/webchannel.py")
    window_source = _read("app/window.py")

    assert "signatureInfoBridge" in js_source
    assert ".signatureWidgetAnnotation" in js_source
    assert "findSignatureTargetFromPoint" in js_source
    assert "params.get('sigmeta')" in js_source
    assert "showSignatureInfo(pageNumber, fieldName)" in js_source
    assert "signature_clicked = pyqtSignal(int, str)" in viewer_source
    assert "class _SignatureInfoBridgeProxy" in webchannel_source
    assert "def _on_signature_clicked" in window_source


def test_print_preview_preserves_target_page_without_polling_timer():
    source = _read("app/window.py")
    assert "currentPageChanged.connect(_remember_page)" in source
    assert "track_page" not in source
    assert "QTimer.singleShot(200, track_page)" not in source
    assert "setCurrentPage(pg)" in source


def test_print_loop_updates_orientation_per_page():
    source = _read("app/window.py")
    assert "desired_orientation = self._page_orientation_for_pdf_size(page_w_pt, page_h_pt)" in source
    assert "_apply_printer_orientation(printer, desired_orientation)" in source
    assert "printer.newPage()" in source


def test_print_preview_prefers_higher_render_scale_for_clarity():
    source = _read("app/window.py")
    assert "def _print_preview_render_scale(" in source
    assert "dpi_scale = max(1.0, float(printer_resolution or 300) / 72.0)" in source
    assert "job_cap = 3.5 if large_job else 5.5" in source
    assert "pixel_cap = 14_000_000 if large_job else 28_000_000" in source


def test_ai_chat_session_persists_history_to_disk():
    source = _read("packages/ai/chat_pdf.py")
    assert "get_cache_dir()" in source
    assert "_resolve_history_path" in source
    assert "_load_history" in source
    assert "_save_history" in source
    assert "self._history_path.unlink(missing_ok=True)" in source


def test_tts_dialog_uses_disk_cache_and_save_audio_action():
    source = _read("app/actions/tts_dialog.py")
    assert "_tts_cache_dir" in source
    assert "_tts_cache_key" in source
    assert "_tts_cache_path" in source
    assert "self.btn_save_audio" in source
    assert "QFileDialog.getSaveFileName" in source
    assert "shutil.move(audio_path, cached_path)" in source


def test_pdf_viewer_injects_pdfjs_override_css_at_document_ready():
    viewer_source = _read("app/pdf_viewer.py")
    window_source = _read("app/window.py")

    assert 'pdfjs_overrides.setName("pdfjs-overrides")' in viewer_source
    assert "data-3t-pdfjs-overrides" in viewer_source
    assert "page_scripts.insert(pdfjs_overrides)" in viewer_source
    assert "self._inject_css_for_viewer(viewer)" in window_source


def test_signature_status_dialog_shows_extended_signature_properties():
    sign_source = _read("app/actions/sign.py")
    shared_source = _read("packages/signing/shared.py")
    window_source = _read("app/window.py")

    assert 'QPushButton("Chứng thư")' in sign_source
    assert 'form.addRow("Người ký", signer_value)' in sign_source
    assert 'form.addRow("Lý do", reason_value)' in sign_source
    assert 'form.addRow("Ngày ký", when_value)' in sign_source
    assert 'form.addRow("Địa điểm", location_value)' in sign_source
    assert 'form.addRow("Liên hệ", contact_value)' in sign_source
    assert 'validation_summary_lines' in shared_source
    assert '_extract_signature_field_report(path, field_name)' in shared_source
    assert 'validate_signed_pdf_status(pdf_path, field_name=field_name or None)' in window_source


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
