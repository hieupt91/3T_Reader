from app.actions._guard import require_document, require_webview


def _apply_pdfjs_zoom(window, wv, percent: int):
    percent = max(25, min(400, int(percent)))
    scale = percent / 100
    js = f"""
(function() {{
  if (window.PDFViewerApplication && PDFViewerApplication.pdfViewer) {{
    PDFViewerApplication.pdfViewer.currentScale = {scale};
  }}
}})();
"""
    wv.setZoomFactor(1.0)
    wv.page().runJavaScript(js)
    window.zoom_spin.setValue(percent)


def _adjust_zoom(window, wv, delta_percent: int):
    _apply_pdfjs_zoom(window, wv, window.zoom_spin.value() + delta_percent)


@require_webview
def zoom_in(window, wv):
    _adjust_zoom(window, wv, +10)


@require_webview
def zoom_out(window, wv):
    _adjust_zoom(window, wv, -10)


@require_webview
def apply_zoom(window, wv):
    _apply_pdfjs_zoom(window, wv, window.zoom_spin.value())


@require_webview
def reset_zoom(window, wv):
    _apply_pdfjs_zoom(window, wv, 100)


@require_document()
def zoom_fit(window):
    wv = window._get_webview()
    if not wv:
        return
    js = """
(function() {
  if (window.PDFViewerApplication && PDFViewerApplication.pdfViewer) {
    PDFViewerApplication.pdfViewer.currentScaleValue = "page-width";
  }
})();
"""
    wv.setZoomFactor(1.0)
    wv.page().runJavaScript(js)
    window.zoom_spin.setValue(100)
