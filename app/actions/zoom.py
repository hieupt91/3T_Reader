from app.actions._guard import require_document, require_webview

_JS_ZOOM_IN = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    if (typeof app.zoomIn === 'function') {
        app.zoomIn(1);
    } else {
        app.pdfViewer.currentScale = Math.min(10, app.pdfViewer.currentScale * 1.1);
    }
    return Math.round((app.pdfViewer.currentScale || 1) * 100);
})()
"""

_JS_ZOOM_OUT = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    if (typeof app.zoomOut === 'function') {
        app.zoomOut(1);
    } else {
        app.pdfViewer.currentScale = Math.max(0.1, app.pdfViewer.currentScale / 1.1);
    }
    return Math.round((app.pdfViewer.currentScale || 1) * 100);
})()
"""

_JS_FIT_PAGE = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    app.pdfViewer.currentScaleValue = 'page-width';
    return Math.round((app.pdfViewer.currentScale || 1) * 100);
})()
"""


def _update_spinner(window, pct):
    if pct and pct > 0:
        window.zoom_spin.setValue(int(pct))


@require_webview
def zoom_in(window, wv):
    wv.page().runJavaScript(_JS_ZOOM_IN, lambda pct: _update_spinner(window, pct))


@require_webview
def zoom_out(window, wv):
    wv.page().runJavaScript(_JS_ZOOM_OUT, lambda pct: _update_spinner(window, pct))


@require_webview
def apply_zoom(window, wv):
    pct = window.zoom_spin.value()
    scale = pct / 100
    js = f"""
(function() {{
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    app.pdfViewer.currentScaleValue = '{scale}';
    return Math.round((app.pdfViewer.currentScale || 1) * 100);
}})()
"""
    wv.page().runJavaScript(js, lambda r: _update_spinner(window, r))


@require_webview
def zoom_fit(window, wv):
    wv.page().runJavaScript(_JS_FIT_PAGE, lambda pct: _update_spinner(window, pct))
