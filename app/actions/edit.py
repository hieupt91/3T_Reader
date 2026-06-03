import os
import shutil
import tempfile
import uuid

from packages.qt_compat.QtCore import QObject, QEventLoop, QTimer, pyqtSignal, pyqtSlot
from packages.qt_compat.QtWebChannel import QWebChannel
from packages.qt_compat.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
)

from app.actions.file import open_file
from app.actions._guard import require_document
from app.actions._pdf_save import atomic_copy_file, reload_document
from app.dialogs import show_warning
from packages.pdf_engine import get_pdf_engine

A4_WIDTH_PT = 595
A4_HEIGHT_PT = 842

AREA_PICK_SCRIPT = r"""
(function () {
    if (window.__readerPdfAreaPickInstalled) {
        return;
    }
    window.__readerPdfAreaPickInstalled = true;

    function startPick(bridge) {
        let dragState = null;
        let overlay = null;

        function cleanup() {
            document.removeEventListener('mousedown', onMouseDown, true);
            document.removeEventListener('mousemove', onMouseMove, true);
            document.removeEventListener('mouseup', onMouseUp, true);
            window.removeEventListener('keydown', onKeyDown, true);
            document.body.style.cursor = '';
            clearOverlay();
            dragState = null;
        }

        function clearOverlay() {
            if (overlay && overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
            overlay = null;
        }

        function resolvePageFromEvent(event) {
            const candidates = [];
            const directTarget = event.target && event.target.nodeType === 1
                ? event.target
                : (event.target && event.target.parentElement);
            if (directTarget) {
                candidates.push(directTarget);
            }
            if (document.elementsFromPoint) {
                try {
                    const hits = document.elementsFromPoint(event.clientX, event.clientY) || [];
                    for (const el of hits) {
                        candidates.push(el);
                    }
                } catch (_err) {}
            } else if (document.elementFromPoint) {
                try {
                    const hit = document.elementFromPoint(event.clientX, event.clientY);
                    if (hit) {
                        candidates.push(hit);
                    }
                } catch (_err) {}
            }

            for (const candidate of candidates) {
                if (candidate && candidate.closest) {
                    const page = candidate.closest('.page');
                    if (page && page.dataset && page.dataset.pageNumber) {
                        return page;
                    }
                }
            }
            return null;
        }

        function cancel() {
            cleanup();
            try { bridge.cancelPick(); } catch (_err) {}
        }

        function onMouseDown(event) {
            const page = resolvePageFromEvent(event);
            if (!page) {
                return;
            }
            const pdfViewer = window.PDFViewerApplication && PDFViewerApplication.pdfViewer;
            if (!pdfViewer) {
                return;
            }
            const pageNumber = parseInt(page.dataset.pageNumber, 10);
            const pageView = pdfViewer.getPageView
                ? pdfViewer.getPageView(pageNumber - 1)
                : (pdfViewer._pages && pdfViewer._pages[pageNumber - 1]);
            if (!pageView || !pageView.viewport || !pageView.pdfPage) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            document.body.style.cursor = 'crosshair';
            const rect = page.getBoundingClientRect();
            const startX = Math.max(0, Math.min(event.clientX - rect.left, page.clientWidth));
            const startY = Math.max(0, Math.min(event.clientY - rect.top, page.clientHeight));

            dragState = {
                page,
                pageView,
                pageNumber,
                rect,
                startX,
                startY,
                curX: startX,
                curY: startY,
            };

            if (!overlay) {
                overlay = document.createElement('div');
                overlay.style.position = 'absolute';
                overlay.style.border = '2px dashed #0B84F3';
                overlay.style.background = 'rgba(11, 132, 243, 0.15)';
                overlay.style.pointerEvents = 'none';
                overlay.style.zIndex = '10000';
                overlay.style.boxSizing = 'border-box';
                page.appendChild(overlay);
            } else if (overlay.parentNode !== page) {
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                page.appendChild(overlay);
            }
            overlay.style.left = `${startX}px`;
            overlay.style.top = `${startY}px`;
            overlay.style.width = '1px';
            overlay.style.height = '1px';
        }

        function onMouseMove(event) {
            if (!dragState || !overlay) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            const x = Math.max(0, Math.min(event.clientX - dragState.rect.left, dragState.page.clientWidth));
            const y = Math.max(0, Math.min(event.clientY - dragState.rect.top, dragState.page.clientHeight));
            dragState.curX = x;
            dragState.curY = y;

            const left = Math.min(dragState.startX, x);
            const top = Math.min(dragState.startY, y);
            const width = Math.max(1, Math.abs(x - dragState.startX));
            const height = Math.max(1, Math.abs(y - dragState.startY));

            overlay.style.left = `${left}px`;
            overlay.style.top = `${top}px`;
            overlay.style.width = `${width}px`;
            overlay.style.height = `${height}px`;
        }

        function onMouseUp(event) {
            if (!dragState) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            const x2 = Math.max(0, Math.min(event.clientX - dragState.rect.left, dragState.page.clientWidth));
            const y2 = Math.max(0, Math.min(event.clientY - dragState.rect.top, dragState.page.clientHeight));
            const x1 = dragState.startX;
            const y1 = dragState.startY;

            const minX = Math.min(x1, x2);
            const minY = Math.min(y1, y2);
            const maxX = Math.max(x1, x2);
            const maxY = Math.max(y1, y2);

            const p1 = dragState.pageView.viewport.convertToPdfPoint(minX, minY);
            const p2 = dragState.pageView.viewport.convertToPdfPoint(maxX, maxY);

            const left = Math.min(p1[0], p2[0]);
            const right = Math.max(p1[0], p2[0]);
            const bottom = Math.min(p1[1], p2[1]);
            const top = Math.max(p1[1], p2[1]);

            const pickedPageNumber = dragState.pageNumber;
            cleanup();

            try {
                bridge.reportArea(pickedPageNumber, left, bottom, right, top);
            } catch (_err) {}
        }

        function onKeyDown(event) {
            if (event.key === 'Escape') {
                cancel();
            }
        }

        document.addEventListener('mousedown', onMouseDown, true);
        document.addEventListener('mousemove', onMouseMove, true);
        document.addEventListener('mouseup', onMouseUp, true);
        window.addEventListener('keydown', onKeyDown, true);
    }

    function attachBridge() {
        if (typeof QWebChannel === 'undefined') {
            var script = document.createElement('script');
            script.src = 'qrc:///qtwebchannel/qwebchannel.js';
            script.onload = attachBridge;
            document.head.appendChild(script);
            return;
        }

        if (!(window.qt && qt.webChannelTransport)) {
            setTimeout(attachBridge, 50);
            return;
        }

        // Reuse cached bridge from previous pick in the same channel session.
        // This avoids a second async QWebChannel handshake for Move's second pick.
        if (window.__3tAreaPickBridgeCache) {
            startPick(window.__3tAreaPickBridgeCache);
            return;
        }

        new QWebChannel(qt.webChannelTransport, function (channel) {
            var b = channel.objects.areaPickBridge;
            if (!b) {
                return;
            }
            window.__3tAreaPickBridgeCache = b;
            startPick(b);
        });
    }

    attachBridge();
})();
"""

_CLEAR_BRIDGE_CACHE_JS = "(function(){window.__3tAreaPickBridgeCache=null;window.__readerPdfAreaPickInstalled=false;})();"

# Show blue dashed bounding box at the op's actual PDF coordinates.
# Args (Python % formatting): pageNum, pdfLeft, pdfBottom, pdfRight, pdfTop
_SHOW_SELECTION_OVERLAY_JS = """(function(pageNum, pdfLeft, pdfBottom, pdfRight, pdfTop) {
    var existing = document.getElementById('__3tSelectionBox');
    if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return;
    var pdfViewer = app.pdfViewer;
    var pageView = pdfViewer.getPageView
        ? pdfViewer.getPageView(pageNum - 1)
        : (pdfViewer._pages && pdfViewer._pages[pageNum - 1]);
    if (!pageView || !pageView.viewport || !pageView.div) return;
    var vp = pageView.viewport;
    var r = vp.convertToViewportRectangle([pdfLeft, pdfBottom, pdfRight, pdfTop]);
    var pageEl = pageView.div;
    var el = document.createElement('div');
    el.id = '__3tSelectionBox';
    var x = Math.min(r[0], r[2]);
    var y = Math.min(r[1], r[3]);
    var w = Math.abs(r[2] - r[0]);
    var h = Math.abs(r[3] - r[1]);
    el.style.cssText = 'position:absolute;border:2px dashed #0B84F3;background:rgba(11,132,243,0.08);pointer-events:none;z-index:50;box-sizing:border-box;left:' + x + 'px;top:' + y + 'px;width:' + w + 'px;height:' + h + 'px;';
    pageEl.appendChild(el);
})(%d, %f, %f, %f, %f);
"""

_CLEAR_SELECTION_OVERLAY_JS = """(function() {
    var el = document.getElementById('__3tSelectionBox');
    if (el && el.parentNode) el.parentNode.removeChild(el);
})();
"""

# JS for Foxit-style handles overlay — drag ↻ to rotate live.
# Handle layout: ↻ top-right, ✥ move top-left, × delete bottom-left, ✎ edit bottom-right.
# Args (Python % formatting): pageNum, pdfLeft, pdfBottom, pdfRight, pdfTop, currentRotation, hasEdit (true/false JS literal)
# Communicates with Python via window.__3tPendingAction (polled by QTimer — no QWebChannel needed).
_SHOW_OBJECT_WITH_HANDLES_JS = r"""(function(pageNum, pdfLeft, pdfBottom, pdfRight, pdfTop, currentRotation, hasEdit) {
    console.log('[3T] handles IIFE start page=' + pageNum + ' rot=' + currentRotation);
    var _cleanedUp = false;
    var _dragging  = false;

    window.__3tPendingAction = null;

    function reportAction(obj) {
        console.log('[3T] reportAction type=' + obj.type + (obj.angle !== undefined ? ' angle=' + obj.angle : ''));
        window.__3tPendingAction = obj;
    }

    function onDocClick(e) {
        if (_dragging) return;
        var grp = document.getElementById('__3tObjGroup');
        if (grp && grp.contains(e.target)) return;
        cleanupAll();
        reportAction({type:'dismiss'});
    }
    function onKeyDown(e) {
        if (e.key === 'Escape') {
            cleanupAll();
            reportAction({type:'dismiss'});
        }
    }
    function cleanupAll() {
        if (_cleanedUp) return;
        _cleanedUp = true;
        var el = document.getElementById('__3tObjGroup');
        if (el && el.parentNode) el.parentNode.removeChild(el);
        document.removeEventListener('click',   onDocClick, true);
        document.removeEventListener('keydown', onKeyDown,  true);
        window.__3tObjCleanup = null;
    }
    window.__3tObjCleanup = cleanupAll;

    // Delay click-outside listener so area-pick mouseup doesn't immediately dismiss.
    setTimeout(function() {
        if (!_cleanedUp) {
            document.addEventListener('click',   onDocClick, true);
            document.addEventListener('keydown', onKeyDown,  true);
        }
    }, 300);

    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) { console.error('[3T] no PDFViewerApplication'); return; }
    var pdfViewer = app.pdfViewer;
    var pageView  = pdfViewer.getPageView
        ? pdfViewer.getPageView(pageNum - 1)
        : (pdfViewer._pages && pdfViewer._pages[pageNum - 1]);
    if (!pageView || !pageView.viewport || !pageView.div) { console.error('[3T] no pageView for page ' + pageNum); return; }

    var vp     = pageView.viewport;
    var coords = vp.convertToViewportRectangle([pdfLeft, pdfBottom, pdfRight, pdfTop]);
    var pageEl = pageView.div;

    var bx = Math.min(coords[0], coords[2]);
    var by = Math.min(coords[1], coords[3]);
    var bw = Math.abs(coords[2] - coords[0]);
    var bh = Math.abs(coords[3] - coords[1]);
    console.log('[3T] coords bx=' + bx.toFixed(1) + ' by=' + by.toFixed(1) + ' bw=' + bw.toFixed(1) + ' bh=' + bh.toFixed(1));
    var H  = 13;
    var pad = H;

    // Group wrapper with padding so handles don't clip at page edge
    var grp = document.createElement('div');
    grp.id = '__3tObjGroup';
    grp.style.cssText = 'position:absolute;'
        + 'left:'+(bx-pad)+'px;top:'+(by-pad)+'px;'
        + 'width:'+(bw+2*pad)+'px;height:'+(bh+2*pad)+'px;'
        + 'transform-origin:'+(pad+bw/2)+'px '+(pad+bh/2)+'px;'
        + 'z-index:50;pointer-events:none;';
    if (currentRotation) grp.style.transform = 'rotate('+currentRotation+'deg)';
    pageEl.appendChild(grp);
    console.log('[3T] handles group appended to pageEl');

    // Selection box
    var box = document.createElement('div');
    box.style.cssText = 'position:absolute;'
        + 'left:'+pad+'px;top:'+pad+'px;width:'+bw+'px;height:'+bh+'px;'
        + 'border:2px solid #0B84F3;background:rgba(11,132,243,0.06);'
        + 'pointer-events:none;box-sizing:border-box;';
    grp.appendChild(box);

    // Angle label during drag
    var angleLbl = document.createElement('div');
    angleLbl.style.cssText = 'position:absolute;'
        + 'left:'+(pad+bw/2)+'px;top:'+(pad+bh/2)+'px;'
        + 'transform:translate(-50%%,-50%%);'
        + 'color:#0B84F3;font-size:13px;font-weight:700;font-family:sans-serif;'
        + 'pointer-events:none;opacity:0;transition:opacity 0.1s;'
        + 'background:rgba(255,255,255,0.82);border-radius:4px;padding:2px 7px;';
    grp.appendChild(angleLbl);

    function mkH(id, html, title, corner, bg, cur, fs) {
        var h = document.createElement('div');
        if (id) h.id = id;
        h.innerHTML = html;
        h.title = title;
        var pos;
        if (corner === 'tl') pos = 'left:0;top:0;';
        if (corner === 'tr') pos = 'right:0;top:0;';
        if (corner === 'bl') pos = 'left:0;bottom:0;';
        if (corner === 'br') pos = 'right:0;bottom:0;';
        h.style.cssText = 'position:absolute;border-radius:50%%;z-index:62;'
            + 'user-select:none;pointer-events:auto;'
            + 'display:flex;align-items:center;justify-content:center;'
            + 'box-shadow:0 2px 6px rgba(0,0,0,0.5);'
            + 'width:'+(H*2)+'px;height:'+(H*2)+'px;font-size:'+(fs||13)+'px;'
            + 'background:'+bg+';color:#fff;cursor:'+cur+';' + pos;
        return h;
    }

    // ↻ Rotate — top-right
    var rotH = mkH('__3tRotHandle', '&#8635;', 'Kéo để xoay', 'tr', '#0B84F3', 'grab', 18);
    grp.appendChild(rotH);
    // ✥ Move — top-left
    var mvH  = mkH('__3tMoveHandle', '&#10021;', 'Di chuyển', 'tl', '#FF8800', 'move', 11);
    grp.appendChild(mvH);
    // × Delete — bottom-left
    var delH = mkH('__3tDelHandle', '&times;', 'Xóa', 'bl', '#FF4444', 'pointer', 17);
    grp.appendChild(delH);
    // ✎ Edit — bottom-right (text only)
    if (hasEdit) {
        var editH = mkH('__3tEditHandle', '&#9998;', 'Sửa nội dung', 'br', '#22AA55', 'pointer', 13);
        grp.appendChild(editH);
        editH.addEventListener('click', function(e) {
            e.stopPropagation(); cleanupAll();
            reportAction({type:'edit'});
        });
    }

    // Rotation drag
    rotH.addEventListener('mousedown', function(e) {
        console.log('[3T] rotH mousedown');
        e.preventDefault(); e.stopPropagation();
        _dragging = true;
        rotH.style.cursor = 'grabbing';
        angleLbl.style.opacity = '1';
        angleLbl.textContent = currentRotation + '°';

        var pr0      = pageEl.getBoundingClientRect();
        var cx       = pr0.left + bx + bw / 2;
        var cy       = pr0.top  + by + bh / 2;
        var startAng = Math.atan2(e.clientY - cy, e.clientX - cx) * 180 / Math.PI;
        var dispAngle = currentRotation;

        function onMove(e2) {
            var pr  = pageEl.getBoundingClientRect();
            var cur = Math.atan2(e2.clientY - pr.top  - by - bh/2,
                                  e2.clientX - pr.left - bx - bw/2) * 180 / Math.PI;
            dispAngle = ((currentRotation + cur - startAng) %% 360 + 360) %% 360;
            grp.style.transform = 'rotate(' + dispAngle + 'deg)';
            angleLbl.textContent = Math.round(dispAngle) + '°';
        }
        function onUp() {
            console.log('[3T] rotH mouseup dispAngle=' + dispAngle);
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup',   onUp);
            _dragging = false;
            rotH.style.cursor = 'grab';
            var finalAngle = Math.round(dispAngle) %% 360;
            var moved = Math.abs(finalAngle - currentRotation);
            if (moved > 180) moved = 360 - moved;
            if (moved < 3) finalAngle = (Math.round(currentRotation / 15) * 15 + 15) %% 360;
            cleanupAll();
            reportAction({type:'rotate', angle: finalAngle});
        }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup',   onUp);
    });

    delH.addEventListener('click', function(e) {
        e.stopPropagation(); cleanupAll();
        reportAction({type:'delete'});
    });
    mvH.addEventListener('click', function(e) {
        e.stopPropagation(); cleanupAll();
        reportAction({type:'move'});
    });
})(%d, %f, %f, %f, %f, %d, %s);"""

_CLEAR_OBJECT_HANDLES_JS = """(function() {
    var el = document.getElementById('__3tObjGroup');
    if (el && el.parentNode) el.parentNode.removeChild(el);
    if (typeof window.__3tObjCleanup === 'function') window.__3tObjCleanup();
    window.__3tPendingAction = null;
})();"""

_SHOW_CANCEL_BTN_JS = r"""(function() {
    if (document.getElementById('__3tPickCancelBtn')) return;
    var btn = document.createElement('div');
    btn.id = '__3tPickCancelBtn';
    btn.textContent = 'Hủy';
    btn.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#c62828;color:#fff;padding:7px 24px;border-radius:20px;cursor:pointer;z-index:9999;font-size:13px;font-family:sans-serif;box-shadow:0 2px 8px rgba(0,0,0,0.4);user-select:none;';
    btn.onmousedown = function(e) {
        e.preventDefault();
        e.stopPropagation();
        window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    };
    document.body.appendChild(btn);
})();
"""

_REMOVE_CANCEL_BTN_JS = """(function() {
    var el = document.getElementById('__3tPickCancelBtn');
    if (el && el.parentNode) el.parentNode.removeChild(el);
})();
"""


class AreaPickBridge(QObject):
    picked = pyqtSignal(int, float, float, float, float)
    cancelled = pyqtSignal()

    @pyqtSlot(int, float, float, float, float)
    def reportArea(self, page_number, left, bottom, right, top):
        self.picked.emit(page_number, left, bottom, right, top)

    @pyqtSlot()
    def cancelPick(self):
        self.cancelled.emit()


class ObjectActionBridge(QObject):
    rotateConfirmed = pyqtSignal(float)
    deleteConfirmed = pyqtSignal()
    editConfirmed   = pyqtSignal()
    moveRequested   = pyqtSignal()
    dismissed       = pyqtSignal()

    @pyqtSlot(float)
    def reportRotation(self, angle):
        self.rotateConfirmed.emit(angle)

    @pyqtSlot()
    def reportDelete(self):
        self.deleteConfirmed.emit()

    @pyqtSlot()
    def reportEdit(self):
        self.editConfirmed.emit()

    @pyqtSlot()
    def reportMove(self):
        self.moveRequested.emit()

    @pyqtSlot()
    def reportDismiss(self):
        self.dismissed.emit()


def _pick_context_matches(window, expected_state, expected_path: str | None) -> bool:
    active_fn = getattr(window, "_active_state", None)
    current_state = active_fn() if callable(active_fn) else None
    if expected_state is not None and current_state is not expected_state:
        return False
    if expected_path and getattr(window, "current_path", None) != expected_path:
        return False
    return True


def _do_area_pick(web_view, bridge, window, *, expected_state=None, expected_path: str | None = None):
    """Execute one area pick using an already-registered bridge. Returns result dict or None."""
    result = {}
    loop = QEventLoop(window)
    stale_context = {"value": False}

    def _finish(page_number, left, bottom, right, top):
        if not _pick_context_matches(window, expected_state, expected_path):
            stale_context["value"] = True
            result.clear()
            if loop.isRunning():
                loop.quit()
            return
        result.update({
            "page_number": max(1, int(page_number)),
            "box": (left, bottom, right, top),
        })
        if loop.isRunning():
            loop.quit()

    def _cancel():
        result.clear()
        if loop.isRunning():
            loop.quit()

    bridge.picked.connect(_finish)
    bridge.cancelled.connect(_cancel)
    try:
        web_view.page().runJavaScript(_SHOW_CANCEL_BTN_JS)
        web_view.page().runJavaScript(_CLEAR_BRIDGE_CACHE_JS + "\n" + AREA_PICK_SCRIPT)
        loop.exec()
    finally:
        web_view.page().runJavaScript(_REMOVE_CANCEL_BTN_JS)
        try:
            bridge.picked.disconnect(_finish)
        except Exception:
            pass
        try:
            bridge.cancelled.disconnect(_cancel)
        except Exception:
            pass

    if stale_context["value"]:
        return {"_stale_context": True}
    return result or None


def _pick_pdf_area(window):
    from app.actions.sign import _get_web_view, _setup_webchannel, _teardown_webchannel
    expected_state = window._active_state() if hasattr(window, "_active_state") else None
    expected_path = getattr(window, "current_path", None)
    web_view = _get_web_view(window)
    if web_view is None:
        return None

    bridge = AreaPickBridge(window)
    _setup_webchannel(web_view, window, "areaPickBridge", bridge)
    try:
        result = _do_area_pick(
            web_view,
            bridge,
            window,
            expected_state=expected_state,
            expected_path=expected_path,
        )
        if result and result.get("_stale_context"):
            show_warning(
                window,
                "Đã đổi tài liệu",
                "Bạn đã đổi tab trong lúc đang chọn vùng. Hãy thực hiện lại trên đúng tài liệu.",
            )
            return None
        return result
    finally:
        web_view.page().runJavaScript(_CLEAR_BRIDGE_CACHE_JS)
        _teardown_webchannel(web_view)


def _show_object_overlay(window, op):
    from app.actions.sign import _get_web_view
    wv = _get_web_view(window)
    if not wv:
        return
    page_num = int(op.get("page_number", 1))
    left, bottom, right, top = op.get("box", (0, 0, 0, 0))
    js = _SHOW_SELECTION_OVERLAY_JS % (page_num, left, bottom, right, top)
    wv.page().runJavaScript(js)


def _clear_object_overlay(window):
    from app.actions.sign import _get_web_view
    wv = _get_web_view(window)
    if wv:
        wv.page().runJavaScript(_CLEAR_SELECTION_OVERLAY_JS)


def _get_edit_state(window):
    """Get edit state for the currently active tab (falls back to window attr)."""
    active_fn = getattr(window, "_active_state", None)
    if callable(active_fn):
        tab_state = active_fn()
        if tab_state is not None:
            return tab_state.get("_pdf_edit_state")
    return getattr(window, "_pdf_edit_state", None)


def _set_edit_state(window, value):
    """Set edit state for the currently active tab (falls back to window attr)."""
    active_fn = getattr(window, "_active_state", None)
    if callable(active_fn):
        tab_state = active_fn()
        if tab_state is not None:
            tab_state["_pdf_edit_state"] = value
            return
    window._pdf_edit_state = value


def _reset_edit_state(window):
    state = _get_edit_state(window)
    if not state:
        return
    for path_key in ("base_snapshot", "working_file"):
        path = state.get(path_key)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    _set_edit_state(window, None)


def _place_dialog_near_parent(parent, width: int, height: int, *, dx: int = 16, dy: int = 72):
    if parent is None:
        return 0, 0
    try:
        screen = parent.windowHandle().screen() if parent.windowHandle() else None
    except Exception:
        screen = None
    if screen is None:
        from packages.qt_compat.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
    if screen is None:
        return 0, 0
    geo = screen.availableGeometry()
    parent_geo = parent.frameGeometry()
    target_x = parent_geo.right() - width - dx
    target_y = parent_geo.top() + dy
    max_x = max(geo.left(), geo.right() - width)
    max_y = max(geo.top(), geo.bottom() - height)
    x = min(max(geo.left(), target_x), max_x)
    y = min(max(geo.top(), target_y), max_y)
    return int(x), int(y)


def _ensure_edit_state(window):
    current = window.current_path
    if not current:
        return None

    state = _get_edit_state(window)

    # Nếu đang edit state và file gốc khớp → tái sử dụng
    if state and state.get("original_path") == current:
        return state
    # Nếu đang edit và viewer đang hiển thị working file → tái sử dụng
    if state and state.get("working_file") == current:
        return state

    # Cảnh báo trước khi vào edit mode trên file đã ký số: rebuild_pdf_with_ops
    # không bảo toàn chữ ký, mọi edit sẽ làm chữ ký mất hiệu lực.
    try:
        from app.local_server import _pdf_has_signature_field

        if _pdf_has_signature_field(current):
            warned = getattr(window, "_edit_sig_warned_paths", None)
            if warned is None:
                warned = set()
                window._edit_sig_warned_paths = warned
            if current not in warned:
                reply = QMessageBox.warning(
                    window,
                    "Tài liệu đã có chữ ký số",
                    "Tài liệu này có chữ ký số. Mọi thao tác chỉnh sửa (chèn text/ảnh, vẽ, "
                    "tô đậm, xóa…) sẽ làm chữ ký không còn hợp lệ và trình đọc PDF sẽ báo "
                    "“document modified after signing”.\n\n"
                    "Bạn có chắc muốn tiếp tục?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return None
                warned.add(current)
    except Exception:
        pass

    display_path = window.get_display_path() if hasattr(window, "get_display_path") else None
    temp_root = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    snapshot_source = current
    try:
        current_abs = os.path.abspath(current)
        temp_root_abs = os.path.abspath(temp_root)
        if (
            display_path
            and os.path.exists(display_path)
            and current_abs.startswith(temp_root_abs + os.sep)
            and os.path.basename(current_abs).lower().startswith(("op_", "work_", "base_"))
        ):
            snapshot_source = display_path
    except Exception:
        snapshot_source = current

    _reset_edit_state(window)

    edit_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(edit_dir, exist_ok=True)
    session_id = uuid.uuid4().hex[:8]
    base_snapshot = os.path.join(edit_dir, f"base_{session_id}.pdf")
    working_file = os.path.join(edit_dir, f"work_{session_id}.pdf")

    shutil.copy2(snapshot_source, base_snapshot)
    shutil.copy2(snapshot_source, working_file)

    state = {
        "original_path": snapshot_source,
        "base_snapshot": base_snapshot,
        "working_file": working_file,
        "ops": [],
        "next_id": 1,
    }
    _set_edit_state(window, state)
    return state


def _reload_viewer(window, pdf_path: str, page: int | None = None):
    """Reload PDF in the current viewer without opening a new tab."""
    if page is None:
        try:
            page = window.viewer.get_current_page()
        except Exception:
            page = 1
    page = max(1, page)

    window.current_path = pdf_path
    from packages.qt_compat.QtCore import QTimer

    def _load():
        try:
            window.viewer.load_pdf(pdf_path, page=page, zoom="page-width")
        except Exception as exc:
            show_warning(window, "Không thể mở file vừa lưu", str(exc))

    QTimer.singleShot(0, _load)


def _run_when_viewer_page_ready(window, callback, *, timeout_ms: int = 1600):
    viewer = getattr(window, "viewer", None)
    if viewer is None:
        callback()
        return

    fired = {"done": False}

    def _finish(*_args):
        if fired["done"]:
            return
        fired["done"] = True
        try:
            viewer.page_ready.disconnect(_on_ready)
        except Exception:
            pass
        callback()

    def _on_ready(*_args):
        _finish()

    try:
        viewer.page_ready.connect(_on_ready)
    except Exception:
        callback()
        return

    from packages.qt_compat.QtCore import QTimer
    QTimer.singleShot(timeout_ms, _finish)


def _navigate_viewer(window, page_no: int):
    """Điều hướng PDF viewer đến trang chỉ định qua JavaScript."""
    try:
        from app.actions.sign import _get_web_view
        wv = _get_web_view(window)
        if wv:
            wv.page().runJavaScript(
                f"(function(){{var app=window.PDFViewerApplication;"
                f"if(app&&app.pdfViewer){{app.pdfViewer.currentPageNumber={int(page_no)};}}}})()"
            )
    except Exception:
        pass


def _render_edit_state(
    window,
    state,
    status_message: str,
    focus_page: int | None = None,
    auto_select_op: dict | None = None,
):
    """Rebuild working file from base + all ops, then reload viewer in-place."""
    base_snapshot = state.get("base_snapshot")
    ops = state.get("ops") or []
    if not base_snapshot or not os.path.exists(base_snapshot):
        show_warning(window, "Không thể chỉnh sửa", "Thiếu bản gốc để dựng lại tài liệu.")
        return None

    working_file = state.get("working_file")
    if not working_file:
        show_warning(window, "Không thể chỉnh sửa", "Thiếu file làm việc.")
        return None

    current_page = focus_page
    if current_page is None:
        try:
            current_page = window.viewer.get_current_page()
        except Exception:
            pass

    try:
        get_pdf_engine().rebuild_pdf_with_ops(base_snapshot, working_file, ops)
    except Exception as e:
        show_warning(window, "Không lưu được tệp", str(e))
        return None

    _reload_viewer(window, working_file, page=current_page)

    if auto_select_op is not None:
        viewer = getattr(window, "viewer", None)
        if viewer is not None:
            def _auto_open():
                try:
                    viewer.page_ready.disconnect(_auto_open)
                except Exception:
                    pass
                from packages.qt_compat.QtCore import QTimer
                QTimer.singleShot(0, lambda: _run_object_action_session(window, state, auto_select_op))

            try:
                viewer.page_ready.connect(_auto_open)
            except Exception:
                pass

    # Điều hướng đến trang đã chèn sau khi viewer load xong (delay nhỏ)
    if focus_page is not None:
        _run_when_viewer_page_ready(window, lambda: _navigate_viewer(window, focus_page))

    op_count = len(ops)
    undo_hint = f" (Ctrl+Z để hoàn tác, {op_count} thao tác)" if op_count > 0 else ""
    window.status.showMessage(f"{status_message}{undo_hint}", 4000)
    return working_file


def _adjust_placement(window, initial_placement: dict, title: str = "Xác nhận vị trí") -> dict | None:
    """Hiển thị overlay kéo/co dãn để người dùng tinh chỉnh vị trí TRƯỚC khi rebuild.
    Returns: placement dict cuối cùng, hoặc None nếu huỷ."""
    from app.actions.sign import (
        _get_web_view, _setup_webchannel, _teardown_webchannel,
        _set_signature_preview, SignaturePreviewAdjustBridge,
    )

    web_view = _get_web_view(window)
    if web_view is None:
        return initial_placement

    placement = dict(initial_placement)

    confirm_dlg = _ObjectPlacementDialog(
        window,
        title=title,
        note=(
            "Kéo khung xanh để di chuyển\n"
            "Kéo góc phải-dưới để thay đổi kích thước\n"
            "Nhấn OK để xác nhận vị trí"
        ),
    )

    bridge = SignaturePreviewAdjustBridge(confirm_dlg)
    _setup_webchannel(web_view, confirm_dlg, "sigPreviewBridge", bridge)

    def _on_adjusted(page_no, left, bottom, right, top):
        nonlocal placement
        placement = {
            "page_number": max(1, int(page_no)),
            "box": (left, bottom, right, top),
        }
        _set_signature_preview(window, placement)

    bridge.adjusted.connect(_on_adjusted)
    _set_signature_preview(window, placement)

    try:
        loop = QEventLoop(confirm_dlg)
        confirm_dlg.finished.connect(
            lambda _code: loop.quit() if loop.isRunning() else None
        )
        confirm_dlg.show()
        confirm_dlg.raise_()
        confirm_dlg.activateWindow()
        loop.exec()

        if confirm_dlg.result() != QDialog.DialogCode.Accepted:
            return None
        return placement
    finally:
        _set_signature_preview(window, None)
        _teardown_webchannel(web_view)


@require_document(show_message=True)
def undo_last_edit(window):
    """Hoàn tác thao tác chèn cuối cùng."""
    state = _get_edit_state(window)
    if not state or not state.get("ops"):
        try:
            from app.actions.annotate import undo_last_annotation

            if undo_last_annotation(window):
                return
        except Exception:
            pass
        show_warning(window, "Không có gì để hoàn tác", "Chưa có thao tác chèn nào để hoàn tác.")
        return

    removed = state["ops"].pop()
    op_type = "văn bản" if removed.get("type") == "text" else "ảnh"

    if not state["ops"]:
        # Không còn ops → dọn dẹp state và quay về file gốc
        original = state.get("original_path")
        _reset_edit_state(window)  # xóa temp files, clear state
        if original and os.path.exists(original):
            _reload_viewer(window, original)
        window.status.showMessage(f"Đã hoàn tác chèn {op_type} — về trạng thái ban đầu", 3000)
    else:
        _render_edit_state(window, state, f"Đã hoàn tác chèn {op_type}")



def _find_op_at_pick(state, pick):
    page_number = int(pick.get("page_number", 0))
    pl, pb, pr, pt = pick.get("box", (0, 0, 0, 0))

    candidates = [op for op in state.get("ops", []) if op.get("page_number") == page_number]
    if not candidates:
        return None

    # Prefer last inserted op with maximum overlap area.
    def overlap_area(op):
        l, b, r, t = op.get("box", (0, 0, 0, 0))
        ow = max(0.0, min(pr, r) - max(pl, l))
        oh = max(0.0, min(pt, t) - max(pb, b))
        return ow * oh

    best = max(candidates, key=overlap_area)
    if overlap_area(best) > 0:
        return best

    # Fallback: nearest center.
    cx = (pl + pr) / 2.0
    cy = (pb + pt) / 2.0

    def dist2(op):
        l, b, r, t = op.get("box", (0, 0, 0, 0))
        ox = (l + r) / 2.0
        oy = (b + t) / 2.0
        return (ox - cx) ** 2 + (oy - cy) ** 2

    return min(candidates, key=dist2)


def _run_object_action_session(window, state, target_op, web_view=None):
    from app.actions.sign import _get_web_view, _setup_webchannel, _teardown_webchannel

    if web_view is None:
        web_view = _get_web_view(window)
    if web_view is None:
        return

    op_type = target_op.get("type", "text")
    current_rot = int(target_op.get("rotation", 0))
    page_num = int(target_op.get("page_number", 1))
    left, bottom, right, top = target_op.get("box", (0, 0, 0, 0))

    _show_object_overlay(window, target_op)

    # Poll window.__3tPendingAction every 80 ms â€” no QWebChannel needed.
    action_result = {}
    loop = QEventLoop(window)
    poll_timer = QTimer(window)
    poll_timer.setInterval(80)

    def _poll_action(js_result):
        if js_result is None:
            return
        action_result.update(js_result)
        poll_timer.stop()
        if loop.isRunning():
            loop.quit()

    def _do_poll():
        web_view.page().runJavaScript("window.__3tPendingAction", _poll_action)

    poll_timer.timeout.connect(_do_poll)

    def _js_ran(_result):
        pass

    try:
        js = _SHOW_OBJECT_WITH_HANDLES_JS % (
            page_num, left, bottom, right, top,
            current_rot, "true" if op_type == "text" else "false",
        )
        web_view.page().runJavaScript(js, _js_ran)
        poll_timer.start()
        loop.exec()
    finally:
        poll_timer.stop()
        web_view.page().runJavaScript(_CLEAR_OBJECT_HANDLES_JS)
        _clear_object_overlay(window)

    action = action_result.get("type", "dismiss")

    if action == "dismiss":
        return

    if action == "rotate":
        angle = int(action_result.get("angle", 0)) % 360
        target_op["rotation"] = angle
        _render_edit_state(window, state, f"Đã xoay {angle}°", focus_page=page_num)
        return

    if action == "delete":
        op_label = "văn bản" if op_type == "text" else "ảnh"
        state["ops"].remove(target_op)
        if not state["ops"]:
            original = state.get("original_path")
            _reset_edit_state(window)
            if original and os.path.exists(original):
                _reload_viewer(window, original)
            window.status.showMessage(f"Đã xóa {op_label} — tài liệu về trạng thái gốc", 3000)
        else:
            _render_edit_state(window, state, f"Đã xóa {op_label}")
        return

    if action == "edit" and op_type == "text":
        color_tuple = target_op.get("font_color", (0.0, 0.0, 0.0))
        dlg_edit = _TextEditDialog(
            window,
            text=target_op.get("text", ""),
            font_size=target_op.get("font_size", 14),
            color_tuple=color_tuple,
            bold=target_op.get("bold", False),
            underline=target_op.get("underline", False),
        )
        if dlg_edit.exec() != QDialog.DialogCode.Accepted:
            return
        new_text = dlg_edit.get_text()
        if not new_text:
            return

        target_op["text"] = new_text
        target_op["font_size"] = dlg_edit.get_font_size()
        target_op["font_color"] = dlg_edit.get_color_tuple()
        target_op["bold"] = dlg_edit.get_bold()
        target_op["underline"] = dlg_edit.get_underline()
        _render_edit_state(window, state, "Đã cập nhật văn bản", focus_page=page_num)
        return

    if action == "move":
        pick_bridge2 = AreaPickBridge(window)
        _setup_webchannel(web_view, window, "areaPickBridge", pick_bridge2)
        try:
            if hasattr(window, "status"):
                window.status.showMessage("Kéo để chọn vị trí/kích thước mới... (Esc để hủy)", 0)
            new_area = _do_area_pick(web_view, pick_bridge2, window)
            if hasattr(window, "status"):
                window.status.showMessage("", 0)
        finally:
            web_view.page().runJavaScript(_CLEAR_BRIDGE_CACHE_JS)
            _teardown_webchannel(web_view)

        if not new_area:
            return
        l, b, r, t = new_area["box"]
        if abs(r - l) < 6 or abs(t - b) < 6:
            w = target_op["box"][2] - target_op["box"][0]
            h = target_op["box"][3] - target_op["box"][1]
            r = l + max(20, w)
            t = b + max(20, h)
        target_op["page_number"] = int(new_area["page_number"])
        target_op["box"] = (l, b, r, t)
        _render_edit_state(window, state, "Đã cập nhật vị trí/kích thước đối tượng")


def _pick_save_pdf_path(window, default_name: str) -> str | None:
    path, _ = QFileDialog.getSaveFileName(
        window,
        "Lưu tệp PDF",
        default_name,
        "PDF Files (*.pdf)",
    )
    if not path:
        return None
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    return path


class _ObjectPlacementDialog(QDialog):
    """Simple confirm dialog for object placement preview (image, text)."""

    def __init__(self, parent=None, *, title: str = "Chèn đối tượng", note: str = ""):
        from packages.qt_compat.QtCore import Qt

        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(320)

        root = QVBoxLayout(self)

        if note:
            label = QLabel(note)
            label.setWordWrap(True)
            root.addWidget(label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.adjustSize()
        self._position_near_parent(parent)

    def _position_near_parent(self, parent):
        x, y = _place_dialog_near_parent(parent, self.width(), self.height())
        self.move(x, y)


class _TextEditDialog(QDialog):
    """Dark-themed dialog for editing text/formatting — no webchannel needed."""

    def __init__(self, parent=None, *, text="", font_size=14,
                 color_tuple=(0.0, 0.0, 0.0), bold=False, underline=False):
        from packages.qt_compat.QtCore import Qt
        from packages.qt_compat.QtGui import QColor

        super().__init__(parent)
        self.setWindowTitle("Sửa văn bản")
        # Do NOT use Tool flag — it blocks keyboard input on Windows
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(True)
        self.setMinimumWidth(420)

        self._color = QColor(
            int(color_tuple[0] * 255),
            int(color_tuple[1] * 255),
            int(color_tuple[2] * 255),
        )

        self.setStyleSheet(
            "QDialog{background:#1A1E30;}"
            "QLabel{color:#B0C8F0;font-size:12px;background:transparent;border:none;padding:0;}"
            "QTextEdit{background:#10121C;color:#D8E8FF;border:1px solid #304080;"
            "          border-radius:4px;padding:6px;font-size:14px;}"
            "QTextEdit:focus{border-color:#4060C0;}"
            "QSpinBox{background:#10121C;color:#D8E8FF;border:1px solid #304080;"
            "         border-radius:4px;padding:2px 6px;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("✏  Sửa văn bản")
        title.setStyleSheet(
            "color:#7AAAE8;font-size:11px;font-weight:700;background:transparent;border:none;"
        )
        root.addWidget(title)

        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(text)
        self._text_edit.setMinimumHeight(130)
        root.addWidget(self._text_edit)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)

        fmt_row.addWidget(QLabel("Cỡ chữ:"))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 96)
        self._size_spin.setValue(font_size)
        self._size_spin.setFixedWidth(64)
        fmt_row.addWidget(self._size_spin)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(72, 26)
        self._color_btn.clicked.connect(self._pick_color)
        self._refresh_color_btn()
        fmt_row.addWidget(self._color_btn)

        _fmt_ss = (
            "QToolButton{background:#10121C;color:#D8E8FF;border:1px solid #304080;"
            "border-radius:4px;font-size:13px;font-weight:700;padding:3px 8px;}"
            "QToolButton:checked{background:#2A4080;border-color:#6080C0;color:#FFF;}"
            "QToolButton:hover{border-color:#4060A0;}"
        )
        self._bold_btn = QToolButton()
        self._bold_btn.setText("B")
        self._bold_btn.setCheckable(True)
        self._bold_btn.setChecked(bold)
        self._bold_btn.setStyleSheet(_fmt_ss)
        fmt_row.addWidget(self._bold_btn)

        self._under_btn = QToolButton()
        self._under_btn.setText("U")
        self._under_btn.setCheckable(True)
        self._under_btn.setChecked(underline)
        self._under_btn.setStyleSheet(_fmt_ss.replace("font-weight:700", "font-weight:400"))
        fmt_row.addWidget(self._under_btn)

        fmt_row.addStretch()
        root.addLayout(fmt_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet(
            "QPushButton{background:transparent;color:#FF6655;border:2px solid #FF6655;"
            "border-radius:5px;padding:5px 14px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#3A1010;}"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("Lưu thay đổi")
        btn_ok.setDefault(True)
        btn_ok.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #FF7700,stop:1 #FF4400);color:white;border:none;"
            "border-radius:5px;padding:5px 14px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#FF9900;}"
        )
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        root.addLayout(btn_row)

        self.adjustSize()
        self._position_near_parent(parent)

        from packages.qt_compat.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._text_edit.setFocus())

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Màu chữ")
        if c.isValid():
            self._color = c
            self._refresh_color_btn()

    def _refresh_color_btn(self):
        c = self._color
        luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        txt = "#000" if luma > 128 else "#FFF"
        self._color_btn.setStyleSheet(
            f"QPushButton{{background:{c.name()};color:{txt};"
            "border:1px solid #555;border-radius:4px;font-size:11px;}}"
        )
        self._color_btn.setText("Màu chữ")

    def get_text(self) -> str:
        return self._text_edit.toPlainText().strip()

    def get_font_size(self) -> int:
        return self._size_spin.value()

    def get_color_tuple(self) -> tuple:
        c = self._color
        return (c.redF(), c.greenF(), c.blueF())

    def get_bold(self) -> bool:
        return self._bold_btn.isChecked()

    def get_underline(self) -> bool:
        return self._under_btn.isChecked()

    def _position_near_parent(self, parent):
        x, y = _place_dialog_near_parent(parent, self.width(), self.height())
        self.move(x, y)


class _ObjectEditDialog(QDialog):
    """Action panel shown after a selected object is highlighted."""

    ACTION_MOVE   = "move"
    ACTION_EDIT   = "edit"
    ACTION_ROTATE = "rotate"
    ACTION_DELETE = "delete"
    ACTION_CANCEL = "cancel"

    def __init__(self, parent=None, *, op_type: str = "text"):
        from packages.qt_compat.QtCore import Qt

        super().__init__(parent)
        self.setWindowTitle("Tùy chọn đối tượng")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setMinimumWidth(300)

        self._action = self.ACTION_CANCEL

        self.setStyleSheet(
            "QDialog{background:#1A1E30;}"
            "QLabel{color:#B0C8F0;font-size:12px;background:transparent;border:none;padding:4px 0;}"
            "QPushButton{background:#10121C;color:#D8E8FF;border:1px solid #304080;"
            "border-radius:5px;padding:8px 14px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#1E2A50;border-color:#4060C0;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)

        title = QLabel("Chọn thao tác cho đối tượng đã chọn:")
        title.setStyleSheet(
            "color:#7AAAE8;font-size:11px;font-weight:700;background:transparent;border:none;"
        )
        root.addWidget(title)

        btn_move = QPushButton("Di chuyển / Đổi kích thước")
        btn_move.clicked.connect(lambda: self._pick(self.ACTION_MOVE))
        root.addWidget(btn_move)

        if op_type == "text":
            btn_edit = QPushButton("Sửa nội dung / Định dạng")
            btn_edit.clicked.connect(lambda: self._pick(self.ACTION_EDIT))
            root.addWidget(btn_edit)

        btn_rotate = QPushButton("Xoay (nhập góc tùy ý)")
        btn_rotate.clicked.connect(lambda: self._pick(self.ACTION_ROTATE))
        root.addWidget(btn_rotate)

        btn_delete = QPushButton("Xóa đối tượng")
        btn_delete.setStyleSheet(
            "QPushButton{background:#10121C;color:#FF6655;border:2px solid #FF4444;"
            "border-radius:5px;padding:8px 14px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#3A1010;border-color:#FF6655;}"
        )
        btn_delete.clicked.connect(lambda: self._pick(self.ACTION_DELETE))
        root.addWidget(btn_delete)

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet(
            "QPushButton{background:transparent;color:#7090B0;border:1px solid #304060;"
            "border-radius:5px;padding:8px 14px;font-size:12px;}"
            "QPushButton:hover{background:#1A1E30;color:#B0C0D0;}"
        )
        btn_cancel.clicked.connect(lambda: self._pick(self.ACTION_CANCEL))
        root.addWidget(btn_cancel)

        self.adjustSize()
        self._position_near_parent(parent)

    def _pick(self, action: str):
        self._action = action
        self.accept()

    def chosen_action(self) -> str:
        return self._action

    def _position_near_parent(self, parent):
        x, y = _place_dialog_near_parent(parent, self.width(), self.height())
        self.move(x, y)


def create_new_pdf(window):
    output_path = _pick_save_pdf_path(window, "tai_lieu_moi.pdf")
    if not output_path:
        return

    get_pdf_engine().create_blank_pdf(output_path, A4_WIDTH_PT, A4_HEIGHT_PT)

    open_file(window, output_path)
    window.status.showMessage("Đã tạo PDF mới", 3000)


@require_document(show_message=True)
def insert_text_to_pdf(window):
    from app.pdf_inline_editor import run_inline_text

    result = run_inline_text(window)
    if not result:
        return

    page_number = result["page_number"]
    left, bottom, right, top = result["box"]

    # Đảm bảo vùng tối thiểu
    if abs(right - left) < 20:
        right = left + 180
    if abs(top - bottom) < 12:
        top = bottom + 44

    state = _ensure_edit_state(window)
    if not state:
        return

    op = {
        "id":         state["next_id"],
        "type":       "text",
        "page_number": page_number,
        "box":        (left, bottom, right, top),
        "text":       result["text"],
        "font_size":  result.get("font_size", 14),
        "font_color": result.get("color_tuple", (0.0, 0.0, 0.0)),
        "bold":       result.get("bold", False),
        "underline":  result.get("underline", False),
        "rotation":   result.get("rotation", 0),
    }
    state["next_id"] += 1
    state["ops"].append(op)

    _render_edit_state(window, state,
        "Đã chèn văn bản  ·  Dùng nút 'Chọn & Xoay' để xoay/di chuyển/sửa",
        focus_page=page_number,
        auto_select_op=op)


@require_document(show_message=True)
def insert_image_to_pdf(window):
    from app.pdf_inline_editor import run_inline_image

    image_path, _ = QFileDialog.getOpenFileName(
        window,
        "Chọn ảnh",
        "",
        "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
    )
    if not image_path:
        return

    result = run_inline_image(window, image_path)
    if not result:
        return

    # Stage image to temp dir so the op doesn't depend on the original path
    edit_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(edit_dir, exist_ok=True)
    ext = os.path.splitext(image_path)[1].lower() or ".png"
    staged = os.path.join(edit_dir, f"img_{uuid.uuid4().hex[:12]}{ext}")
    try:
        shutil.copy2(image_path, staged)
        image_path = staged
    except OSError:
        pass  # keep original path if staging fails

    page_number = result["page_number"]
    left, bottom, right, top = result["box"]

    # Đảm bảo vùng tối thiểu
    if abs(right - left) < 20:
        right = left + 150
    if abs(top - bottom) < 20:
        top = bottom + 120
    box = (left, bottom, right, top)

    state = _ensure_edit_state(window)
    if not state:
        return

    op = {
        "id":          state["next_id"],
        "type":        "image",
        "page_number": page_number,
        "box":         box,
        "image_path":  image_path,
        "rotation":    result.get("rotation", 0),
    }
    state["next_id"] += 1
    state["ops"].append(op)

    _render_edit_state(window, state,
        "Đã chèn ảnh  ·  Dùng nút 'Chọn & Xoay' để xoay/di chuyển",
        focus_page=page_number,
        auto_select_op=op)



@require_document(show_message=True)
def save_edits(window, *, reload_viewer: bool = True) -> bool:
    """Lưu các thay đổi (text/ảnh đã chèn) vào file gốc."""
    state = _get_edit_state(window)
    if not state:
        # Không có edit state — lưu thông thường
        try:
            window.viewer.save_pdf()
        except Exception:
            return False
        return True

    working = state.get("working_file")
    base = state.get("base_snapshot")
    original = state.get("original_path")

    if not working or not base or not os.path.exists(base):
        show_warning(window, "Không lưu được", "Không tìm thấy file làm việc.")
        return False

    # Rebuild lần cuối vào working file
    try:
        get_pdf_engine().rebuild_pdf_with_ops(base, working, state.get("ops", []))
    except Exception as e:
        show_warning(window, "Lỗi khi dựng file", str(e))
        return False

    # Xác định đường dẫn lưu
    save_path = original
    if not save_path or not os.path.exists(os.path.dirname(save_path) or "."):
        save_path = _pick_save_pdf_path(window, "document.pdf")
    if not save_path:
        return False

    try:
        atomic_copy_file(working, save_path)
    except Exception as e:
        show_warning(window, "Lỗi ghi file", str(e))
        return False

    # Reset edit state, tải lại từ file đã lưu
    _set_edit_state(window, None)
    if reload_viewer:
        reload_document(window, save_path, display_path=save_path, temp_path=None)
    else:
        try:
            window.current_path = save_path
            state_obj = window._state_or_global() if hasattr(window, "_state_or_global") else None
            if isinstance(state_obj, dict):
                state_obj["source_path"] = save_path
                state_obj["display_path"] = save_path
                state_obj["temp_path"] = None
        except Exception:
            pass
    window.status.showMessage(
        f"Đã lưu: {os.path.basename(save_path)}", 5000
    )
    return True


def save_edits_quiet(window) -> bool:
    """Save current edit session without reloading the viewer."""
    state = _get_edit_state(window)
    if not state:
        try:
            window.viewer.save_pdf()
        except Exception:
            return False
        return True

    working = state.get("working_file")
    base = state.get("base_snapshot")
    original = state.get("original_path")

    if not working or not base or not os.path.exists(base):
        return False

    try:
        get_pdf_engine().rebuild_pdf_with_ops(base, working, state.get("ops", []))
    except Exception:
        return False

    save_path = original
    if not save_path or not os.path.exists(os.path.dirname(save_path) or "."):
        save_path = _pick_save_pdf_path(window, "document.pdf")
    if not save_path:
        return False

    try:
        atomic_copy_file(working, save_path)
    except Exception:
        return False

    _set_edit_state(window, None)
    reload_document(window, save_path, display_path=save_path, temp_path=None)
    window.status.showMessage(f"Đã lưu: {os.path.basename(save_path)}", 5000)
    return True


@require_document(show_message=True)
def save_edits_as(window):
    """Lưu bản chỉnh sửa thành file mới (Save As)."""
    state = _get_edit_state(window)
    src = state.get("working_file") if state else window.current_path
    if not src:
        return

    save_path = _pick_save_pdf_path(window, "document_copy.pdf")
    if not save_path:
        return

    if state:
        base = state.get("base_snapshot", "")
        try:
            get_pdf_engine().rebuild_pdf_with_ops(base, src, state.get("ops", []))
        except Exception as e:
            show_warning(window, "Lỗi khi dựng file", str(e))
            return

    try:
        atomic_copy_file(src, save_path)
    except Exception as e:
        show_warning(window, "Lỗi ghi file", str(e))
        return

    window.status.showMessage(f"Đã lưu bản sao: {os.path.basename(save_path)}", 4000)


@require_document(show_message=True)
def delete_inserted_object(window):
    """Xóa một text/ảnh đã chèn — click vào đối tượng muốn xóa."""
    state = _get_edit_state(window)  # read-only: must already exist
    if not state or not state.get("ops"):
        show_warning(window, "Chưa có đối tượng", "Chưa có text/ảnh nào được chèn để xóa.")
        return

    if hasattr(window, "status"):
        window.status.showMessage("Click vào text/ảnh muốn xóa... (Esc để hủy)", 0)

    picked = _pick_pdf_area(window)

    if hasattr(window, "status"):
        window.status.showMessage("", 0)

    if not picked:
        return

    target_op = _find_op_at_pick(state, picked)
    if not target_op:
        show_warning(window, "Không tìm thấy", "Không xác định được đối tượng tại vị trí đó.")
        return

    op_type = "văn bản" if target_op.get("type") == "text" else "ảnh"
    state["ops"].remove(target_op)

    if not state["ops"]:
        original = state.get("original_path")
        _reset_edit_state(window)
        if original and os.path.exists(original):
            _reload_viewer(window, original)
        window.status.showMessage(f"Đã xóa {op_type} — tài liệu về trạng thái gốc", 3000)
    else:
        _render_edit_state(window, state, f"Đã xóa {op_type}")


@require_document(show_message=True)
def redact_area(window):
    """Che/tẩy vùng nội dung bằng hộp màu trắng."""
    if hasattr(window, "status"):
        window.status.showMessage("Kéo để chọn vùng cần che... (Esc để hủy)", 0)

    placement = _pick_pdf_area(window)

    if hasattr(window, "status"):
        window.status.showMessage("", 0)

    if not placement:
        return

    page_number = int(placement["page_number"])
    left, bottom, right, top = placement["box"]

    if abs(right - left) < 4 or abs(top - bottom) < 4:
        show_warning(window, "Vùng quá nhỏ", "Hãy kéo để chọn vùng rộng hơn.")
        return

    state = _ensure_edit_state(window)
    if not state:
        return

    op = {
        "id": state["next_id"],
        "type": "rect",
        "page_number": page_number,
        "box": (left, bottom, right, top),
        "fill_color": (1.0, 1.0, 1.0),
        "stroke_color": (1.0, 1.0, 1.0),
    }
    state["next_id"] += 1
    state["ops"].append(op)
    _render_edit_state(window, state, "Đã che vùng nội dung")


@require_document(show_message=True)
def draw_on_pdf(window):
    """Vẽ tự do lên vùng PDF đã chọn."""
    from app.signature_pad import DrawOnPdfDialog

    if hasattr(window, "status"):
        window.status.showMessage("Kéo để chọn vùng muốn vẽ trên PDF... (Esc để hủy)", 0)

    placement = _pick_pdf_area(window)

    if hasattr(window, "status"):
        window.status.showMessage("", 0)

    if not placement:
        return

    page_number = int(placement["page_number"])
    left, bottom, right, top = placement["box"]

    # Tính kích thước canvas theo tỉ lệ vùng đã chọn
    w_pt = max(right - left, 20.0)
    h_pt = max(top - bottom, 20.0)
    aspect = w_pt / h_pt
    canvas_w = 560
    canvas_h = max(80, int(canvas_w / aspect))
    if canvas_h > 480:
        canvas_h = 480
        canvas_w = int(canvas_h * aspect)

    dlg = DrawOnPdfDialog(window, canvas_w=canvas_w, canvas_h=canvas_h)
    if dlg.exec() != dlg.DialogCode.Accepted:
        return

    pixmap = dlg.get_pixmap()
    if pixmap is None:
        return

    # Lưu ra file PNG tạm (ARGB — giữ trong suốt)
    edit_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(edit_dir, exist_ok=True)
    img_path = os.path.join(edit_dir, f"draw_{uuid.uuid4().hex[:8]}.png")
    pixmap.save(img_path, "PNG")

    state = _ensure_edit_state(window)
    if not state:
        return

    op = {
        "id": state["next_id"],
        "type": "image",
        "page_number": page_number,
        "box": (left, bottom, right, top),
        "image_path": img_path,
    }
    state["next_id"] += 1
    state["ops"].append(op)
    _render_edit_state(window, state, "Đã vẽ lên PDF")


@require_document(show_message=True)
def select_inserted_object(window):
    state = _get_edit_state(window)
    if not state or not state.get("ops"):
        show_warning(window, "Chưa có đối tượng", "Chưa có text/ảnh nào được chèn.")
        return

    from app.actions.sign import _get_web_view, _setup_webchannel, _teardown_webchannel
    web_view = _get_web_view(window)
    if web_view is None:
        return

    # ── Phase 1: pick the object via area drag ────────────────────────────
    pick_bridge = AreaPickBridge(window)
    _setup_webchannel(web_view, window, "areaPickBridge", pick_bridge)

    try:
        if hasattr(window, "status"):
            window.status.showMessage("Click/kéo vào vùng text/ảnh muốn chọn... (Esc để hủy)", 0)
        picked_object = _do_area_pick(web_view, pick_bridge, window)
        if hasattr(window, "status"):
            window.status.showMessage("", 0)
        if not picked_object:
            return

        target_op = _find_op_at_pick(state, picked_object)
        if not target_op:
            show_warning(
                window,
                "Không tìm thấy",
                "Không xác định được đối tượng tại vị trí đó.\nHãy kéo chọn vùng chứa text hoặc ảnh đã chèn.",
            )
            return
    finally:
        web_view.page().runJavaScript(_CLEAR_BRIDGE_CACHE_JS)
        _teardown_webchannel(web_view)

    # ── Phase 2: show Foxit-style handles overlay ─────────────────────────
    _run_object_action_session(window, state, target_op, web_view)
    return

@require_document(show_message=True)
def edit_text_object(window):
    """Click vào text đã chèn để sửa nội dung hoặc định dạng."""
    state = _ensure_edit_state(window)
    if not state:
        return

    text_ops = [op for op in state.get("ops", []) if op.get("type") == "text"]
    if not text_ops:
        show_warning(window, "Chưa có văn bản", "Chưa có văn bản nào được chèn để sửa.")
        return

    if hasattr(window, "status"):
        window.status.showMessage("Click vào văn bản muốn sửa... (Esc để hủy)", 0)

    picked = _pick_pdf_area(window)

    if hasattr(window, "status"):
        window.status.showMessage("", 0)

    if not picked:
        return

    target_op = _find_op_at_pick(state, picked)
    if not target_op or target_op.get("type") != "text":
        show_warning(window, "Không tìm thấy", "Không tìm thấy văn bản tại vị trí đó.")
        return

    color_tuple = target_op.get("font_color", (0.0, 0.0, 0.0))
    dlg_edit = _TextEditDialog(
        window,
        text=target_op.get("text", ""),
        font_size=target_op.get("font_size", 14),
        color_tuple=color_tuple,
        bold=target_op.get("bold", False),
        underline=target_op.get("underline", False),
    )
    if dlg_edit.exec() != QDialog.DialogCode.Accepted:
        return
    new_text = dlg_edit.get_text()
    if not new_text:
        return

    target_op["text"]       = new_text
    target_op["font_size"]  = dlg_edit.get_font_size()
    target_op["font_color"] = dlg_edit.get_color_tuple()
    target_op["bold"]      = dlg_edit.get_bold()
    target_op["underline"] = dlg_edit.get_underline()

    _render_edit_state(window, state, "Đã cập nhật văn bản",
                       focus_page=int(target_op.get("page_number", 1)))
