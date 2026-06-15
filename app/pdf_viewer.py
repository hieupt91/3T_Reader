import json
import os
import threading
from pathlib import Path

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


class _SignatureInfoBridge(QtCore.QObject):
    signatureClicked = pyqtSignal(int, str)

    @QtCore.Slot(int, str)
    def showSignatureInfo(self, page_number: int, field_name: str):
        self.signatureClicked.emit(int(page_number), str(field_name or ""))

# Polyfill for collection helpers added in V8 13.6+ (Chrome 136+).
# Qt WebEngine 6.11 reports Chrome/140 but ships a build without these methods.
# Loaded from assets/js/polyfill.js — single source of truth shared with local_server.
from app.js_loader import load_js as _load_js
_MAP_POLYFILL_JS = _load_js("polyfill.js")

# Load the same PDF.js override CSS as a DocumentReady script so the viewer
# gets a deterministic stylesheet injection even before page-level callbacks run.
_PDFJS_OVERRIDES_CSS = (
    Path(__file__).resolve().parent.parent / "assets" / "css" / "pdfjs_overrides.css"
).read_text(encoding="utf-8")
_PDFJS_OVERRIDES_JS = f"""
(function () {{
    var style = document.createElement('style');
    style.setAttribute('data-3t-pdfjs-overrides', '1');
    style.textContent = {json.dumps(_PDFJS_OVERRIDES_CSS)};
    document.head.appendChild(style);
}})();
"""

# Hide PDF.js built-in toolbar/sidebar — the app provides its own UI.
# Also installs find-state listener so Python can detect "not found".
# Loaded from assets/js/pdfjs_ui_hooks.js
_PDFJS_UI_AND_HOOKS_JS = _load_js("pdfjs_ui_hooks.js")

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
    signature_clicked = pyqtSignal(int, str)
    context_menu_requested = pyqtSignal(QtCore.QPoint)

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
        self._web_view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._web_view.customContextMenuRequested.connect(self.context_menu_requested)
        self._web_view.setPage(_DebugPage(self._web_view))
        self._page_state_bridge = _PageStateBridge(self)
        self._page_state_bridge.stateChanged.connect(self._on_bridge_page_state)
        register_webchannel_object(
            self._web_view,
            self,
            "pageStateBridge",
            self._page_state_bridge,
        )
        self._signature_info_bridge = _SignatureInfoBridge(self)
        self._signature_info_bridge.signatureClicked.connect(self.signature_clicked)
        register_webchannel_object(
            self._web_view,
            self,
            "signatureInfoBridge",
            self._signature_info_bridge,
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

        pdfjs_overrides = QWebEngineScript()
        pdfjs_overrides.setName("pdfjs-overrides")
        pdfjs_overrides.setSourceCode(_PDFJS_OVERRIDES_JS)
        pdfjs_overrides.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        pdfjs_overrides.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        pdfjs_overrides.setRunsOnSubFrames(False)

        # UI + hooks: after DOM ready
        ui_hooks = QWebEngineScript()
        ui_hooks.setName("pdfjs-ui-hooks")
        ui_hooks.setSourceCode(_PDFJS_UI_AND_HOOKS_JS)
        ui_hooks.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        ui_hooks.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        ui_hooks.setRunsOnSubFrames(False)

        page_scripts = self._web_view.page().scripts()
        page_scripts.insert(polyfill)
        page_scripts.insert(pdfjs_overrides)
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

    def reload_soft(self, path: str, zoom: str = "100", page: int | None = None, ops_json: str = "[]", erase_json: str = "[]"):
        self._load_token += 1
        token = self._load_token
        self._path = path
        self._zoom = zoom
        if page:
            self._current_page = max(1, int(page))
        self._page_count = 0
        
        server = LocalPDFJSServer.get()
        abs_path = server.register_pdf(path)
        import urllib.parse
        encoded_path = urllib.parse.quote(abs_path)
        try:
            cache_key = str(os.stat(abs_path).st_mtime_ns)
        except OSError:
            cache_key = "0"
        pdf_url = f"http://127.0.0.1:{server._port}/pdf?p={encoded_path}&v={cache_key}"
        
        js = f"""
        (function() {{
            if (window.PDFViewerApplication && window.PDFViewerApplication.pdfViewer) {{
                var app = window.PDFViewerApplication;
                var currentScroll = app.pdfViewer.container.scrollTop;
                var currentLeft = app.pdfViewer.container.scrollLeft;
                
                var ops = {ops_json};
                var eraseBoxes = {erase_json};
                
                var freezeDiv = document.createElement('div');
                freezeDiv.id = '__3t_freeze';
                freezeDiv.style.cssText = 'position:fixed;inset:0;z-index:999999;background:#e4e4e4;pointer-events:none;overflow:hidden;';
                
                var pages = document.querySelectorAll('.page');
                pages.forEach(function(p) {{
                    var pageNum = parseInt(p.getAttribute('data-page-number'));
                    var pageView = app.pdfViewer.getPageView ? app.pdfViewer.getPageView(pageNum - 1) : null;
                    if (!pageView) pageView = app.pdfViewer._pages ? app.pdfViewer._pages[pageNum - 1] : null;
                    var c = p.querySelector('canvas');
                    if (c && pageView && pageView.viewport) {{
                        var clone = document.createElement('canvas');
                        clone.width = c.width;
                        clone.height = c.height;
                        var ctx = clone.getContext('2d');
                        ctx.drawImage(c, 0, 0);
                        
                        // Erase old object boxes
                        if (eraseBoxes && eraseBoxes.length > 0) {{
                            eraseBoxes.forEach(function(eb) {{
                                if (eb.page_number === pageNum) {{
                                    var vp = pageView.viewport;
                                    var coords = vp.convertToViewportRectangle([eb.box[0], eb.box[1], eb.box[2], eb.box[3]]);
                                    var bx = Math.min(coords[0], coords[2]);
                                    var by = Math.min(coords[1], coords[3]);
                                    var bw = Math.abs(coords[2] - coords[0]);
                                    var bh = Math.abs(coords[3] - coords[1]);
                                    // Scale to canvas pixel ratio
                                    var ratioX = c.width / c.clientWidth;
                                    var ratioY = c.height / c.clientHeight;
                                    ctx.clearRect(bx * ratioX - 2, by * ratioY - 2, bw * ratioX + 4, bh * ratioY + 4);
                                }}
                            }});
                        }}
                        
                        var rect = p.getBoundingClientRect();
                        clone.style.cssText = 'position:absolute;left:' + rect.left + 'px;top:' + rect.top + 'px;width:' + rect.width + 'px;height:' + rect.height + 'px;background:#fff;box-shadow:0 2px 5px rgba(0,0,0,0.2);';
                        freezeDiv.appendChild(clone);
                    }}
                }});
                
                // Draw NEW ops on top of freezeDiv
                if (ops && ops.length > 0) {{
                    ops.forEach(function(op) {{
                        var pageEl = document.querySelector('.page[data-page-number="' + op.page_number + '"]');
                        if (!pageEl) return;
                        var pageView = app.pdfViewer.getPageView ? app.pdfViewer.getPageView(op.page_number - 1) : null;
                        if (!pageView) pageView = app.pdfViewer._pages ? app.pdfViewer._pages[op.page_number - 1] : null;
                        if (!pageView || !pageView.viewport) return;
                        var vp = pageView.viewport;
                        var coords = vp.convertToViewportRectangle([op.box[0], op.box[1], op.box[2], op.box[3]]);
                        var bx = Math.min(coords[0], coords[2]);
                        var by = Math.min(coords[1], coords[3]);
                        var bw = Math.abs(coords[2] - coords[0]);
                        var bh = Math.abs(coords[3] - coords[1]);
                        
                        var pRect = pageEl.getBoundingClientRect();
                        
                        var ov = document.createElement('div');
                        var pad = 13;
                        ov.style.cssText = 'position:absolute;left:'+(pRect.left+bx-pad)+'px;top:'+(pRect.top+by-pad)+'px;width:'+(bw+2*pad)+'px;height:'+(bh+2*pad)+'px;z-index:999999;pointer-events:none;transform-origin:'+(pad+bw/2)+'px '+(pad+bh/2)+'px;';
                        if (op.rotation) ov.style.transform = 'rotate('+op.rotation+'deg)';
                        
                        var box = document.createElement('div');
                        box.style.cssText = 'position:absolute;left:'+pad+'px;top:'+pad+'px;width:'+bw+'px;height:'+bh+'px;';
                        
                        if (op.type === 'text') {{
                            var txt = document.createElement('div');
                            txt.textContent = op.text || '';
                            var c = op.font_color || [0,0,0];
                            var r = Math.round(c[0]*255), g = Math.round(c[1]*255), b = Math.round(c[2]*255);
                            txt.style.cssText = 'width:100%;height:100%;display:flex;align-items:flex-start;justify-content:flex-start;'
                                + 'color:rgb('+r+','+g+','+b+');'
                                + 'font-weight:'+(op.bold?'bold':'normal')+';'
                                + 'text-decoration:'+(op.underline?'underline':'none')+';'
                                + 'font-family:sans-serif;white-space:pre-wrap;overflow:hidden;';
                            var fs = (op.font_size || 14) * (vp.scale || 1.0) * 1.333;
                            txt.style.fontSize = fs + 'px';
                            txt.style.lineHeight = '1.15';
                            box.appendChild(txt);
                        }} else if (op.type === 'image' && op.image_path) {{
                            var img = document.createElement('img');
                            img.src = 'file://' + op.image_path;
                            img.style.cssText = 'width:100%;height:100%;object-fit:contain;opacity:0.85;';
                            box.appendChild(img);
                        }}
                        ov.appendChild(box);
                        freezeDiv.appendChild(ov);
                    }});
                }}
                

                
                var textOv = window.__3TTextState ? window.__3TTextState.overlay : null;
                if (textOv && textOv.parentNode) {{
                    textOv.style.zIndex = '9999999';
                }}
                
                document.body.appendChild(freezeDiv);
                
                app.open({url: '{pdf_url}'}).then(function() {{
                    var container = app.pdfViewer.container;
                    container.scrollTop = currentScroll;
                    container.scrollLeft = currentLeft;
                    
                    function removeFreeze() {{
                        if (freezeDiv.parentNode) {{
                            freezeDiv.style.transition = 'opacity 0.2s ease-out';
                            freezeDiv.style.opacity = '0';
                            setTimeout(function() {{
                                if (freezeDiv.parentNode) freezeDiv.parentNode.removeChild(freezeDiv);
                            }}, 200);
                        }}
                    }}
                    
                    function onRender() {{
                        app.pdfViewer.eventBus.off('pagerendered', onRender);
                        setTimeout(removeFreeze, 150);
                    }}
                    app.pdfViewer.eventBus.on('pagerendered', onRender);
                    
                    setTimeout(removeFreeze, 2500);
                }}).catch(function(e) {{ 
                    console.error('Soft reload error:', e); 
                    if (freezeDiv.parentNode) freezeDiv.parentNode.removeChild(freezeDiv);
                }});
            }}
        }})();
        """
        self._web_view.page().runJavaScript(js)
        self.pdf_loaded.emit({"filename": os.path.basename(path), "path": path})
        self.page_changed.emit(self._current_page, self._page_count)
        self._page_timer.start()
        self._load_page_count_async(token, path)

    def update_ops(self, ops_json: str):
        js = f"""
        (function() {{
            window.__3tOps = {ops_json};
            
            function renderOps() {{
                if (!window.__3tOps) return;
                var app = window.PDFViewerApplication;
                if (!app || !app.pdfViewer) return;
                
                document.querySelectorAll('.__3t-op-overlay').forEach(function(el) {{ el.remove(); }});
                
                window.__3tOps.forEach(function(op) {{
                    var pageEl = document.querySelector('.page[data-page-number="' + op.page_number + '"]');
                    if (!pageEl) return;
                    var pageView = app.pdfViewer.getPageView ? app.pdfViewer.getPageView(op.page_number - 1) : null;
                    if (!pageView) pageView = app.pdfViewer._pages ? app.pdfViewer._pages[op.page_number - 1] : null;
                    if (!pageView || !pageView.viewport) return;
                    
                    var vp = pageView.viewport;
                    var coords = vp.convertToViewportRectangle([op.box[0], op.box[1], op.box[2], op.box[3]]);
                    var bx = Math.min(coords[0], coords[2]);
                    var by = Math.min(coords[1], coords[3]);
                    var bw = Math.abs(coords[2] - coords[0]);
                    var bh = Math.abs(coords[3] - coords[1]);
                    
                    var ov = document.createElement('div');
                    ov.className = '__3t-op-overlay';
                    var pad = 0;
                    ov.style.cssText = 'position:absolute;left:'+(bx-pad)+'px;top:'+(by-pad)+'px;width:'+(bw+2*pad)+'px;height:'+(bh+2*pad)+'px;z-index:40;pointer-events:none;transform-origin:'+(pad+bw/2)+'px '+(pad+bh/2)+'px;';
                    if (op.rotation) ov.style.transform = 'rotate('+op.rotation+'deg)';
                    
                    if (op.type === 'rect') {{
                        ov.style.background = '#ffffff';
                    }} else if (op.type === 'text') {{
                        ov.style.display = 'flex';
                        ov.style.alignItems = 'flex-start';
                        ov.style.justifyContent = 'flex-start';
                        var txt = document.createElement('div');
                        txt.textContent = op.text || '';
                        var c = op.font_color || [0,0,0];
                        var r = Math.round(c[0]*255), g = Math.round(c[1]*255), b = Math.round(c[2]*255);
                        txt.style.cssText = 'width:100%;height:100%;display:flex;align-items:flex-start;justify-content:flex-start;'
                            + 'color:rgb('+r+','+g+','+b+');'
                            + 'font-weight:'+(op.bold?'bold':'normal')+';'
                            + 'text-decoration:'+(op.underline?'underline':'none')+';'
                            + 'font-family:sans-serif;white-space:pre-wrap;overflow:hidden;';
                        var fs = (op.font_size || 14) * (vp.scale || 1.0) * 1.333;
                        txt.style.fontSize = fs + 'px';
                        txt.style.lineHeight = '1.15';
                        ov.appendChild(txt);
                    }} else if (op.type === 'image' && op.image_path) {{
                        var img = document.createElement('img');
                        img.src = op.image_data_url || ('file://' + op.image_path);
                        img.style.cssText = 'width:100%;height:100%;object-fit:contain;';
                        ov.appendChild(img);
                    }}
                    pageEl.appendChild(ov);
                }});
            }}
            
            renderOps();
            
            if (!window.__3tOpsHooked) {{
                window.__3tOpsHooked = true;
                if (window.PDFViewerApplication && window.PDFViewerApplication.pdfViewer) {{
                    window.PDFViewerApplication.pdfViewer.eventBus.on('pagerendered', renderOps);
                    window.PDFViewerApplication.pdfViewer.eventBus.on('scalechanged', function() {{ setTimeout(renderOps, 50); }});
                }}
            }}
        }})();
        """
        self._web_view.page().runJavaScript(js)

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
