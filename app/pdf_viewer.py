import os

from packages.pdf_engine import get_pdf_engine
from packages.qt_compat import QtCore, QtWebEngineWidgets, QtWidgets, pyqtSignal
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEngineScript

from app.local_server import LocalPDFJSServer

# Polyfill for Map methods added in V8 13.6+ (Chrome 136+).
# Qt WebEngine 6.11 reports Chrome/140 but ships a build without these methods.
_MAP_POLYFILL_JS = """
(function () {
    if (!Map.prototype.getOrInsert) {
        Map.prototype.getOrInsert = function (key, defaultValue) {
            if (!this.has(key)) { this.set(key, defaultValue); }
            return this.get(key);
        };
    }
    if (!Map.prototype.getOrInsertComputed) {
        Map.prototype.getOrInsertComputed = function (key, computeFn) {
            if (!this.has(key)) { this.set(key, computeFn(key)); }
            return this.get(key);
        };
    }
})();
"""

# Hide PDF.js built-in toolbar/sidebar — the app provides its own UI.
# Injected at DocumentReady so DOM elements exist when the style is applied.
_HIDE_PDFJS_UI_JS = """
(function () {
    var css = [
        '#toolbarContainer { display: none !important; }',
        '#loadingBar { display: none !important; }',
        '#viewsManager { display: none !important; }',
        '#mainContainer { top: 0 !important; }',
        '#viewerContainer { top: 0 !important; left: 0 !important; }',
        'body { background-color: #0f0f13 !important; }',
        '#viewer .page {',
        '  border: none !important;',
        '  box-shadow: 0 4px 24px rgba(0,0,0,.5) !important;',
        '  margin: 16px auto !important;',
        '  border-radius: 4px !important;',
        '}',
    ].join('\\n');
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
})();
"""


class PDFViewerWidget(QtWidgets.QWidget):
    """PDF viewer: QWebEngineView + PDF.js served over local HTTP.

    ES modules (used by PDF.js 4+) cannot load from file:// in QtWebEngine,
    so we serve PDF.js via LocalPDFJSServer on 127.0.0.1.
    """

    pdf_loaded = pyqtSignal(dict)
    page_changed = pyqtSignal(int, int)
    error_occurred = pyqtSignal(str)

    def __init__(self, preset: str | None = None, parent=None):
        super().__init__(parent)
        self._preset = preset
        self._path = ""
        self._page_count = 0
        self._current_page = 1
        self._zoom = "page-width"

        self._web_view = QtWebEngineWidgets.QWebEngineView(self)

        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        # Polyfill: runs before PDF.js modules so missing Map methods are available
        polyfill = QWebEngineScript()
        polyfill.setName("map-polyfill")
        polyfill.setSourceCode(_MAP_POLYFILL_JS)
        polyfill.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        polyfill.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        polyfill.setRunsOnSubFrames(False)

        # UI hide: runs at DocumentReady (DOM exists) to strip PDF.js built-in chrome
        hide_ui = QWebEngineScript()
        hide_ui.setName("pdfjs-hide-ui")
        hide_ui.setSourceCode(_HIDE_PDFJS_UI_JS)
        hide_ui.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        hide_ui.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        hide_ui.setRunsOnSubFrames(False)

        page_scripts = self._web_view.page().scripts()
        page_scripts.insert(polyfill)
        page_scripts.insert(hide_ui)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._web_view)

    def load_pdf(self, path: str, zoom: str = "page-width", page: int | None = None, pagemode: str | None = None):
        self._path = path
        self._zoom = zoom
        self._current_page = max(1, int(page or 1))

        try:
            self._page_count = get_pdf_engine().page_count(path)
        except Exception as exc:
            self._page_count = 0
            self.error_occurred.emit(str(exc))

        self._load_web_view(path, zoom=zoom, page=self._current_page, pagemode=pagemode)
        self.pdf_loaded.emit({"filename": os.path.basename(path), "path": path})
        self.page_changed.emit(self._current_page, self._page_count)

    def save_pdf(self):
        if not self._path:
            self.error_occurred.emit("Chưa mở tệp PDF.")

    def goto_page(self, page: int):
        self._current_page = max(1, min(int(page), max(1, self._page_count)))
        js = f"""
(function() {{
  if (window.PDFViewerApplication && PDFViewerApplication.pdfViewer) {{
    PDFViewerApplication.pdfViewer.currentPageNumber = {self._current_page};
  }}
}})();
"""
        self._web_view.page().runJavaScript(js)
        self.page_changed.emit(self._current_page, self._page_count)

    def get_current_page(self) -> int:
        return self._current_page

    def get_page_count(self) -> int:
        return self._page_count

    def findChild(self, child_type, name: str = ""):
        if child_type is QtWebEngineWidgets.QWebEngineView:
            return self._web_view
        return super().findChild(child_type, name)

    def _load_web_view(self, path: str, *, zoom: str, page: int, pagemode: str | None):
        server = LocalPDFJSServer.get()
        url = server.viewer_url(path, page=page, zoom=zoom, pagemode=pagemode)
        if url:
            self._web_view.load(QtCore.QUrl(url))
        else:
            # Fallback: direct file load (no PDF.js, limited support)
            self._web_view.load(QtCore.QUrl.fromLocalFile(os.path.abspath(path)))
