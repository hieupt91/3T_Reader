import os
import shutil
import tempfile
import uuid

from packages.qt_compat.QtCore import QObject, QEventLoop, QTimer, pyqtSignal, pyqtSlot
from packages.qt_compat.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
)

from app.actions.file import open_file
from app.actions._guard import require_document
from app.actions._pdf_save import (
    atomic_copy_file,
    collect_active_pdf_temp_paths,
    prune_stale_app_temp_files,
    reload_document,
)
from app.dialogs import show_warning
from packages.pdf_engine import get_pdf_engine

A4_WIDTH_PT = 595
A4_HEIGHT_PT = 842

# Area pick script loaded from assets/js/area_pick.js (single source of truth).
from app.js_loader import load_js as _load_js
AREA_PICK_SCRIPT = _load_js("area_pick.js")

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
# Communicates with Python via QWebChannel objectActionBridge.
_SHOW_OBJECT_WITH_HANDLES_JS = r"""(function(pageNum, pdfLeft, pdfBottom, pdfRight, pdfTop, currentRotation, hasEdit, opPayloadStr) {
    var _cleanedUp = false;
    var _dragging  = false;
    var _resizing  = false;
    var _actionBridge = null;

    function withActionBridge(callback) {
        if (_actionBridge) {
            callback(_actionBridge);
            return;
        }
        if (typeof window.__3tWithBridge !== 'function') {
            setTimeout(function() { withActionBridge(callback); }, 50);
            return;
        }
        window.__3tWithBridge('objectActionBridge', function(bridge) {
            _actionBridge = bridge || null;
            callback(_actionBridge);
        });
    }

    function reportAction(obj) {
        withActionBridge(function(bridge) {
            if (!bridge) return;
            try {
                if (obj.type === 'rotate') bridge.reportRotation(Number(obj.angle || 0));
                else if (obj.type === 'drag_move') bridge.reportDragMove(obj.box[0], obj.box[1], obj.box[2], obj.box[3]);
                else if (obj.type === 'resize') bridge.reportResize(obj.box[0], obj.box[1], obj.box[2], obj.box[3], obj.scale || 1);
                else if (obj.type === 'delete') bridge.reportDelete();
                else if (obj.type === 'edit') bridge.reportEdit();
                else if (obj.type === 'move') bridge.reportMove();
                else if (obj.type === 'retry') bridge.reportRetry();
                else bridge.reportDismiss();
            } catch (_err) {
                console.error("WITH_BRIDGE_ERROR: " + _err);
            }
        });
    }

    function onDocClick(e) {
        if (_dragging || _resizing) return;
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
        if (opPayload && opPayload.id !== undefined && opPayload.id !== null) {
            document.querySelectorAll('.__3t-op-overlay[data-op-id="' + String(opPayload.id) + '"]').forEach(function(el) {
                el.style.visibility = '';
            });
        }
        var g = document.getElementById('__3tObjGroup');
        if (g) {
            var handles = g.querySelectorAll('div[id^="__3t"]');
            for (var i=0; i<handles.length; i++) {
                handles[i].style.display = 'none';
            }
            var boxes = g.querySelectorAll('div');
            for (var j=0; j<boxes.length; j++) {
                if (boxes[j].style.border && boxes[j].style.border.indexOf('solid') > -1) {
                    boxes[j].style.border = 'none';
                    boxes[j].style.background = 'transparent';
                }
            }
        }
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
    if (!app || !app.pdfViewer) {
        reportAction({type:'retry'});
        return;
    }
    var pdfViewer = app.pdfViewer;
    var pageView  = pdfViewer.getPageView
        ? pdfViewer.getPageView(pageNum - 1)
        : (pdfViewer._pages && pdfViewer._pages[pageNum - 1]);
    if (!pageView || !pageView.viewport || !pageView.div) {
        reportAction({type:'retry'});
        return;
    }

    var vp     = pageView.viewport;
    var coords = vp.convertToViewportRectangle([pdfLeft, pdfBottom, pdfRight, pdfTop]);
    var pageEl = pageView.div;

    var bx = Math.min(coords[0], coords[2]);
    var by = Math.min(coords[1], coords[3]);
    var bw = Math.abs(coords[2] - coords[0]);
    var bh = Math.abs(coords[3] - coords[1]);
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

    // Selection box
    var box = document.createElement('div');
    box.style.cssText = 'position:absolute;'
        + 'left:'+pad+'px;top:'+pad+'px;width:'+bw+'px;height:'+bh+'px;'
        + 'border:2px solid #0B84F3;background:rgba(11,132,243,0.06);'
        + 'pointer-events:none;box-sizing:border-box;overflow:hidden;';
        
    var opPayload = null;
    if (typeof opPayloadStr === 'string' && opPayloadStr.length > 0) {
        try { opPayload = JSON.parse(opPayloadStr); } catch(e) {}
    }
    if (opPayload && opPayload.id !== undefined && opPayload.id !== null) {
        document.querySelectorAll('.__3t-op-overlay[data-op-id="' + String(opPayload.id) + '"]').forEach(function(el) {
            el.style.visibility = 'hidden';
        });
    }
    
    if (opPayload) {
        if (opPayload.type === 'image' && opPayload.image_path) {
            var img = document.createElement('img');
            img.src = opPayload.image_data_url || ('file://' + opPayload.image_path);
            img.style.cssText = 'width:100%%;height:100%%;object-fit:contain;opacity:0.6;';
            box.appendChild(img);
        } else if (opPayload.type === 'text') {
            var txt = document.createElement('div');
            txt.textContent = opPayload.text || '';
            var r = opPayload.font_color ? Math.round(opPayload.font_color[0]*255) : 0;
            var g = opPayload.font_color ? Math.round(opPayload.font_color[1]*255) : 0;
            var b = opPayload.font_color ? Math.round(opPayload.font_color[2]*255) : 0;
            var fontFam = opPayload.font_family || 'sans-serif';
            txt.style.cssText = 'width:100%%;height:100%%;display:flex;align-items:flex-start;justify-content:flex-start;'
                + 'color:rgba('+r+','+g+','+b+',0.78);'
                + 'font-weight:'+(opPayload.bold?'bold':'normal')+';'
                + 'text-decoration:'+(opPayload.underline?'underline':'none')+';'
                + 'font-style:'+(opPayload.italic?'italic':'normal')+';'
                + 'font-family:'+fontFam+';white-space:pre-wrap;overflow:hidden;';
            var fs = (opPayload.font_size || 14) * (vp.scale || 1.0) * 1.333;
            txt.style.fontSize = fs + 'px';
            txt.style.lineHeight = '1.15';
            txt.style.padding = '0';
            box.appendChild(txt);
        }
    }
    
    grp.appendChild(box);

    function syncGeometry(newWidth, newHeight) {
        bw = Math.max(1, newWidth);
        bh = Math.max(1, newHeight);
        grp.style.width = (bw + 2 * pad) + 'px';
        grp.style.height = (bh + 2 * pad) + 'px';
        grp.style.transformOrigin = (pad + bw / 2) + 'px ' + (pad + bh / 2) + 'px';
        box.style.width = bw + 'px';
        box.style.height = bh + 'px';
        angleLbl.style.left = (pad + bw / 2) + 'px';
        angleLbl.style.top = (pad + bh / 2) + 'px';
    }

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
        if (corner === 'mr') pos = 'right:0;top:50%%;transform:translateY(-50%%);';
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

    var resizeH = mkH('__3tResizeHandle', '&#8645;', 'Kéo để thu phóng', 'mr', '#8B5CF6', 'nwse-resize', 14);
    grp.appendChild(resizeH);

    // Rotation drag
    rotH.addEventListener('mousedown', function(e) {
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
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup',   onUp);
            setTimeout(function() { _dragging = false; }, 100);
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

    resizeH.addEventListener('mousedown', function(e) {
        e.preventDefault(); e.stopPropagation();
        _resizing = true;
        resizeH.style.cursor = 'nwse-resize';

        var startX = e.clientX;
        var startY = e.clientY;
        var startW = bw;
        var startH = bh;
        var startLeft = parseFloat(grp.style.left) || 0;
        var startTop = parseFloat(grp.style.top) || 0;
        var startRotation = currentRotation || 0;
        var cap = document.createElement('div');
        cap.style.cssText = 'position:fixed;inset:0;z-index:99999;cursor:nwse-resize;';
        document.body.appendChild(cap);

        function onMove(e2) {
            var dx = e2.clientX - startX;
            var dy = e2.clientY - startY;
            var rad = -startRotation * Math.PI / 180.0;
            var localDx = dx * Math.cos(rad) - dy * Math.sin(rad);
            var localDy = dx * Math.sin(rad) + dy * Math.cos(rad);
            var newW = Math.max(20, startW + localDx);
            var newH = Math.max(20, startH + localDy);
            syncGeometry(newW, newH);
            
            if (opPayload && opPayload.type === 'text') {
                var scaleX = newW / startW;
                var scaleY = newH / startH;
                var rawScale = (scaleX >= 1.0 && scaleY >= 1.0)
                    ? Math.max(scaleX, scaleY)
                    : Math.min(scaleX, scaleY);
                var scale = Math.max(0.25, Math.min(6.0, rawScale));
                var txt = box.querySelector('div');
                if (txt) {
                    var baseFs = (opPayload.font_size || 14) * (vp.scale || 1.0) * 1.333;
                    txt.style.fontSize = (baseFs * scale) + 'px';
                }
            }
        }
        function onUp() {
            cap.removeEventListener('mousemove', onMove);
            cap.removeEventListener('mouseup', onUp);
            if (cap.parentNode) cap.parentNode.removeChild(cap);
            setTimeout(function() { _resizing = false; }, 100);
            resizeH.style.cursor = 'nwse-resize';

            var nLeft = parseFloat(grp.style.left) + pad;
            var nTop = parseFloat(grp.style.top) + pad;
            var newBw = parseFloat(box.style.width) || bw;
            var newBh = parseFloat(box.style.height) || bh;
            var p1 = vp.convertToPdfPoint(nLeft, nTop);
            var p2 = vp.convertToPdfPoint(nLeft + newBw, nTop + newBh);
            var newL = Math.min(p1[0], p2[0]);
            var newB = Math.min(p1[1], p2[1]);
            var newR = Math.max(p1[0], p2[0]);
            var newT = Math.max(p1[1], p2[1]);
            var scaleX = newBw / startW;
            var scaleY = newBh / startH;
            var rawScale = (scaleX >= 1.0 && scaleY >= 1.0)
                ? Math.max(scaleX, scaleY)
                : Math.min(scaleX, scaleY);
            var scale = Math.max(0.25, Math.min(6.0, rawScale));
            cleanupAll();
            try {
                reportAction({type:'resize', box: [newL, newB, newR, newT], scale: scale});
            } catch(err) {
                console.error("RESIZE_ERROR: " + err);
            }
        }
        cap.addEventListener('mousemove', onMove);
        cap.addEventListener('mouseup', onUp);
    });

    // Move drag
    mvH.addEventListener('mousedown', function(e) {
        e.preventDefault(); e.stopPropagation();
        _dragging = true;
        mvH.style.cursor = 'grabbing';
        
        var startX = e.clientX;
        var startY = e.clientY;
        var startLeft = parseFloat(grp.style.left) || 0;
        var startTop = parseFloat(grp.style.top) || 0;
        
        var cap = document.createElement('div');
        cap.style.cssText = 'position:fixed;inset:0;z-index:99999;cursor:grabbing;';
        document.body.appendChild(cap);

        function onMove(e2) {
            grp.style.left = (startLeft + e2.clientX - startX) + 'px';
            grp.style.top  = (startTop + e2.clientY - startY) + 'px';
        }
        function onUp(e2) {
            cap.removeEventListener('mousemove', onMove);
            cap.removeEventListener('mouseup', onUp);
            if(cap.parentNode) cap.parentNode.removeChild(cap);
            setTimeout(function() { _dragging = false; }, 100);
            mvH.style.cursor = 'move';
            
            // Calculate new PDF coords
            var nLeft = parseFloat(grp.style.left) + pad;
            var nTop = parseFloat(grp.style.top) + pad;
            var p1 = vp.convertToPdfPoint(nLeft, nTop);
            var p2 = vp.convertToPdfPoint(nLeft + bw, nTop + bh);
            var newL = Math.min(p1[0], p2[0]);
            var newB = Math.min(p1[1], p2[1]);
            var newR = Math.max(p1[0], p2[0]);
            var newT = Math.max(p1[1], p2[1]);
            
            console.info("DRAG_MOVE_CALC: nLeft=" + nLeft + " nTop=" + nTop + " p1=" + p1 + " p2=" + p2);
            console.info("DRAG_MOVE_CALC: newL=" + newL + " newB=" + newB + " newR=" + newR + " newT=" + newT);
            
            cleanupAll();
            try {
                reportAction({type:'drag_move', box: [newL, newB, newR, newT]});
                console.info("DRAG_MOVE_REPORTED");
            } catch(e) {
                console.error("DRAG_MOVE_ERROR: " + e);
            }
        }
        cap.addEventListener('mousemove', onMove);
        cap.addEventListener('mouseup', onUp);
    });
})(%d, %f, %f, %f, %f, %d, %s, `%s`);"""

_CLEAR_OBJECT_HANDLES_JS = """(function() {
    var el = document.getElementById('__3tObjGroup');
    if (el && el.parentNode) el.parentNode.removeChild(el);
    if (typeof window.__3tObjCleanup === 'function') window.__3tObjCleanup();
})();"""

_SHOW_TEXT_EDIT_LIVE_PREVIEW_JS = r"""(function(opPayloadStr) {
    var existing = document.getElementById('__3tTextEditLivePreview');
    if (existing && existing.parentNode) existing.parentNode.removeChild(existing);

    var op = null;
    try { op = JSON.parse(opPayloadStr); } catch(e) { return; }
    if (!op || !op.box || op.type !== 'text') return;

    if (op.id !== undefined && op.id !== null) {
        document.querySelectorAll('.__3t-op-overlay[data-op-id="' + String(op.id) + '"]').forEach(function(el) {
            el.style.visibility = 'hidden';
        });
    }

    var app = window.PDFViewerApplication;
    if (!app || !app.pdfViewer) return;
    var pageView = app.pdfViewer.getPageView
        ? app.pdfViewer.getPageView((op.page_number || 1) - 1)
        : (app.pdfViewer._pages && app.pdfViewer._pages[(op.page_number || 1) - 1]);
    if (!pageView || !pageView.viewport || !pageView.div) return;

    var vp = pageView.viewport;
    var coords = vp.convertToViewportRectangle([op.box[0], op.box[1], op.box[2], op.box[3]]);
    var bx = Math.min(coords[0], coords[2]);
    var by = Math.min(coords[1], coords[3]);
    var bw = Math.abs(coords[2] - coords[0]);
    var bh = Math.abs(coords[3] - coords[1]);

    var ov = document.createElement('div');
    ov.id = '__3tTextEditLivePreview';
    ov.style.cssText = 'position:absolute;left:'+bx+'px;top:'+by+'px;width:'+bw+'px;height:'+bh+'px;'
        + 'z-index:55;pointer-events:none;transform-origin:'+(bw/2)+'px '+(bh/2)+'px;';
    if (op.rotation) ov.style.transform = 'rotate('+op.rotation+'deg)';

    var txt = document.createElement('div');
    txt.textContent = op.text || '';
    var c = op.font_color || [0,0,0];
    var r = Math.round(c[0]*255), g = Math.round(c[1]*255), b = Math.round(c[2]*255);
    var fontFam = op.font_family || 'sans-serif';
    txt.style.cssText = 'width:100%;height:100%;display:flex;align-items:flex-start;justify-content:flex-start;'
        + 'color:rgb('+r+','+g+','+b+');'
        + 'font-weight:'+(op.bold?'bold':'normal')+';'
        + 'text-decoration:'+(op.underline?'underline':'none')+';'
        + 'font-style:'+(op.italic?'italic':'normal')+';'
        + 'font-family:'+fontFam+';white-space:pre-wrap;overflow:hidden;padding:0;';
    var fs = (op.font_size || 14) * (vp.scale || 1.0) * 1.333;
    txt.style.fontSize = fs + 'px';
    txt.style.lineHeight = '1.15';
    ov.appendChild(txt);
    pageView.div.appendChild(ov);
})(`%s`);"""

_CLEAR_TEXT_EDIT_LIVE_PREVIEW_JS = """(function() {
    var el = document.getElementById('__3tTextEditLivePreview');
    if (el && el.parentNode) el.parentNode.removeChild(el);
    document.querySelectorAll('.__3t-op-overlay').forEach(function(overlay) {
        overlay.style.visibility = '';
    });
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
    dragMoveConfirmed = pyqtSignal(float, float, float, float)
    resizeConfirmed = pyqtSignal(float, float, float, float, float)
    dismissed       = pyqtSignal()
    retryRequested  = pyqtSignal()

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

    @pyqtSlot(float, float, float, float)
    def reportDragMove(self, l, b, r, t):
        self.dragMoveConfirmed.emit(l, b, r, t)

    @pyqtSlot(float, float, float, float, float)
    def reportResize(self, l, b, r, t, scale):
        self.resizeConfirmed.emit(l, b, r, t, scale)

    @pyqtSlot()
    def reportDismiss(self):
        self.dismissed.emit()

    @pyqtSlot()
    def reportRetry(self):
        self.retryRequested.emit()


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


def _is_pdf_file(path: str | None) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"%PDF"
    except OSError:
        return False


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
    
    try:
        if hasattr(window, "viewer") and hasattr(window.viewer, "update_ops"):
            window.viewer.update_ops("[]")
    except Exception:
        pass


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
    state_obj = window._state_or_global() if hasattr(window, "_state_or_global") else None
    if state:
        base_snapshot = state.get("base_snapshot")
        if base_snapshot and not _is_pdf_file(base_snapshot):
            _reset_edit_state(window)
            state = None

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
            warning_key = os.path.abspath(current)
            if warning_key not in warned:
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
                warned.add(warning_key)
                if hasattr(window, "status"):
                    window.status.showMessage(
                        "Tài liệu có chữ ký số; chỉnh sửa PDF có thể làm chữ ký mất hiệu lực.",
                        5000,
                    )
    except Exception:
        pass

    display_path = window.get_display_path() if hasattr(window, "get_display_path") else None
    temp_root = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    snapshot_source = current
    try:
        current_abs = os.path.abspath(current)
        temp_root_abs = os.path.abspath(temp_root)
        if (
            current_abs.startswith(temp_root_abs + os.sep)
            and os.path.basename(current_abs).lower().startswith(("op_", "work_", "base_"))
        ):
            source_path = state_obj.get("source_path") if isinstance(state_obj, dict) else None
            if _is_pdf_file(source_path):
                snapshot_source = source_path
            elif _is_pdf_file(display_path):
                snapshot_source = display_path
    except Exception:
        snapshot_source = current

    if not _is_pdf_file(snapshot_source):
        source_path = state_obj.get("source_path") if isinstance(state_obj, dict) else None
        if _is_pdf_file(source_path):
            snapshot_source = source_path
        elif _is_pdf_file(display_path):
            snapshot_source = display_path
        else:
            show_warning(window, "Không thể chỉnh sửa", "Không tìm thấy bản PDF hợp lệ để bắt đầu phiên chỉnh sửa.")
            return None

    try:
        from app.actions.annotate import _flush_annotations_before_heavy_op

        if not _flush_annotations_before_heavy_op(window, snapshot_source, "chinh sua PDF"):
            return None
    except Exception:
        pass

    _reset_edit_state(window)

    edit_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(edit_dir, exist_ok=True)
    try:
        prune_stale_app_temp_files(active_paths=collect_active_pdf_temp_paths(window))
    except Exception:
        pass
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


def _reload_viewer(window, pdf_path: str, page: int | None = None, ops_json: str = "[]", erase_json: str = "[]"):
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
            zoom = str(getattr(getattr(window, "zoom_spin", None), "value", lambda: 100)())
            if hasattr(window.viewer, "reload_soft"):
                window.viewer.reload_soft(pdf_path, page=page, zoom=zoom, ops_json=ops_json, erase_json=erase_json)
            else:
                window.viewer.load_pdf(pdf_path, page=page, zoom=zoom)
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


def _show_text_edit_live_preview(window, op: dict):
    try:
        import json
        from app.actions.sign import _get_web_view
        web_view = _get_web_view(window)
        if web_view is None:
            return
        payload = json.dumps(op).replace("\\", "\\\\").replace("`", "\\`")
        web_view.page().runJavaScript(_SHOW_TEXT_EDIT_LIVE_PREVIEW_JS.replace("%s", payload, 1))
    except Exception:
        pass


def _clear_text_edit_live_preview(window):
    try:
        from app.actions.sign import _get_web_view
        web_view = _get_web_view(window)
        if web_view is not None:
            web_view.page().runJavaScript(_CLEAR_TEXT_EDIT_LIVE_PREVIEW_JS)
    except Exception:
        pass


def _render_edit_state(
    window,
    state,
    status_message: str,
    focus_page: int | None = None,
    auto_select_op: dict | None = None,
    erase_boxes: list | None = None,
):
    """Rebuild working file from base + all ops, then reload viewer in-place."""
    base_snapshot = state.get("base_snapshot")
    ops = state.get("ops") or []
    if not base_snapshot or not os.path.exists(base_snapshot):
        show_warning(window, "Không thể chỉnh sửa", "Thiếu bản gốc để dựng lại tài liệu.")
        return None

    previous_working_file = state.get("working_file")
    if not previous_working_file:
        show_warning(window, "Không thể chỉnh sửa", "Thiếu file làm việc.")
        return None
    working_dir = os.path.dirname(os.path.abspath(previous_working_file)) or tempfile.gettempdir()
    working_file = os.path.join(working_dir, f"work_{uuid.uuid4().hex[:8]}.pdf")

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

    state["working_file"] = working_file

    # Xóa file working cũ để tránh rò rỉ
    if previous_working_file and previous_working_file != working_file:
        try:
            if os.path.exists(previous_working_file):
                os.remove(previous_working_file)
        except OSError:
            pass

    import json
    ops_json = json.dumps(state.get("ops", []))
    if hasattr(window.viewer, "update_ops"):
        window.viewer.update_ops(ops_json)

    if auto_select_op is not None:
        from packages.qt_compat.QtCore import QTimer
        QTimer.singleShot(50, lambda: _run_object_action_session(window, state, auto_select_op))

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
    try:
        # Dismiss any active object selection box before undoing
        from app.actions.sign import _get_web_view
        web_view = _get_web_view(window)
        if web_view is not None:
            web_view.page().runJavaScript("if(window.__3tObjectActionBridge && window.__3tObjectActionBridge.dismissed) window.__3tObjectActionBridge.dismissed();")
    except Exception:
        pass

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

    # Prefer the newest op when overlap ties. Repeated existing-text edits can
    # stack multiple ops over nearly the same area, and selecting the oldest
    # one makes the UI box drift away from the text that is actually visible.
    def overlap_area(op):
        l, b, r, t = op.get("box", (0, 0, 0, 0))
        ow = max(0.0, min(pr, r) - max(pl, l))
        oh = max(0.0, min(pt, t) - max(pb, b))
        return ow * oh

    best_index = None
    best_overlap = -1.0
    for idx, op in enumerate(candidates):
        current_overlap = overlap_area(op)
        if current_overlap > best_overlap or (current_overlap == best_overlap and idx > (best_index or -1)):
            best_overlap = current_overlap
            best_index = idx
    best = candidates[best_index] if best_index is not None else None
    if best is not None and best_overlap > 0:
        return best

    # Fallback: nearest center.
    cx = (pl + pr) / 2.0
    cy = (pb + pt) / 2.0

    def dist2(op):
        l, b, r, t = op.get("box", (0, 0, 0, 0))
        ox = (l + r) / 2.0
        oy = (b + t) / 2.0
        return (ox - cx) ** 2 + (oy - cy) ** 2

    best_index = None
    best_dist = None
    for idx, op in enumerate(candidates):
        current_dist = dist2(op)
        if best_dist is None or current_dist < best_dist or (current_dist == best_dist and idx > (best_index or -1)):
            best_dist = current_dist
            best_index = idx
    return candidates[best_index] if best_index is not None else None


def _sync_text_anchor_after_transform(op: dict, old_box, new_box, *, drop_baseline: bool = False) -> None:
    """Keep text anchors coherent after UI transforms.

    Existing-text edits may store a `baseline` so the initial replacement lands
    exactly over the original glyphs. Once the user starts moving/resizing/
    rotating that object, the baseline anchor must be updated or dropped,
    otherwise the on-screen selection box and the saved PDF diverge.
    """
    if op.get("type") != "text":
        return
    if drop_baseline:
        op.pop("baseline", None)
        op.pop("single_line", None)
        return

    baseline = op.get("baseline")
    if not baseline:
        return
    try:
        old_left, old_bottom, _old_right, _old_top = [float(v) for v in old_box]
        new_left, new_bottom, _new_right, _new_top = [float(v) for v in new_box]
        bx, by = [float(v) for v in baseline[:2]]
    except Exception:
        op.pop("baseline", None)
        op.pop("single_line", None)
        return

    op["baseline"] = (bx + (new_left - old_left), by + (new_bottom - old_bottom))


def _run_object_action_session(window, state, target_op, web_view=None, retry_count: int = 0):
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

    # Wait for the typed QWebChannel object action result.
    action_result = {}
    loop = QEventLoop(window)
    action_bridge = ObjectActionBridge(window)
    _setup_webchannel(web_view, window, "objectActionBridge", action_bridge)

    def _finish(action_type: str, **payload):
        if action_result:
            return
        action_result["type"] = action_type
        action_result.update(payload)
        if loop.isRunning():
            loop.quit()

    action_bridge.rotateConfirmed.connect(lambda angle: _finish("rotate", angle=angle))
    action_bridge.dragMoveConfirmed.connect(lambda l, b, r, t: _finish("drag_move", box=(l, b, r, t)))
    action_bridge.resizeConfirmed.connect(lambda l, b, r, t, scale: _finish("resize", box=(l, b, r, t), scale=scale))
    action_bridge.deleteConfirmed.connect(lambda: _finish("delete"))
    action_bridge.editConfirmed.connect(lambda: _finish("edit"))
    action_bridge.moveRequested.connect(lambda: _finish("move"))
    action_bridge.retryRequested.connect(lambda: _finish("retry"))
    action_bridge.dismissed.connect(lambda: _finish("dismiss"))

    def _js_ran(_result):
        pass

    import json
    try:
        payload_str = json.dumps(target_op).replace("\\", "\\\\").replace("`", "\\`")
        js = _SHOW_OBJECT_WITH_HANDLES_JS % (
            page_num, left, bottom, right, top,
            current_rot, "true" if op_type == "text" else "false",
            payload_str
        )
        web_view.page().runJavaScript(js, _js_ran)
        QTimer.singleShot(10_000, lambda: _finish("dismiss"))
        loop.exec()
    finally:
        web_view.page().runJavaScript(_CLEAR_OBJECT_HANDLES_JS)
        _teardown_webchannel(web_view)
        _clear_object_overlay(window)

    action = action_result.get("type", "dismiss")

    if action == "retry":
        if retry_count >= 8:
            if hasattr(window, "status"):
                window.status.showMessage("Chưa hiển thị được khung chọn. Vui lòng thử lại sau khi trang tải xong.", 3500)
            return
        QTimer.singleShot(250, lambda: _run_object_action_session(window, state, target_op, web_view, retry_count + 1))
        return

    if action == "dismiss":
        return

    if action == "rotate":
        old_box = target_op["box"]
        angle = int(action_result.get("angle", 0)) % 360
        target_op["rotation"] = angle
        _sync_text_anchor_after_transform(target_op, old_box, old_box, drop_baseline=True)
        _render_edit_state(window, state, f"Đã xoay {angle}°", focus_page=page_num, auto_select_op=target_op, erase_boxes=[{"page_number": target_op.get("page_number", page_num), "box": old_box}])
        return

    if action == "drag_move":
        old_box = target_op["box"]
        l, b, r, t = action_result["box"]
        target_op["box"] = (l, b, r, t)
        _sync_text_anchor_after_transform(target_op, old_box, target_op["box"])
        _render_edit_state(window, state, "Đã di chuyển đối tượng", focus_page=page_num, auto_select_op=target_op, erase_boxes=[{"page_number": target_op.get("page_number", page_num), "box": old_box}])
        return

    if action == "resize":
        old_box = target_op["box"]
        l, b, r, t = action_result["box"]
        scale = float(action_result.get("scale", 1.0) or 1.0)
        target_op["box"] = (l, b, r, t)
        if op_type == "text":
            current_size = float(target_op.get("font_size", 14) or 14)
            target_op["font_size"] = max(4.0, min(120.0, current_size * scale))
            _sync_text_anchor_after_transform(target_op, old_box, target_op["box"], drop_baseline=True)
        _render_edit_state(window, state, "Đã thay đổi kích thước đối tượng", focus_page=page_num, auto_select_op=target_op, erase_boxes=[{"page_number": target_op.get("page_number", page_num), "box": old_box}])
        return

    if action == "delete":
        old_box = target_op["box"]
        page_n = target_op.get("page_number", page_num)
        op_label = "văn bản" if op_type == "text" else "ảnh"
        state["ops"].remove(target_op)
        if not state["ops"]:
            original = state.get("original_path")
            _reset_edit_state(window)
            if hasattr(window.viewer, "update_ops"):
                window.viewer.update_ops("[]")
            window.status.showMessage(f"Đã xóa {op_label} — tài liệu về trạng thái gốc", 3000)
        else:
            _render_edit_state(window, state, f"Đã xóa {op_label}", erase_boxes=[{"page_number": page_n, "box": old_box}])
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
            italic=target_op.get("italic", False),
            font_family=target_op.get("font_family", "sans-serif"),
        )
        def _refresh_preview():
            preview_op = dict(target_op)
            preview_op["text"] = dlg_edit._text_edit.toPlainText()
            preview_op["font_size"] = dlg_edit.get_font_size()
            preview_op["font_color"] = dlg_edit.get_color_tuple()
            preview_op["bold"] = dlg_edit.get_bold()
            preview_op["underline"] = dlg_edit.get_underline()
            preview_op["italic"] = dlg_edit.get_italic()
            preview_op["font_family"] = dlg_edit.get_font_family()
            _show_text_edit_live_preview(window, preview_op)

        dlg_edit.previewChanged.connect(_refresh_preview)
        _refresh_preview()
        try:
            accepted = dlg_edit.exec() == QDialog.DialogCode.Accepted
        finally:
            _clear_text_edit_live_preview(window)
        if not accepted:
            return
        new_text = dlg_edit.get_text()
        if not new_text:
            return

        old_box = target_op["box"]
        target_op["text"] = new_text
        target_op["font_size"] = dlg_edit.get_font_size()
        target_op["font_color"] = dlg_edit.get_color_tuple()
        target_op["bold"] = dlg_edit.get_bold()
        target_op["underline"] = dlg_edit.get_underline()
        target_op["italic"] = dlg_edit.get_italic()
        target_op["font_family"] = dlg_edit.get_font_family()
        _render_edit_state(window, state, "Đã cập nhật văn bản", focus_page=page_num, erase_boxes=[{"page_number": target_op.get("page_number", page_num), "box": old_box}])
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
        old_box = target_op["box"]
        old_page = target_op.get("page_number", page_num)
        target_op["page_number"] = int(new_area["page_number"])
        target_op["box"] = (l, b, r, t)
        _render_edit_state(window, state, "Đã cập nhật vị trí/kích thước đối tượng", erase_boxes=[{"page_number": old_page, "box": old_box}])


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

    def __init__(self, parent=None, *, title: str = "Chèn đối tượng", note: str = "", is_edit: bool = False):
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
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("Lưu thay đổi" if is_edit else "Chèn")
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

    previewChanged = pyqtSignal()

    def __init__(self, parent=None, *, text="", font_size=14,
                 color_tuple=(0.0, 0.0, 0.0), bold=False, underline=False,
                 italic=False, font_family=""):
        from packages.qt_compat.QtCore import Qt
        from packages.qt_compat.QtGui import QColor
        from packages.qt_compat.QtWidgets import QFontComboBox

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

        fmt_row.addWidget(QLabel("Font:"))
        from packages.qt_compat.QtWidgets import QComboBox
        self._font_combo = QComboBox()
        self._font_combo.addItems(["Arial", "Times New Roman", "Calibri", "Tahoma", "Segoe UI", "Cambria", "Consolas", "Verdana", "Courier New", "Comic Sans MS"])
        self._font_combo.setFixedWidth(120)
        if font_family:
            self._font_combo.setCurrentText(font_family)
        self._font_combo.currentTextChanged.connect(lambda _f: self.previewChanged.emit())
        fmt_row.addWidget(self._font_combo)

        fmt_row.addWidget(QLabel("Cỡ chữ:"))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 96)
        self._size_spin.setValue(font_size)
        self._size_spin.setFixedWidth(64)
        self._size_spin.valueChanged.connect(lambda _value: self.previewChanged.emit())
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
        self._bold_btn.toggled.connect(lambda _checked: self.previewChanged.emit())
        fmt_row.addWidget(self._bold_btn)

        self._under_btn = QToolButton()
        self._under_btn.setText("U")
        self._under_btn.setCheckable(True)
        self._under_btn.setChecked(underline)
        self._under_btn.setStyleSheet(_fmt_ss.replace("font-weight:700", "font-weight:400"))
        self._under_btn.toggled.connect(lambda _checked: self.previewChanged.emit())
        fmt_row.addWidget(self._under_btn)

        self._italic_btn = QToolButton()
        self._italic_btn.setText("I")
        self._italic_btn.setCheckable(True)
        self._italic_btn.setChecked(italic)
        self._italic_btn.setStyleSheet(_fmt_ss.replace("font-weight:700", "font-weight:400; font-style:italic"))
        self._italic_btn.toggled.connect(lambda _checked: self.previewChanged.emit())
        fmt_row.addWidget(self._italic_btn)

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
            "QPushButton{background:#FF6600;color:white;border:none;"
            "border-radius:5px;padding:5px 14px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:#FF9900;}"
        )
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        root.addLayout(btn_row)

        self.adjustSize()
        self._position_near_parent(parent)

        self._text_edit.textChanged.connect(self.previewChanged.emit)

        from packages.qt_compat.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._text_edit.setFocus())

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Màu chữ")
        if c.isValid():
            self._color = c
            self._refresh_color_btn()
            self.previewChanged.emit()

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

    def get_italic(self) -> bool:
        if hasattr(self, "_italic_btn"):
            return self._italic_btn.isChecked()
        return False

    def get_font_family(self) -> str:
        if hasattr(self, "_font_combo"):
            return self._font_combo.currentText()
        return "Arial"

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
    expanded_box = False
    if abs(right - left) < 20:
        right = left + 180
        expanded_box = True
    if abs(top - bottom) < 12:
        top = bottom + 44
        expanded_box = True
    if expanded_box and hasattr(window, "status"):
        window.status.showMessage("Vùng chèn quá nhỏ, đã tự mở rộng đến kích thước tối thiểu.", 3000)

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
        "italic":     result.get("italic", False),
        "font_family": result.get("font_family", "sans-serif"),
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
        shutil.copy(image_path, staged)
        image_path = staged
    except OSError:
        pass  # keep original path if staging fails

    page_number = result["page_number"]
    left, bottom, right, top = result["box"]

    # Đảm bảo vùng tối thiểu
    expanded_box = False
    if abs(right - left) < 20:
        right = left + 150
        expanded_box = True
    if abs(top - bottom) < 20:
        top = bottom + 120
        expanded_box = True
    if expanded_box and hasattr(window, "status"):
        window.status.showMessage("Vùng chèn ảnh quá nhỏ, đã tự mở rộng đến kích thước tối thiểu.", 3000)
    box = (left, bottom, right, top)

    state = _ensure_edit_state(window)
    if not state:
        return

    import base64
    from packages.qt_compat.QtGui import QImage
    from packages.qt_compat.QtCore import QByteArray, QBuffer, QIODevice, Qt
    try:
        img = QImage(image_path)
        if not img.isNull():
            if img.width() > 500 or img.height() > 500:
                img = img.scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            ba = QByteArray()
            buffer = QBuffer(ba)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            
            has_alpha = img.hasAlphaChannel()
            if not has_alpha:
                img.save(buffer, "JPEG", 60)
                mime = "jpeg"
            else:
                img.save(buffer, "PNG")
                mime = "png"
                
            raw = ba.data()
            data_url = f"data:image/{mime};base64,{base64.b64encode(raw).decode()}"
        else:
            with open(image_path, "rb") as f:
                raw = f.read()
            ext_clean = ext.lstrip(".").lower()
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "bmp": "bmp", "webp": "webp"}.get(ext_clean, "png")
            has_alpha = False
            data_url = f"data:image/{mime};base64,{base64.b64encode(raw).decode()}"
    except Exception as _e:
        import traceback
        print(f"Exception in image base64 encoding: {_e}")
        traceback.print_exc()
        mime = "png"
        has_alpha = False
        data_url = ""

    op = {
        "id":             state["next_id"],
        "type":           "image",
        "page_number":    page_number,
        "box":            box,
        "image_path":     image_path,
        "image_data_url": data_url,
        "image_mime":     mime,
        "image_has_alpha": has_alpha,
        "rotation":       result.get("rotation", 0),
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
    annotations_were_pending = False
    annotation_saver = getattr(window, "annotation_saver", None)
    if annotation_saver is not None:
        try:
            has_pending = getattr(annotation_saver, "has_pending", None)
            annotations_were_pending = bool(has_pending()) if callable(has_pending) else False
        except Exception:
            annotations_were_pending = False
        try:
            flush_ok = annotation_saver.flush_all()
        except Exception as exc:
            show_warning(window, "Không lưu được", f"Không lưu được chú thích: {exc}")
            return False
        if flush_ok is False:
            show_warning(window, "Không lưu được", "Không lưu được chú thích đang chờ.")
            return False

    state = _get_edit_state(window)
    if not state:
        status = getattr(window, "status", None)
        if status is not None:
            message = "Đã lưu chú thích." if annotations_were_pending else "Không có thay đổi cần lưu."
            try:
                status.showMessage(message, 3000)
            except Exception:
                pass
        return True

    working = state.get("working_file")
    base = state.get("base_snapshot")
    original = state.get("original_path")

    if not working or not base or not os.path.exists(base):
        show_warning(window, "Không lưu được", "Không tìm thấy file làm việc.")
        return False

    # Rebuild lần cuối vào working file
    try:
        final_working = os.path.join(
            os.path.dirname(os.path.abspath(working)) or tempfile.gettempdir(),
            f"work_{uuid.uuid4().hex[:8]}.pdf",
        )
        get_pdf_engine().rebuild_pdf_with_ops(base, final_working, state.get("ops", []))
        state["working_file"] = final_working
        working = final_working
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
    _reset_edit_state(window)
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
    return save_edits(window, reload_viewer=False)


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
            rebuilt_src = os.path.join(
                os.path.dirname(os.path.abspath(src)) or tempfile.gettempdir(),
                f"work_{uuid.uuid4().hex[:8]}.pdf",
            )
            get_pdf_engine().rebuild_pdf_with_ops(base, rebuilt_src, state.get("ops", []))
            state["working_file"] = rebuilt_src
            # Xóa file working cũ
            if src != rebuilt_src and os.path.exists(src):
                try:
                    os.remove(src)
                except OSError:
                    pass
            src = rebuilt_src
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
        if hasattr(window.viewer, "update_ops"):
            window.viewer.update_ops("[]")
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
        show_warning(window, "Vùng quá nhỏ", "Vùng chọn tối thiểu là 4 x 4 pt. Hãy kéo để chọn vùng rộng hơn.")
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

    import base64
    try:
        with open(img_path, "rb") as f:
            raw = f.read()
        data_url = f"data:image/png;base64,{base64.b64encode(raw).decode()}"
    except Exception:
        data_url = ""

    op = {
        "id": state["next_id"],
        "type": "image",
        "page_number": page_number,
        "box": (left, bottom, right, top),
        "image_path": img_path,
        "image_data_url": data_url,
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
        italic=target_op.get("italic", False),
        font_family=target_op.get("font_family", "sans-serif"),
    )
    def _refresh_preview():
        preview_op = dict(target_op)
        preview_op["text"] = dlg_edit._text_edit.toPlainText()
        preview_op["font_size"] = dlg_edit.get_font_size()
        preview_op["font_color"] = dlg_edit.get_color_tuple()
        preview_op["bold"] = dlg_edit.get_bold()
        preview_op["underline"] = dlg_edit.get_underline()
        preview_op["italic"] = dlg_edit.get_italic()
        preview_op["font_family"] = dlg_edit.get_font_family()
        _show_text_edit_live_preview(window, preview_op)

    dlg_edit.previewChanged.connect(_refresh_preview)
    _refresh_preview()
    try:
        accepted = dlg_edit.exec() == QDialog.DialogCode.Accepted
    finally:
        _clear_text_edit_live_preview(window)
    if not accepted:
        return
    new_text = dlg_edit.get_text()
    if not new_text:
        return

    target_op["text"]       = new_text
    target_op["font_size"]  = dlg_edit.get_font_size()
    target_op["font_color"] = dlg_edit.get_color_tuple()
    target_op["bold"]      = dlg_edit.get_bold()
    target_op["underline"] = dlg_edit.get_underline()
    target_op["italic"]    = dlg_edit.get_italic()
    target_op["font_family"] = dlg_edit.get_font_family()

    _render_edit_state(window, state, "Đã cập nhật văn bản",
                       focus_page=int(target_op.get("page_number", 1)))


@require_document(show_message=True)
def edit_existing_text(window):
    """Edit existing text in the PDF by redacting it and inserting new text."""
    from packages.qt_compat.QtWidgets import QInputDialog
    import json
    import re

    class ExistingTextBridge(QObject):
        @pyqtSlot(int, float, float, float, float, str, str)
        def reportExistingTextClick(self, pageNum, left, bottom, right, top, text, styles_json):
            on_click(pageNum, left, bottom, right, top, text, styles_json, use_span_box=True)

        @pyqtSlot()
        def cancelExistingTextEdit(self):
            _stop_existing_text_click_mode()
            window.status.showMessage("", 0)

    def _existing_text_web_view():
        try:
            getter = getattr(window, "_get_webview", None)
            web_view = getter() if callable(getter) else None
            if web_view is not None:
                return web_view
        except Exception:
            pass
        try:
            return getattr(window.viewer, "_web_view", None)
        except Exception:
            return None

    def _stop_existing_text_click_mode():
        web_view = _existing_text_web_view()
        if web_view is None:
            return
        try:
            web_view.page().runJavaScript("window.__3tExistingTextMode = false;")
        except Exception:
            pass
        try:
            from app.webchannel import unregister_webchannel_object
            unregister_webchannel_object(web_view, "editExistingTextBridge")
        except Exception:
            pass
        try:
            window._existing_text_bridge = None
        except Exception:
            pass

    def _parse_font_size(styles: dict) -> float:
        try:
            font_size = float(styles.get("fontSizePt", 0) or 0)
            if font_size > 0:
                return max(6.0, min(96.0, font_size))
        except Exception:
            pass
        try:
            fs_px = float(str(styles.get("fontSize", "16px")).replace("px", ""))
            return max(6.0, min(96.0, fs_px * 0.75))
        except Exception:
            return 14.0

    def _parse_color(styles: dict) -> tuple[float, float, float]:
        try:
            m = re.search(
                r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",
                str(styles.get("color", "")),
            )
            if m:
                return (
                    int(m.group(1)) / 255.0,
                    int(m.group(2)) / 255.0,
                    int(m.group(3)) / 255.0,
                )
        except Exception:
            pass
        return (0.0, 0.0, 0.0)

    def _parse_bold(styles: dict) -> bool:
        try:
            fw = str(styles.get("fontWeight", ""))
            return fw in {"bold", "bolder"} or (fw.isdigit() and int(fw) >= 600)
        except Exception:
            return False

    def _parse_italic(styles: dict) -> bool:
        try:
            fs = str(styles.get("fontStyle", "")).lower()
            return "italic" in fs or "oblique" in fs
        except Exception:
            return False

    def _parse_underline(styles: dict) -> bool:
        try:
            td = str(styles.get("textDecoration", "")).lower()
            return "underline" in td
        except Exception:
            return False

    def _expanded_text_box(left: float, bottom: float, right: float, top: float, text: str, font_size: float, base_path: str, page_num: int):
        estimated_width = max(right - left, len(text) * font_size * 0.62)
        new_right = left + estimated_width
        min_height = max(top - bottom, font_size * 1.35)
        new_top = bottom + min_height
        try:
            doc = get_pdf_engine().open(base_path)
            try:
                page_width, page_height = doc.page_size(page_num)
            finally:
                doc.close()
            new_right = min(max(right, new_right), float(page_width))
            new_top = min(max(top, new_top), float(page_height))
        except Exception:
            new_right = max(right, new_right)
            new_top = max(top, new_top)
        return (left, bottom, new_right, new_top)

    def _find_pdf_span(base_path: str, page_num: int, pick_box: tuple[float, float, float, float], prefer_text: str = "") -> dict | None:
        # prefer_text: khi sửa nhiều lần, working_file có 2 span chồng nhau tại 1 vị
        # trí (text cũ bị che trắng + text mới overlay). Ưu tiên span CHỨA đúng text
        # đang chọn (text mới đang hiển thị) để không nhắm nhầm span cũ → hết chập chờn.
        prefer = (prefer_text or "").strip()
        try:
            import fitz
        except Exception:
            return None

        def _inter_area(a, b) -> float:
            x0 = max(a[0], b[0])
            y0 = max(a[1], b[1])
            x1 = min(a[2], b[2])
            y1 = min(a[3], b[3])
            return max(0.0, x1 - x0) * max(0.0, y1 - y0)

        def _center_distance(a, b) -> float:
            ax = (a[0] + a[2]) / 2.0
            ay = (a[1] + a[3]) / 2.0
            bx = (b[0] + b[2]) / 2.0
            by = (b[1] + b[3]) / 2.0
            return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

        doc = fitz.open(base_path)
        try:
            if page_num < 1 or page_num > doc.page_count:
                return None
            page = doc[page_num - 1]
            page_h = float(page.rect.height)
            best = None
            best_score = None
            best_overlap = 0.0
            for block in page.get_text("rawdict").get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_chars = span.get("chars", [])
                        text = "".join(str(ch.get("c", "")) for ch in span_chars)
                        if not text.strip():
                            continue
                        x0, y0, x1, y1 = [float(v) for v in span.get("bbox", (0, 0, 0, 0))]
                        # Convert bbox from page.rect space to unrotated PDF user space
                        cb = page.cropbox
                        p0 = fitz.Point(x0, y0) * page.derotation_matrix
                        p1 = fitz.Point(x1, y1) * page.derotation_matrix

                        pdf_x0 = min(p0.x, p1.x) + cb.x0
                        pdf_x1 = max(p0.x, p1.x) + cb.x0
                        pdf_y0 = cb.y1 - max(p0.y, p1.y) # bottom
                        pdf_y1 = cb.y1 - min(p0.y, p1.y) # top
                        span_box = (pdf_x0, pdf_y0, pdf_x1, pdf_y1)
                        overlap = _inter_area(pick_box, span_box)
                        distance = _center_distance(pick_box, span_box)
                        # Span chứa đúng text đang chọn được ưu tiên tuyệt đối (rank 0),
                        # sau đó mới xét overlap/khoảng cách.
                        text_rank = 0 if (prefer and prefer in text) else 1
                        score = (text_rank, -overlap, distance)
                        if best_score is None or score < best_score:
                            origin_x, origin_y = span.get("origin", (x0, y1))
                            color_int = int(span.get("color", 0) or 0)
                            font_name = str(span.get("font", ""))
                            span_flags = int(span.get("flags", 0) or 0)
                            # Convert origin from page.rect space to PDF user space
                            op_pt = fitz.Point(origin_x, origin_y) * page.derotation_matrix
                            pdf_ox = op_pt.x + cb.x0
                            pdf_oy = cb.y1 - op_pt.y
                            # Pen origin từng ký tự (PDF space) — để canh chính xác
                            # điểm bắt đầu khi thay text ở GIỮA dòng.
                            char_origins = []
                            char_boxes = []
                            for ch in span_chars:
                                cox, coy = ch.get("origin", (0.0, 0.0))
                                cpt = fitz.Point(float(cox), float(coy)) * page.derotation_matrix
                                char_origins.append((float(cpt.x + cb.x0), str(ch.get("c", ""))))
                                # bbox từng ký tự (PDF space) để clip redact chính xác
                                cbx0, cby0, cbx1, cby1 = [float(v) for v in ch.get("bbox", (0, 0, 0, 0))]
                                cp0 = fitz.Point(cbx0, cby0) * page.derotation_matrix
                                cp1 = fitz.Point(cbx1, cby1) * page.derotation_matrix
                                char_boxes.append((
                                    float(min(cp0.x, cp1.x) + cb.x0),
                                    float(max(cp0.x, cp1.x) + cb.x0),
                                    str(ch.get("c", "")),
                                ))
                            best = {
                                "box": span_box,
                                "baseline": (float(pdf_ox), float(pdf_oy)),
                                "char_origins": char_origins,
                                "char_boxes": char_boxes,
                                "font_size": float(span.get("size", 12) or 12),
                                "font_family": font_name,
                                "font_color": (
                                    ((color_int >> 16) & 0xFF) / 255.0,
                                    ((color_int >> 8) & 0xFF) / 255.0,
                                    (color_int & 0xFF) / 255.0,
                                ),
                                # PyMuPDF span flags: italic=2, serifed=4, bold=16 (chuẩn hơn đoán tên)
                                "bold": bool(span_flags & 16) or ("bold" in font_name.lower()),
                                "italic": bool(span_flags & 2)
                                          or ("italic" in font_name.lower())
                                          or ("oblique" in font_name.lower()),
                                # Cờ serif từ chính PDF — fallback phân họ cho font lạ
                                "serifed": bool(span_flags & 4),
                            }
                            best_score = score
                            best_overlap = overlap
            if best is not None and best_overlap <= 0.0:
                return None
            return best
        finally:
            doc.close()

    def on_click(pageNum, left, bottom, right, top, old_text, styles_json, use_span_box=True):
        _stop_existing_text_click_mode()
        window.status.showMessage("", 0)

        styles = {}
        try:
            styles = json.loads(styles_json)
        except Exception:
            pass

        font_size = _parse_font_size(styles)
        color = _parse_color(styles)
        is_bold = _parse_bold(styles)
        is_italic = _parse_italic(styles)
        is_underline = _parse_underline(styles)
        font_family = str(styles.get("fontFamily", "sans-serif"))

        new_text, ok = QInputDialog.getText(
            window,
            "Sửa text",
            f"Text gốc: {old_text}\nNhập text thay thế (để trống để xóa):",
            text=old_text
        )

        if not ok:
            return

        state = _ensure_edit_state(window)
        if not state:
            return

        base_snapshot = state.get("base_snapshot")
        if not base_snapshot or not os.path.exists(base_snapshot):
            return

        # Đọc span theo TRẠNG THÁI HIỆN TẠI (working_file = base + mọi lần sửa trước),
        # KHÔNG đọc bản gốc. Nếu đọc bản gốc, lần sửa thứ 2 trở đi sẽ tính toạ độ
        # theo text CŨ trong khi màn hình đang là text đã sửa lần trước → chồng chéo.
        current_pdf = state.get("working_file")
        if not current_pdf or not os.path.exists(current_pdf):
            current_pdf = base_snapshot

        x0, x1 = float(left), float(right)
        y0, y1 = float(bottom), float(top)
        left, right = min(x0, x1), max(x0, x1)
        bottom, top = min(y0, y1), max(y0, y1)
        if right - left < 0.5 or top - bottom < 0.5:
            return

        def _text_match_x_range(char_boxes, target):
            """Khớp text đã chọn vào chuỗi ký tự của span → (x_left, x_right) đúng
            đoạn đó. Miễn nhiễm với box selection bị lệch (không phụ thuộc toạ độ),
            nên tránh 'xoá cả' dòng khi union box sai. Trả None nếu không khớp."""
            if not char_boxes or not target:
                return None
            span_str = "".join(cb2[2] for cb2 in char_boxes)
            tgt = str(target)
            idx = span_str.find(tgt)
            if idx < 0:
                tgt = tgt.strip()
                idx = span_str.find(tgt) if tgt else -1
            if idx < 0 or not tgt:
                return None
            seg = char_boxes[idx: idx + len(tgt)]
            if not seg:
                return None
            return (min(cb2[0] for cb2 in seg), max(cb2[1] for cb2 in seg))

        insert_box = (left, bottom, right, top)
        redact_box = (left, bottom, right, top)
        span_info = _find_pdf_span(current_pdf, int(pageNum), redact_box, prefer_text=old_text)
        redact_padding = 2.0 if use_span_box else 0.0
        if span_info:
            span_left, span_bottom, span_right, span_top = span_info["box"]
            if use_span_box:
                # Direct-click mode may receive a PDF.js text-layer span that covers
                # a whole line. Keep the clicked fragment's horizontal bounds and
                # only borrow the real PDF span height, otherwise a single edit can
                # erase an entire text run.
                clipped_left = max(left, span_left)
                clipped_right = min(right, span_right)
                if clipped_right - clipped_left < 0.5:
                    clipped_left, clipped_right = left, right
                bottom, top = span_bottom, span_top
                redact_box = (clipped_left - 0.75, bottom, clipped_right + 1.25, top)
                insert_box = (clipped_left, bottom, clipped_right, top)
            else:
                tight_bottom = max(bottom, span_bottom)
                tight_top = min(top, span_top)
                if tight_top - tight_bottom >= 0.5:
                    # Dùng đúng chiều cao span để xoá sạch text cũ, không đụng dòng khác
                    bottom, top = span_bottom, span_top
                    # Ưu tiên khớp theo TEXT đã chọn (miễn nhiễm box lệch do reload)
                    # → redact đúng đoạn text, không bao giờ "xoá cả" dòng.
                    char_boxes = span_info.get("char_boxes") or []
                    tm = _text_match_x_range(char_boxes, old_text)
                    if tm:
                        r_left = max(span_left, tm[0])
                        r_right = min(span_right, tm[1])
                    else:
                        # Fallback: clip theo ký tự nằm trong union box, chặn trong span
                        sel_chars = [cb2 for cb2 in char_boxes if cb2[1] > left - 1.0 and cb2[0] < right + 1.0]
                        if sel_chars:
                            r_left = max(span_left, min(cb2[0] for cb2 in sel_chars))
                            r_right = min(span_right, max(cb2[1] for cb2 in sel_chars))
                        else:
                            r_left = max(left, span_left)
                            r_right = min(right, span_right)
                    redact_box = (r_left - 0.75, bottom, r_right + 1.0, top)
                    # Canh điểm chèn theo redact thật → baseline trùng vị trí text cũ
                    insert_box = (r_left, bottom, r_right, top)
                redact_padding = 0.0
            font_size = span_info["font_size"]
            color = span_info["font_color"]
            is_bold = span_info["bold"]
            is_italic = span_info.get("italic", is_italic)
            # Ưu tiên font GỐC trích từ PyMuPDF; chỉ fallback sang hint JS
            # (serif/sans-serif) khi PyMuPDF không cho tên font. KHÔNG nối chuỗi:
            # "sans-serif <tên>" làm _macos_font_path dính nhầm hint "serif" và
            # làm hỏng font-family trong CSS preview → mất font gốc.
            font_family = span_info["font_family"] or font_family

        # Do not strip(), so leading/trailing spaces selected by the user are preserved.
        # This keeps the horizontal alignment perfectly intact!
        text_value = str(new_text)

        if text_value:
            insert_left, insert_bottom, insert_right, insert_top = insert_box
            text_box = _expanded_text_box(insert_left, insert_bottom, insert_right, insert_top, text_value, font_size, base_snapshot, int(pageNum))
            op = {
                "id": state["next_id"],
                "type": "text",
                "page_number": pageNum,
                "box": text_box,
                "redact_box": redact_box,
                "redact_padding": redact_padding,
                "text": text_value,
                "font_size": font_size,
                "font_color": color,
                "font_family": font_family,
                "bold": is_bold,
                "italic": is_italic,
                "underline": is_underline,
                # Cờ serif của font gốc (từ PDF) — để font lạ vẫn chọn đúng họ chữ
                "font_serif": span_info.get("serifed") if span_info else None,
                "rotation": 0,
                "is_existing_edit": True,
            }
            if span_info:
                baseline_x = insert_box[0]
                span_left = span_info["box"][0]
                # Canh chính xác điểm đặt bút theo char-level của PyMuPDF: box từ
                # text-layer JS (nhất là chữ nghiêng) gồm cả phần overhang nên lệch
                # so với pen origin thật. Snap baseline_x về origin của glyph gần
                # mép trái vùng thay nhất → text mới trùng đúng vị trí text gốc.
                char_origins = span_info.get("char_origins") or []
                if char_origins:
                    nearest_ox = min(char_origins, key=lambda c: abs(c[0] - baseline_x))[0]
                    if abs(nearest_ox - baseline_x) < 8.0:
                        baseline_x = float(nearest_ox)
                elif abs(baseline_x - span_left) < 3.0:
                    baseline_x = float(span_info["baseline"][0])
                op["baseline"] = (baseline_x, float(span_info["baseline"][1]))
                op["single_line"] = True
        else:
            op = {
                "id": state["next_id"],
                "type": "redact",
                "page_number": pageNum,
                "box": redact_box,
                "fill_color": (1.0, 1.0, 1.0),
                "redact_padding": redact_padding,
            }

        state["next_id"] += 1
        state["ops"].append(op)

        # Dựng working_file + vẽ overlay (hộp trắng che chữ cũ + chữ mới đúng cỡ) —
        # KHÔNG reload_document, tránh hẳn nhấp nháy + nhảy trang.
        working_file = _render_edit_state(window, state, "Đã sửa text" if text_value else "Đã xóa text", focus_page=int(pageNum))
        if not working_file:
            return

    def _get_live_selection_payload_sync(timeout_ms: int = 500):
        try:
            getter = getattr(window, "_get_webview", None)
            web_view = getter() if callable(getter) else None
        except Exception:
            web_view = None
        if web_view is None:
            return {}

        holder = {"payload": None}
        loop = QEventLoop(window)

        def _done(payload):
            holder["payload"] = payload
            if loop.isRunning():
                loop.quit()

        js = """(function() {
            function hasRects(payload) {
                return payload && payload.rects && payload.rects.length > 0;
            }
            // Text đang bôi đen THỰC TẾ ngay lúc này — dùng làm chuẩn để không
            // lấy nhầm cache cũ (vd đang chọn "Lắp 3T" nhưng cache còn "BÁO").
            var sel = window.getSelection ? window.getSelection() : null;
            var liveText = sel ? String(sel.toString() || '').trim() : '';

            var live = null;
            try {
                if (typeof window.__3tReadSelectionPayload === 'function') {
                    live = window.__3tReadSelectionPayload(true);
                }
            } catch (_err) {}
            // Ưu tiên payload tươi nếu có rects VÀ khớp text đang chọn.
            if (hasRects(live) && (!liveText || String(live.text || '').trim() === liveText)) {
                return live;
            }
            // Cache chỉ được dùng nếu text khớp đúng selection hiện tại.
            try {
                var cached = window.__3tLastSelectionPayload;
                if (hasRects(cached) && liveText &&
                    String(cached.text || '').trim() === liveText &&
                    Date.now() - (cached.timestamp || 0) < 10000) {
                    return cached;
                }
            } catch (_err2) {}
            // Không có rects khớp → trả text hiện tại để Python tự tìm vị trí theo text.
            if (live && (live.text || '')) return { text: live.text, rects: live.rects || [], styles: live.styles };
            return { text: liveText, rects: [] };
        })()"""
        try:
            web_view.page().runJavaScript(js, _done)
            QTimer.singleShot(timeout_ms, lambda: loop.quit() if loop.isRunning() else None)
            loop.exec()
        except Exception:
            return {}
        return holder.get("payload") or {}

    def _current_pdf_for_read():
        st = window._state_or_global() if hasattr(window, "_state_or_global") else None
        pdf = None
        if isinstance(st, dict):
            pdf = st.get("working_file") or st.get("base_snapshot")
        if not pdf or not os.path.exists(pdf):
            pdf = getattr(window, "current_path", None)
        return pdf if (pdf and os.path.exists(pdf)) else None

    def _locate_text_rect(pdf_path, page_num, text, near):
        """Tìm VỊ TRÍ CHÍNH XÁC của đoạn text đã chọn bằng PyMuPDF search_for.
        Text lấy từ trình duyệt (đáng tin), còn hộp chọn của trình duyệt hay lệch
        → dùng search_for để định vị đúng, hộp chọn chỉ để chọn đúng lần xuất hiện
        (khi text xuất hiện nhiều nơi). Trả (left,bottom,right,top) hệ PDF, hoặc None."""
        try:
            import fitz
            t = (text or "").strip()
            if not t or not pdf_path or not os.path.exists(pdf_path):
                return None
            doc = fitz.open(pdf_path)
            try:
                if page_num < 1 or page_num > doc.page_count:
                    return None
                page = doc[page_num - 1]
                ph = float(page.rect.height)
                rects = page.search_for(t)
                if not rects:
                    return None
                cands = [(float(r.x0), float(ph - r.y1), float(r.x1), float(ph - r.y0)) for r in rects]
                if near is not None:
                    nx, ny = near
                    cands.sort(key=lambda b: ((b[0] + b[2]) / 2 - nx) ** 2 + ((b[1] + b[3]) / 2 - ny) ** 2)
                return cands[0]
            finally:
                doc.close()
        except Exception:
            return None

    def edit_from_selection():
        from app.actions.annotate import (
            _fallback_selection_payload_from_text,
            _payload_has_selection_rects,
            _qt_selected_text,
            _selection_page_rects,
        )

        payload = _get_live_selection_payload_sync(timeout_ms=500)
        if not _payload_has_selection_rects(payload):
            qt_text = _qt_selected_text(window)
            if qt_text:
                fallback = _fallback_selection_payload_from_text(window, qt_text)
                if _payload_has_selection_rects(fallback):
                    payload = fallback
        selected_text, rects_by_page = _selection_page_rects(payload, merge_lines=False)
        if not rects_by_page:
            return False

        page_num = sorted(rects_by_page.keys())[0]
        page_rects = rects_by_page.get(page_num) or []
        if not page_rects:
            return False

        left = min(float(rect[0]) for rect in page_rects)
        bottom = min(float(rect[1]) for rect in page_rects)
        right = max(float(rect[2]) for rect in page_rects)
        top = max(float(rect[3]) for rect in page_rects)

        # Định vị CHÍNH XÁC theo text đã chọn (browser truth). Hộp chọn từ trình
        # duyệt chỉ để chọn đúng lần xuất hiện; search_for cho vị trí thật.
        exact = _locate_text_rect(_current_pdf_for_read(), page_num,
                                  selected_text, ((left + right) / 2, (bottom + top) / 2))
        if exact:
            left, bottom, right, top = exact

        # Truyền style thật của span neo (thu ở JS) để chế độ bôi đen lấy đúng
        # cỡ/màu/đậm/nghiêng/gạch chân — không rơi về mặc định như khi styles rỗng.
        sel_styles = payload.get("styles") if isinstance(payload, dict) else None
        try:
            styles_json = json.dumps(sel_styles) if sel_styles else "{}"
        except Exception:
            styles_json = "{}"
        on_click(page_num, left, bottom, right, top, selected_text or "", styles_json, use_span_box=False)
        return True

    if edit_from_selection():
        return

    web_view = _existing_text_web_view()
    if web_view is None:
        show_warning(window, "Không mở được trình xem", "Không tìm thấy PDF viewer để chọn chữ gốc.")
        return

    from app.webchannel import register_webchannel_object
    bridge = ExistingTextBridge(window)
    window._existing_text_bridge = bridge
    register_webchannel_object(web_view, window, "editExistingTextBridge", bridge)
    web_view.page().runJavaScript("window.__3tExistingTextMode = true;")
    window.status.showMessage("Click vào đoạn text có sẵn trên trang để sửa... (Esc để hủy)", 0)
