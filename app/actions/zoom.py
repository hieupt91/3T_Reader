from packages.qt_compat.QtCore import QTimer

from app.actions._guard import require_webview

_JS_ZOOM_IN = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    var viewer = app.pdfViewer;
    if (typeof viewer.increaseScale === 'function') {
        viewer.increaseScale();
    } else if (typeof app.zoomIn === 'function') {
        app.zoomIn(1);
    } else {
        viewer.currentScaleValue = String(Math.min(10, (viewer.currentScale || 1) * 1.1));
    }
    return Math.round((viewer.currentScale || 1) * 100);
})()
"""

_JS_ZOOM_OUT = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    var viewer = app.pdfViewer;
    if (typeof viewer.decreaseScale === 'function') {
        viewer.decreaseScale();
    } else if (typeof app.zoomOut === 'function') {
        app.zoomOut(1);
    } else {
        viewer.currentScaleValue = String(Math.max(0.1, (viewer.currentScale || 1) / 1.1));
    }
    return Math.round((viewer.currentScale || 1) * 100);
})()
"""

_JS_FIT_PAGE = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    app.pdfViewer.currentScaleValue = 'page-fit';
    return Math.round((app.pdfViewer.currentScale || 1) * 100);
})()
"""


def _update_spinner(window, pct):
    if pct and pct > 0:
        window.zoom_spin.setValue(int(pct))


def _run_zoom_js(window, wv, js: str, *, attempts: int = 8):
    def _handle(pct, remaining: int):
        if pct and pct > 0:
            _update_spinner(window, pct)
            return
        if remaining <= 0:
            return
        QTimer.singleShot(120, lambda: wv.page().runJavaScript(js, lambda r: _handle(r, remaining - 1)))

    wv.page().runJavaScript(js, lambda pct: _handle(pct, attempts - 1))


@require_webview
def zoom_in(window, wv):
    _run_zoom_js(window, wv, _JS_ZOOM_IN)


@require_webview
def zoom_out(window, wv):
    _run_zoom_js(window, wv, _JS_ZOOM_OUT)


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
    _run_zoom_js(window, wv, js)


@require_webview
def zoom_fit(window, wv):
    _run_zoom_js(window, wv, _JS_FIT_PAGE)
