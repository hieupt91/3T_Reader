from __future__ import annotations

from app.actions.sign import (
    SignaturePreviewAdjustBridge,
    _get_web_view,
    _set_object_preview,
    _setup_webchannel,
    _teardown_webchannel,
)


class PdfInlineEditorController:
    """Lightweight controller for PDF inline object selection/edit overlays."""

    def __init__(self, window):
        self._window = window
        self._bridge = None
        self._web_view = None

    def _ensure_bridge(self):
        web_view = _get_web_view(self._window)
        if web_view is None:
            return None
        if self._bridge is None or self._web_view is not web_view:
            self._bridge = SignaturePreviewAdjustBridge(self._window)
            self._bridge.adjusted.connect(self._window._apply_selected_object_preview_adjustment)
            self._web_view = web_view
            _setup_webchannel(web_view, self._window, "sigPreviewBridge", self._bridge)
        return web_view

    def show(self, placement: dict | None, *, label: str = "Đang chọn"):
        web_view = self._ensure_bridge()
        if web_view is None:
            return
        if not placement:
            _set_object_preview(self._window, None)
            return
        _set_object_preview(self._window, placement, label=label)

    def clear(self):
        _set_object_preview(self._window, None)
        if self._web_view is not None:
            _teardown_webchannel(self._web_view)
        self._bridge = None
        self._web_view = None

