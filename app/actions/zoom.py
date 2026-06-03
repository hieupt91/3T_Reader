from packages.qt_compat.QtCore import QTimer

from app.actions._guard import require_webview

_JS_ZOOM_IN = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    var viewer = app.pdfViewer;
    var current = Number(viewer.currentScale || 1);
    var target = Math.min(4.0, current * 1.1);
    viewer.currentScaleValue = String(target);
    return Math.round(target * 100);
})()
"""

_JS_ZOOM_OUT = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    var viewer = app.pdfViewer;
    var current = Number(viewer.currentScale || 1);
    var target = Math.max(0.25, current / 1.1);
    viewer.currentScaleValue = String(target);
    return Math.round(target * 100);
})()
"""

_JS_FIT_PAGE = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    app.pdfViewer.currentScaleValue = '1.0';
    return Math.round((app.pdfViewer.currentScale || 1) * 100);
})()
"""


def _update_spinner(window, pct):
    if pct and pct > 0:
        try:
            window.zoom_spin.blockSignals(True)
            window.zoom_spin.setValue(max(25, min(400, int(pct))))
        finally:
            window.zoom_spin.blockSignals(False)


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
