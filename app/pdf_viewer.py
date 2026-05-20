import os
import sys

from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript, QWebEngineSettings

from app.local_server import LocalPDFJSServer
from packages.pdf_engine import get_pdf_engine
from packages.qt_compat import QtCore, QtWebEngineWidgets, QtWidgets, pyqtSignal

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

# Hide PDF.js built-in toolbar/sidebar; the app provides its own UI.
# Also install find/page hooks so Python can react to PDF.js state.
_PDFJS_UI_AND_HOOKS_JS = """
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

    window.__3tFindState = -1;
    window.__3tCurrentPage = 0;

    function installHooks() {
        var app = window.PDFViewerApplication;
        if (!app || !app.eventBus) {
            setTimeout(installHooks, 200);
            return;
        }
        app.eventBus.on('updatefindcontrolstate', function (data) {
            window.__3tFindState = data.state;
        });
        app.eventBus.on('pagechanging', function (data) {
            window.__3tCurrentPage = data.pageNumber;
        });
    }
    installHooks();
})();
"""

_JS_GET_PAGE = """
(function(){
    var app = window.PDFViewerApplication;
    if (app && app.pdfViewer) return app.pdfViewer.currentPageNumber || 0;
    return window.__3tCurrentPage || 0;
})()
"""

_JS_GET_FIND_STATE = "window.__3tFindState"


class _DebugWebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        print(
            f"[PDFJS][{level.name}] {source_id}:{line_number}: {message}",
            file=sys.stderr,
            flush=True,
        )
        super().javaScriptConsoleMessage(level, message, line_number, source_id)


class PDFViewerWidget(QtWidgets.QWidget):
    """PDF viewer: QWebEngineView + PDF.js served over local HTTP."""

    pdf_loaded = pyqtSignal(dict)
    page_changed = pyqtSignal(int, int)
    error_occurred = pyqtSignal(str)
    find_not_found = pyqtSignal(str)

    def __init__(self, preset: str | None = None, parent=None):
        super().__init__(parent)
        self._preset = preset
        self._path = ""
        self._page_count = 0
        self._current_page = 1
        self._zoom = "page-width"

        self._web_view = QtWebEngineWidgets.QWebEngineView(self)
        self._web_view.setPage(_DebugWebEnginePage(self._web_view))

        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        polyfill = QWebEngineScript()
        polyfill.setName("map-polyfill")
        polyfill.setSourceCode(_MAP_POLYFILL_JS)
        polyfill.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        polyfill.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        polyfill.setRunsOnSubFrames(False)

        ui_hooks = QWebEngineScript()
        ui_hooks.setName("pdfjs-ui-hooks")
        ui_hooks.setSourceCode(_PDFJS_UI_AND_HOOKS_JS)
        ui_hooks.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        ui_hooks.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        ui_hooks.setRunsOnSubFrames(False)

        page_scripts = self._web_view.page().scripts()
        page_scripts.insert(polyfill)
        page_scripts.insert(ui_hooks)

        self._page_timer = QtCore.QTimer(self)
        self._page_timer.setInterval(400)
        self._page_timer.timeout.connect(self._poll_page)

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
        self._page_timer.start()

    def save_pdf(self):
        if not self._path:
            self.error_occurred.emit("Chua mo tep PDF.")

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

    def check_find_result(self, query: str, delay_ms: int = 700):
        def _check():
            self._web_view.page().runJavaScript(
                _JS_GET_FIND_STATE,
                lambda state: self.find_not_found.emit(query) if state == 0 else None,
            )

        QtCore.QTimer.singleShot(delay_ms, _check)

    def findChild(self, child_type, name: str = ""):
        if child_type is QtWebEngineWidgets.QWebEngineView:
            return self._web_view
        return super().findChild(child_type, name)

    def _poll_page(self):
        if not self._path:
            return
        self._web_view.page().runJavaScript(_JS_GET_PAGE, self._on_page_polled)

    def _on_page_polled(self, page_num):
        if not page_num or page_num == self._current_page:
            return
        self._current_page = int(page_num)
        self.page_changed.emit(self._current_page, self._page_count)

    def _load_web_view(self, path: str, *, zoom: str, page: int, pagemode: str | None):
        server = LocalPDFJSServer.get()
        url = server.viewer_url(path, page=page, zoom=zoom, pagemode=pagemode)
        if url:
            self._web_view.load(QtCore.QUrl(url))
        else:
            self._web_view.load(QtCore.QUrl.fromLocalFile(os.path.abspath(path)))
