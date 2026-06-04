import os
import threading

from packages.pdf_engine import get_pdf_engine
from packages.qt_compat import QtCore, QtWebEngineWidgets, QtWidgets, pyqtSignal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineScript

from app.local_server import LocalPDFJSServer
from app.webchannel import register_webchannel_object


class _DebugPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS:{level.name}:{lineNumber}] {message}", flush=True)


class _PageStateBridge(QtCore.QObject):
    stateChanged = pyqtSignal(int, int)

    @QtCore.Slot(int, int)
    def reportState(self, page_number: int, zoom_percent: int):
        self.stateChanged.emit(int(page_number), int(zoom_percent))

# Polyfill for collection helpers added in V8 13.6+ (Chrome 136+).
# Qt WebEngine 6.11 reports Chrome/140 but ships a build without these methods.
_MAP_POLYFILL_JS = """
(function () {
    function install(Ctor) {
        if (!Ctor || !Ctor.prototype) return;
        if (!Ctor.prototype.getOrInsert) {
            Object.defineProperty(Ctor.prototype, 'getOrInsert', {
                configurable: true,
                writable: true,
                value: function (key, defaultValue) {
                    if (!this.has(key)) { this.set(key, defaultValue); }
                    return this.get(key);
                }
            });
        }
        if (!Ctor.prototype.getOrInsertComputed) {
            Object.defineProperty(Ctor.prototype, 'getOrInsertComputed', {
                configurable: true,
                writable: true,
                value: function (key, computeFn) {
                    if (!this.has(key)) { this.set(key, computeFn(key)); }
                    return this.get(key);
                }
            });
        }
    }
    install(Map);
    install(WeakMap);
    if (!Promise.withResolvers) {
        Promise.withResolvers = function () {
            var resolve, reject;
            var promise = new Promise(function (res, rej) {
                resolve = res;
                reject = rej;
            });
            return { promise: promise, resolve: resolve, reject: reject };
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
        '.annotationLayer .signatureWidgetAnnotation,',
        '.annotationLayer .signatureWidgetAnnotation * {',
        '  border: none !important;',
        '  outline: none !important;',
        '  box-shadow: none !important;',
        '  background: transparent !important;',
        '}',
        '.annotationLayer .signatureWidgetAnnotation input,',
        '.annotationLayer .signatureWidgetAnnotation textarea {',
        '  opacity: 0 !important;',
        '  pointer-events: none !important;',
        '}',
    ].join('\\n');
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    // --- Install PDF.js event hooks (retried until eventBus is ready) ---
    window.__3tFindState = -1;   // -1=unknown, 0=notFound, 1=found, 2=wrapped
    window.__3tCurrentPage = 0;

    function readVisiblePage(app) {
        try {
            var viewer = app && app.pdfViewer;
            if (!viewer) return 0;

            var visible = null;
            if (typeof viewer._getVisiblePages === 'function') {
                visible = viewer._getVisiblePages();
            } else if (viewer._visiblePages) {
                visible = viewer._visiblePages;
            } else if (viewer.visiblePages) {
                visible = viewer.visiblePages;
            }

            var views = visible && (visible.views || visible);
            if (views && views.length) {
                var best = views[0];
                var bestPercent = -1;
                for (var i = 0; i < views.length; i++) {
                    var item = views[i];
                    var percent = Number(item.percent || 0);
                    if (percent > bestPercent) {
                        best = item;
                        bestPercent = percent;
                    }
                }
                return parseInt(best.id || (best.view && best.view.id) || 0, 10) || 0;
            }

            if (viewer._location && viewer._location.pageNumber) {
                return parseInt(viewer._location.pageNumber, 10) || 0;
            }
            return parseInt(viewer.currentPageNumber || 0, 10) || 0;
        } catch (_) {
            return 0;
        }
    }

    window.__3tReadVisiblePage = function () {
        return readVisiblePage(window.PDFViewerApplication);
    };

    function ensureQWebChannelScript(callback) {
        if (typeof QWebChannel !== 'undefined') {
            callback();
            return;
        }
        var existing = document.getElementById('__3t_qwebchannel_script');
        if (existing) {
            existing.addEventListener('load', callback, { once: true });
            return;
        }
        var script = document.createElement('script');
        script.id = '__3t_qwebchannel_script';
        script.src = 'qrc:///qtwebchannel/qwebchannel.js';
        script.onload = callback;
        document.head.appendChild(script);
    }

    window.__3tWithBridge = function (name, callback) {
        if (!name || typeof callback !== 'function') return;

        function deliver(channel) {
            try {
                callback((channel && channel.objects && channel.objects[name]) || null);
            } catch (_) {}
        }

        if (window.__3tSharedWebChannel) {
            deliver(window.__3tSharedWebChannel);
            return;
        }

        if (!window.__3tSharedWebChannelCallbacks) {
            window.__3tSharedWebChannelCallbacks = [];
        }
        window.__3tSharedWebChannelCallbacks.push(function(channel) {
            deliver(channel);
        });
        if (window.__3tSharedWebChannelConnecting) return;
        window.__3tSharedWebChannelConnecting = true;

        ensureQWebChannelScript(function () {
            function connectWhenReady() {
                if (!(window.qt && qt.webChannelTransport) || typeof QWebChannel === 'undefined') {
                    setTimeout(connectWhenReady, 50);
                    return;
                }
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.__3tSharedWebChannel = channel;
                    window.__3tSharedWebChannelConnecting = false;
                    var callbacks = window.__3tSharedWebChannelCallbacks || [];
                    window.__3tSharedWebChannelCallbacks = [];
                    callbacks.forEach(function(fn) {
                        try { fn(channel); } catch (_) {}
                    });
                });
            }
            connectWhenReady();
        });
    };

    function collectSelectionPayload() {
        var sel = window.getSelection ? window.getSelection() : null;
        var text = sel ? String(sel.toString() || '') : '';
        var app = window.PDFViewerApplication;
        var viewer = app && app.pdfViewer;
        if (!sel || sel.rangeCount <= 0 || !viewer) return { text: text, rects: [] };

        function pageViewFor(pageNumber) {
            return viewer.getPageView ? viewer.getPageView(pageNumber - 1) : (viewer._pages && viewer._pages[pageNumber - 1]);
        }
        function pageForNode(node) {
            try {
                var el = node && (node.nodeType === 1 ? node : node.parentElement);
                return el && el.closest ? el.closest('.page') : null;
            } catch (_) {
                return null;
            }
        }
        function pageForRect(rect) {
            var cx = (rect.left + rect.right) / 2;
            var cy = (rect.top + rect.bottom) / 2;
            var el = document.elementFromPoint(cx, cy);
            var pageEl = el && el.closest ? el.closest('.page') : null;
            if (pageEl) return pageEl;
            var pages = document.querySelectorAll('.page[data-page-number]');
            var best = null;
            var bestArea = 0;
            for (var i = 0; i < pages.length; i++) {
                var pr = pages[i].getBoundingClientRect();
                if (cx >= pr.left && cx <= pr.right && cy >= pr.top && cy <= pr.bottom) return pages[i];
                var ix = Math.max(0, Math.min(rect.right, pr.right) - Math.max(rect.left, pr.left));
                var iy = Math.max(0, Math.min(rect.bottom, pr.bottom) - Math.max(rect.top, pr.top));
                var area = ix * iy;
                if (area > bestArea) {
                    bestArea = area;
                    best = pages[i];
                }
            }
            return bestArea > 0 ? best : null;
        }

        var out = [];
        for (var r = 0; r < sel.rangeCount; r++) {
            var range = sel.getRangeAt(r);
            var fallbackPage = pageForNode(range.commonAncestorContainer) || pageForNode(range.startContainer);
            var rects = range.getClientRects();
            for (var i = 0; i < rects.length; i++) {
                var cr = rects[i];
                if (!cr || cr.width < 2 || cr.height < 2) continue;
                var pageEl = pageForRect(cr) || fallbackPage;
                if (!pageEl) continue;
                var pageNumber = parseInt(pageEl.getAttribute('data-page-number') || '0', 10);
                var pageView = pageNumber ? pageViewFor(pageNumber) : null;
                if (!pageView || !pageView.viewport) continue;
                var pr = pageEl.getBoundingClientRect();
                var p0 = pageView.viewport.convertToPdfPoint(cr.left - pr.left, cr.top - pr.top);
                var p1 = pageView.viewport.convertToPdfPoint(cr.right - pr.left, cr.bottom - pr.top);
                out.push({
                    page_number: pageNumber,
                    rect: [
                        Math.min(p0[0], p1[0]), Math.min(p0[1], p1[1]),
                        Math.max(p0[0], p1[0]), Math.max(p0[1], p1[1])
                    ]
                });
            }
        }
        return { text: text, rects: out };
    }

    function updateSelectionCache() {
        try {
            var payload = collectSelectionPayload();
            if (payload && payload.rects && payload.rects.length > 0) {
                payload.timestamp = Date.now();
                window.__3tLastSelectionPayload = payload;
            }
        } catch (_) {}
    }

    window.__3tReadSelectionPayload = function () {
        var payload = collectSelectionPayload();
        if (payload && payload.rects && payload.rects.length > 0) {
            payload.timestamp = Date.now();
            window.__3tLastSelectionPayload = payload;
            return payload;
        }
        var cached = window.__3tLastSelectionPayload;
        if (cached && cached.rects && cached.rects.length > 0 && Date.now() - (cached.timestamp || 0) < 15000) {
            return cached;
        }
        return payload || { text: '', rects: [] };
    };

    function currentZoomPercent(app) {
        try {
            var viewer = app && app.pdfViewer;
            return Math.round((viewer && viewer.currentScale || 0) * 100);
        } catch (_) {
            return 0;
        }
    }

    function reportPageState(app, reason) {
        var page = readVisiblePage(app) || window.__3tCurrentPage || 0;
        if (!page) return;
        window.__3tCurrentPage = page;
        var zoom = currentZoomPercent(app);

        function send(bridge) {
            try {
                if (bridge && typeof bridge.reportState === 'function') {
                    bridge.reportState(page, zoom || 0);
                }
            } catch (_) {}
        }

        window.__3tWithBridge('pageStateBridge', function(bridge) {
            window.__3tPageStateBridge = bridge || null;
            send(window.__3tPageStateBridge);
        });
    }

    function reportPageStateSoon(app, reason) {
        reportPageState(app, reason);
        setTimeout(function () { reportPageState(app, reason + ':settled'); }, 80);
    }

    function installHooks() {
        var app = window.PDFViewerApplication;
        if (!app || !app.eventBus) {
            setTimeout(installHooks, 200);
            return;
        }
        if (window.__3tHooksInstalled) return;
        window.__3tHooksInstalled = true;

        var selectionTimer = null;
        var scheduleSelectionCache = function () {
            if (selectionTimer) clearTimeout(selectionTimer);
            [0, 60, 160, 320, 640].forEach(function(delay) {
                setTimeout(updateSelectionCache, delay);
            });
            selectionTimer = setTimeout(function () { selectionTimer = null; }, 700);
        };
        document.addEventListener('selectionchange', scheduleSelectionCache, true);
        document.addEventListener('mouseup', scheduleSelectionCache, true);
        document.addEventListener('pointerup', scheduleSelectionCache, true);
        document.addEventListener('keyup', scheduleSelectionCache, true);

        // Track find state
        app.eventBus.on('updatefindcontrolstate', function (data) {
            window.__3tFindState = data.state;
        });
        // Track page changes from scroll/keyboard inside PDF.js
        app.eventBus.on('pagechanging', function (data) {
            window.__3tCurrentPage = data.pageNumber;
            reportPageState(app, 'pagechanging');
        });
        app.eventBus.on('updateviewarea', function (data) {
            var page = 0;
            if (data && data.location && data.location.pageNumber) {
                page = parseInt(data.location.pageNumber, 10) || 0;
            }
            window.__3tCurrentPage = page || readVisiblePage(app) || window.__3tCurrentPage || 1;
            reportPageState(app, 'updateviewarea');
        });
        app.eventBus.on('scalechanging', function () {
            reportPageStateSoon(app, 'scalechanging');
        });
        app.eventBus.on('scalechanged', function () {
            reportPageStateSoon(app, 'scalechanged');
        });
        var container = document.getElementById('viewerContainer');
        if (container) {
            var scrollTimer = null;
            container.addEventListener('scroll', function () {
                if (scrollTimer) clearTimeout(scrollTimer);
                scrollTimer = setTimeout(function () {
                    scrollTimer = null;
                    window.__3tCurrentPage = readVisiblePage(app) || window.__3tCurrentPage || 1;
                    reportPageState(app, 'scroll');
                }, 50);
            }, { passive: true });
        }
        function clear3TOverlays() {
            window.__3tLastSelectionPayload = null;
            document.querySelectorAll('.reader-pdf-sigfield-marker').forEach(function(el) { el.remove(); });
            var state = window.__readerPdfSignaturePreviewState;
            if (state && state.overlay && state.overlay.parentNode) {
                state.overlay.parentNode.removeChild(state.overlay);
            }
            if (state) {
                state.overlay = null;
                state.handle = null;
                state.pageView = null;
                state.pageNumber = null;
                state.dragging = false;
                state.dragMode = null;
            }
        }
        app.eventBus.on('documentinit', clear3TOverlays);
        app.eventBus.on('pagesinit', clear3TOverlays);
    }
    installHooks();
})();
"""

# Poll JS: returns current page number + zoom percent if PDF.js is ready.
_JS_GET_VIEW_STATE = """
(function(){
    var app = window.PDFViewerApplication;
    if (app && app.pdfViewer) {
        var viewer = app.pdfViewer;
        var page = 0, source = '';

        function readVisiblePageFromViewer() {
            try {
                var visible = null;
                if (typeof viewer._getVisiblePages === 'function') {
                    visible = viewer._getVisiblePages();
                } else if (viewer._visiblePages) {
                    visible = viewer._visiblePages;
                } else if (viewer.visiblePages) {
                    visible = viewer.visiblePages;
                }
                var views = visible && (visible.views || visible);
                if (views && views.length) {
                    var best = views[0];
                    var bestPercent = -1;
                    for (var i = 0; i < views.length; i++) {
                        var item = views[i];
                        var percent = Number(item.percent || 0);
                        if (percent > bestPercent) {
                            best = item;
                            bestPercent = percent;
                        }
                    }
                    return parseInt(best.id || (best.view && best.view.id) || 0, 10) || 0;
                }
            } catch (_) {}
            return 0;
        }

        page = readVisiblePageFromViewer();
        source = page ? 'visible' : '';

        if (!page && typeof window.__3tReadVisiblePage === 'function') {
            page = window.__3tReadVisiblePage() || 0;
            source = page ? 'hook-visible' : '';
        }
        if (!page && window.__3tCurrentPage) {
            page = parseInt(window.__3tCurrentPage, 10) || 0;
            source = page ? 'event' : '';
        }
        if (!page && viewer._location && viewer._location.pageNumber) {
            page = parseInt(viewer._location.pageNumber, 10) || 0;
            source = page ? 'location' : '';
        }
        if (!page && viewer.currentPageNumber) {
            page = parseInt(viewer.currentPageNumber, 10) || 0;
            source = page ? 'current' : '';
        }

        if (!page) {
            var container = document.getElementById('viewerContainer');
            var pages = document.querySelectorAll('.page[data-page-number]');
            if (container && pages && pages.length) {
                var viewport = container.getBoundingClientRect();
                var bestScore = -1;
                for (var j = 0; j < pages.length; j++) {
                    var pageEl = pages[j];
                    var rect = pageEl.getBoundingClientRect();
                    var overlapY = Math.max(0, Math.min(rect.bottom, viewport.bottom) - Math.max(rect.top, viewport.top));
                    var overlapX = Math.max(0, Math.min(rect.right, viewport.right) - Math.max(rect.left, viewport.left));
                    var score = overlapY * Math.max(1, overlapX);
                    if (score > bestScore) {
                        bestScore = score;
                        page = parseInt(pageEl.getAttribute('data-page-number') || '0', 10) || 0;
                    }
                }
                source = page ? 'dom' : '';
            }
        }
        if (page) window.__3tCurrentPage = page;
        return {
            page: page,
            zoom: Math.round((viewer.currentScale || 0) * 100),
            source: source
        };
    }
    return {page: window.__3tCurrentPage || 0, zoom: 0};
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
    zoom_changed = pyqtSignal(int)
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
        self._zoom = "100"
        self._zoom_pct = 0
        self._load_token = 0

        self._web_view = QtWebEngineWidgets.QWebEngineView(self)
        self._web_view.setPage(_DebugPage(self._web_view))
        self._page_state_bridge = _PageStateBridge(self)
        self._page_state_bridge.stateChanged.connect(self._on_bridge_page_state)
        register_webchannel_object(
            self._web_view,
            self,
            "pageStateBridge",
            self._page_state_bridge,
        )

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

        # Timer: polls current page/zoom from PDF.js while a PDF is open.
        self._page_timer = QtCore.QTimer(self)
        self._page_timer.setInterval(150)
        self._page_timer.timeout.connect(self._poll_page)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._web_view)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def load_pdf(self, path: str, zoom: str = "100", page: int | None = None, pagemode: str | None = None):
        self._load_token += 1
        token = self._load_token
        self._path = path
        self._zoom = zoom
        self._current_page = max(1, int(page or 1))
        self._page_count = 0
        self._zoom_pct = 0

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
        self._web_view.page().runJavaScript(_JS_GET_VIEW_STATE, self._on_view_state_polled)

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

    def _on_view_state_polled(self, state):
        if not isinstance(state, dict):
            return
        try:
            page_num = int(state.get("page") or 0)
        except Exception:
            page_num = 0
        try:
            zoom_pct = int(state.get("zoom") or 0)
        except Exception:
            zoom_pct = 0

        if zoom_pct > 0 and zoom_pct != self._zoom_pct:
            self._zoom_pct = zoom_pct
            self.zoom_changed.emit(zoom_pct)

        if not page_num or page_num == self._current_page:
            return
        self._current_page = page_num
        self.page_changed.emit(self._current_page, self._page_count)

    def _on_bridge_page_state(self, page_num: int, zoom_pct: int):
        if not self._path:
            return
        self._on_view_state_polled({
            "page": page_num,
            "zoom": zoom_pct,
        })

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
