import os
import threading

from packages.pdf_engine import get_pdf_engine
from packages.qt_compat import QtCore, QtWebEngineWidgets, QtWidgets, pyqtSignal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineScript

from app.local_server import LocalPDFJSServer


class _DebugPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS:{level.name}:{lineNumber}] {message}", flush=True)

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
# Also installs find-state listener so Python can detect "not found".
_PDFJS_UI_AND_HOOKS_JS = """
(function () {
    // --- Hide built-in chrome ---
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

    // --- Install PDF.js event hooks (retried until eventBus is ready) ---
    window.__3tFindState = -1;   // -1=unknown, 0=notFound, 1=found, 2=wrapped
    window.__3tCurrentPage = 0;

    function installHooks() {
        var app = window.PDFViewerApplication;
        if (!app || !app.eventBus) {
            setTimeout(installHooks, 200);
            return;
        }
        // Track find state
        app.eventBus.on('updatefindcontrolstate', function (data) {
            window.__3tFindState = data.state;
        });
        // Track page changes from scroll/keyboard inside PDF.js
        app.eventBus.on('pagechanging', function (data) {
            window.__3tCurrentPage = data.pageNumber;
        });
    }
    installHooks();
})();
"""

# Poll JS: returns current page number (0 if PDF.js not ready)
_JS_GET_PAGE = """
(function(){
    var app = window.PDFViewerApplication;
    if (app && app.pdfViewer) return app.pdfViewer.currentPageNumber || 0;
    return window.__3tCurrentPage || 0;
})()
"""

# Poll JS: returns find state (-1/0/1/2)
_JS_GET_FIND_STATE = "window.__3tFindState"


class PDFViewerWidget(QtWidgets.QWidget):
    """PDF viewer: QWebEngineView + PDF.js served over local HTTP.

    ES modules (used by PDF.js 4+) cannot load from file:// in QtWebEngine,
    so we serve PDF.js via LocalPDFJSServer on 127.0.0.1.
    """

    pdf_loaded = pyqtSignal(dict)
    page_changed = pyqtSignal(int, int)
    page_ready = pyqtSignal()
    error_occurred = pyqtSignal(str)
    find_not_found = pyqtSignal(str)   # emitted with the query when PDF.js reports notFound
    page_count_ready = pyqtSignal(int, str, int, str)  # token, path, page_count, error

    def __init__(self, preset: str | None = None, parent=None):
        super().__init__(parent)
        self._preset = preset
        self._path = ""
        self._page_count = 0
        self._current_page = 1
        self._zoom = "page-width"
        self._load_token = 0

        self._web_view = QtWebEngineWidgets.QWebEngineView(self)
        self._web_view.setPage(_DebugPage(self._web_view))

        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        # Polyfill: before PDF.js modules load
        polyfill = QWebEngineScript()
        polyfill.setName("map-polyfill")
        polyfill.setSourceCode(_MAP_POLYFILL_JS)
        polyfill.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        polyfill.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        polyfill.setRunsOnSubFrames(False)

        # UI + hooks: after DOM ready
        ui_hooks = QWebEngineScript()
        ui_hooks.setName("pdfjs-ui-hooks")
        ui_hooks.setSourceCode(_PDFJS_UI_AND_HOOKS_JS)
        ui_hooks.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        ui_hooks.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        ui_hooks.setRunsOnSubFrames(False)

        page_scripts = self._web_view.page().scripts()
        page_scripts.insert(polyfill)
        page_scripts.insert(ui_hooks)

        self._web_view.loadFinished.connect(lambda ok: self.page_ready.emit() if ok else None)
        self.page_count_ready.connect(self._on_page_count_ready)

        # Timer: polls current page from PDF.js every 400 ms while a PDF is open
        self._page_timer = QtCore.QTimer(self)
        self._page_timer.setInterval(400)
        self._page_timer.timeout.connect(self._poll_page)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._web_view)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def load_pdf(self, path: str, zoom: str = "page-width", page: int | None = None, pagemode: str | None = None):
        self._load_token += 1
        token = self._load_token
        self._path = path
        self._zoom = zoom
        self._current_page = max(1, int(page or 1))
        self._page_count = 0

        self._load_web_view(path, zoom=zoom, page=self._current_page, pagemode=pagemode)
        self.pdf_loaded.emit({"filename": os.path.basename(path), "path": path})
        self.page_changed.emit(self._current_page, self._page_count)
        self._page_timer.start()
        self._load_page_count_async(token, path)

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

    def check_find_result(self, query: str, delay_ms: int = 700):
        """After dispatching a find event, wait delay_ms then emit find_not_found if state==0."""
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

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _poll_page(self):
        if not self._path:
            return
        self._web_view.page().runJavaScript(_JS_GET_PAGE, self._on_page_polled)

    def _load_page_count_async(self, token: int, path: str):
        def _worker():
            try:
                count = get_pdf_engine().page_count(path)
                err = ""
            except Exception as exc:
                count = 0
                err = str(exc)
            self.page_count_ready.emit(token, path, count, err)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_page_polled(self, page_num):
        if not page_num or page_num == self._current_page:
            return
        self._current_page = int(page_num)
        self.page_changed.emit(self._current_page, self._page_count)

    def _on_page_count_ready(self, token: int, path: str, page_count: int, error: str):
        if token != self._load_token or path != self._path:
            return
        if error:
            self.error_occurred.emit(error)
            return
        self._page_count = max(0, int(page_count))
        self.page_changed.emit(self._current_page, self._page_count)

    def _load_web_view(self, path: str, *, zoom: str, page: int, pagemode: str | None):
        server = LocalPDFJSServer.get()
        url = server.viewer_url(path, page=page, zoom=zoom, pagemode=pagemode)
        if url:
            self._web_view.load(QtCore.QUrl(url))
        else:
            self._web_view.load(QtCore.QUrl.fromLocalFile(os.path.abspath(path)))
