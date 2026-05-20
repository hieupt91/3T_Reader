from app.actions._guard import require_document, require_webview


def _adjust_zoom(window, wv, delta: float):
    val = round(max(0.25, min(4.0, wv.zoomFactor() + delta)), 1)
    wv.setZoomFactor(val)
    window.zoom_spin.setValue(int(val * 100))


@require_webview
def zoom_in(window, wv):
    _adjust_zoom(window, wv, -0.1)


@require_webview
def zoom_out(window, wv):
    _adjust_zoom(window, wv, +0.1)


@require_webview
def apply_zoom(window, wv):
    wv.setZoomFactor(window.zoom_spin.value() / 100)


@require_document()
def zoom_fit(window):
    page = window.viewer.get_current_page()
    page = page if page >= 1 else 1
    window.viewer.load_pdf(window.current_path, zoom="page-width", page=page)
    window.zoom_spin.setValue(100)