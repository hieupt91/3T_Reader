from packages.qt_compat.QtCore import QTimer

from app.actions._guard import require_webview

_JS_ZOOM_IN = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    var viewer = app.pdfViewer;
    var container = document.getElementById('viewerContainer');
    var pointer = window.__3tLastPointer || null;
    var before = Number(viewer.currentScale || 1);
    var anchor = null;
    if (container) {
        var vr = container.getBoundingClientRect();
        var px = vr.left + vr.width / 2;
        var py = vr.top + vr.height / 2;
        if (pointer && Date.now() - (pointer.timestamp || 0) < 2000 &&
            pointer.x >= vr.left && pointer.x <= vr.right && pointer.y >= vr.top && pointer.y <= vr.bottom) {
            px = pointer.x;
            py = pointer.y;
        }
        anchor = {
            viewX: px - vr.left,
            viewY: py - vr.top,
            docX: container.scrollLeft + px - vr.left,
            docY: container.scrollTop + py - vr.top
        };
    }
    var current = Number(viewer.currentScale || 1);
    var target = Math.min(4.0, current * 1.1);
    viewer.currentScaleValue = String(target);
    if (container && anchor && before > 0) {
        var after = Number(viewer.currentScale || target);
        var ratio = after / before;
        container.scrollLeft = Math.max(0, anchor.docX * ratio - anchor.viewX);
        container.scrollTop = Math.max(0, anchor.docY * ratio - anchor.viewY);
    }
    return Math.round((Number(viewer.currentScale || 0) || target) * 100);
})()
"""

_JS_ZOOM_OUT = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    var viewer = app.pdfViewer;
    var container = document.getElementById('viewerContainer');
    var pointer = window.__3tLastPointer || null;
    var before = Number(viewer.currentScale || 1);
    var anchor = null;
    if (container) {
        var vr = container.getBoundingClientRect();
        var px = vr.left + vr.width / 2;
        var py = vr.top + vr.height / 2;
        if (pointer && Date.now() - (pointer.timestamp || 0) < 2000 &&
            pointer.x >= vr.left && pointer.x <= vr.right && pointer.y >= vr.top && pointer.y <= vr.bottom) {
            px = pointer.x;
            py = pointer.y;
        }
        anchor = {
            viewX: px - vr.left,
            viewY: py - vr.top,
            docX: container.scrollLeft + px - vr.left,
            docY: container.scrollTop + py - vr.top
        };
    }
    var current = Number(viewer.currentScale || 1);
    var target = Math.max(0.25, current / 1.1);
    viewer.currentScaleValue = String(target);
    if (container && anchor && before > 0) {
        var after = Number(viewer.currentScale || target);
        var ratio = after / before;
        container.scrollLeft = Math.max(0, anchor.docX * ratio - anchor.viewX);
        container.scrollTop = Math.max(0, anchor.docY * ratio - anchor.viewY);
    }
    return Math.round((Number(viewer.currentScale || 0) || target) * 100);
})()
"""

_JS_FIT_PAGE = """
(function() {
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return 0;
    app.pdfViewer.currentScaleValue = '1.0';
    return 100;
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
    var viewer = app.pdfViewer;
    var container = document.getElementById('viewerContainer');
    var before = Number(viewer.currentScale || 1);
    var anchor = null;
    if (container) {{
        var vr = container.getBoundingClientRect();
        var pointer = window.__3tLastPointer || null;
        var px = vr.left + vr.width / 2;
        var py = vr.top + vr.height / 2;
        if (pointer && Date.now() - (pointer.timestamp || 0) < 2000 &&
            pointer.x >= vr.left && pointer.x <= vr.right && pointer.y >= vr.top && pointer.y <= vr.bottom) {{
            px = pointer.x;
            py = pointer.y;
        }}
        anchor = {{
            viewX: px - vr.left,
            viewY: py - vr.top,
            docX: container.scrollLeft + px - vr.left,
            docY: container.scrollTop + py - vr.top
        }};
    }}
    viewer.currentScaleValue = '{scale}';
    if (container && anchor && before > 0) {{
        var after = Number(viewer.currentScale || {scale});
        var ratio = after / before;
        container.scrollLeft = Math.max(0, anchor.docX * ratio - anchor.viewX);
        container.scrollTop = Math.max(0, anchor.docY * ratio - anchor.viewY);
    }}
    return Math.round((Number(viewer.currentScale || 0) || {scale}) * 100);
}})()
"""
    _run_zoom_js(window, wv, js)


@require_webview
def zoom_fit(window, wv):
    _run_zoom_js(window, wv, _JS_FIT_PAGE)
