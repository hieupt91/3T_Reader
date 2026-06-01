import os
import re
import uuid
import json
from datetime import datetime, timezone

import pikepdf

from packages.qt_compat.QtCore import QObject, QTimer, pyqtSlot
from packages.qt_compat.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)
from app.actions._guard import require_document
from app.actions._pdf_save import (
    make_staged_pdf_path,
    remove_path_quietly,
    replace_document_with_staged,
    replace_file_with_retry,
)
from app.dialogs import show_warning, show_info
from app.webchannel import register_webchannel_object


NOTE_ICON_SIZE_PT = 18.0
NOTE_MARGIN_PT = 12.0
NOTE_STACK_GAP_PT = 6.0
NOTE_POSITION_DEFAULT = "default"
NOTE_POSITION_TOP_LEFT = "top_left"
NOTE_POSITION_TOP_RIGHT = "top_right"
NOTE_POSITION_BOTTOM_LEFT = "bottom_left"
NOTE_POSITION_BOTTOM_RIGHT = "bottom_right"
NOTE_POSITION_CUSTOM = "custom"


def _get_current_page(window) -> int:
    try:
        return max(1, window.viewer.get_current_page())
    except Exception:
        return 1


def _save_pikepdf_reload(window, pdf: pikepdf.Pdf, *, keep_page: bool = True):
    """Save pikepdf doc atomically to the active document and reload viewer."""
    target_path = window.current_path
    if not target_path:
        raise ValueError("Không tìm thấy đường dẫn tài liệu hiện tại.")

    staged_path = make_staged_pdf_path(target_path)
    pdf.save(staged_path)
    try:
        pdf.close()
    except Exception:
        pass
    replace_document_with_staged(window, staged_path, target_path=target_path, keep_page=keep_page)


class _AnnotationOpQueue(QObject):
    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._pending: list[tuple[str, object]] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.flush)

    def enqueue(self, target_path: str, op, *, delay_ms: int = 350) -> None:
        self._pending.append((os.path.abspath(target_path), op))
        self._timer.start(max(0, int(delay_ms)))

    def flush(self) -> None:
        if not self._pending:
            return
        target_path = self._pending[0][0]
        same_target: list[tuple[str, object]] = []
        rest: list[tuple[str, object]] = []
        for item in self._pending:
            if item[0] == target_path:
                same_target.append(item)
            else:
                rest.append(item)
        self._pending = rest

        staged_path = ""
        try:
            with pikepdf.open(target_path) as pdf:
                for _path, op in same_target:
                    op(pdf)
                staged_path = make_staged_pdf_path(target_path)
                pdf.save(staged_path)
            replace_file_with_retry(staged_path, target_path, attempts=3)
            if hasattr(self._window, "status"):
                self._window.status.showMessage("Da tu dong luu chu thich.", 1800)
        except Exception as exc:
            remove_path_quietly(staged_path)
            self._pending = same_target + self._pending
            if hasattr(self._window, "status"):
                self._window.status.showMessage(f"Chua luu duoc chu thich, se thu lai: {exc}", 3500)
            self._timer.start(1200)
            return

        if self._pending:
            self._timer.start(50)


def _annotation_queue(window) -> _AnnotationOpQueue:
    queue = getattr(window, "_annotation_op_queue", None)
    if queue is None:
        queue = _AnnotationOpQueue(window)
        window._annotation_op_queue = queue
    return queue


def _queue_annotation_op(window, target_path: str, op, *, delay_ms: int = 350) -> None:
    _annotation_queue(window).enqueue(target_path, op, delay_ms=delay_ms)


def _flush_annotation_queue(window) -> None:
    queue = getattr(window, "_annotation_op_queue", None)
    if queue is None:
        return
    queue.flush()


def _save_pikepdf_in_place(pdf: pikepdf.Pdf, target_path: str) -> None:
    staged_path = ""
    try:
        staged_path = make_staged_pdf_path(target_path)
        pdf.save(staged_path)
        replace_file_with_retry(staged_path, target_path, attempts=8)
    except Exception:
        remove_path_quietly(staged_path)
        raise


def _pdf_date_now() -> pikepdf.String:
    now = datetime.now(timezone.utc)
    return pikepdf.String(now.strftime("D:%Y%m%d%H%M%SZ"))


def _name_value(value) -> str:
    try:
        return str(value)
    except Exception:
        return ""


def _annotation_subtype(annot) -> str:
    try:
        return _name_value(annot.get("/Subtype"))
    except Exception:
        return ""


def _annotation_id(annot) -> str:
    try:
        value = annot.get("/NM")
    except Exception:
        value = None
    return str(value or "")


def load_annotations(pdf_path: str, page_no: int | None = None) -> list[dict]:
    """Load supported PDF annotations. Currently exposes Text notes for the comment panel path."""
    items: list[dict] = []
    with pikepdf.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            if page_no is not None and idx != int(page_no):
                continue
            annots = page.get("/Annots", [])
            for annot_idx, annot in enumerate(annots):
                if _annotation_subtype(annot) != "/Text":
                    continue
                rect = [float(v) for v in annot.get("/Rect", [])]
                annot_id = _annotation_id(annot)
                if not annot_id:
                    annot_id = _synthetic_note_id(idx, annot_idx, rect, str(annot.get("/Contents", "")))
                items.append({
                    "id": annot_id,
                    "page_number": idx,
                    "type": "Text",
                    "content": str(annot.get("/Contents", "")),
                    "author": str(annot.get("/T", "")),
                    "modified": str(annot.get("/M", "")),
                    "rect": tuple(rect) if len(rect) == 4 else (),
                })
    return items


def _synthetic_note_id(page_number: int, annot_index: int, rect: list[float], content: str) -> str:
    rect_key = ",".join(f"{float(v):.2f}" for v in (rect or [])[:4])
    raw = f"{int(page_number)}|{int(annot_index)}|{rect_key}|{content[:80]}"
    return "3t-note-synth-" + uuid.uuid5(uuid.NAMESPACE_URL, raw).hex


def _page_box(page) -> tuple[float, float, float, float]:
    box = page.mediabox
    return float(box[0]), float(box[1]), float(box[2]), float(box[3])


def _default_note_rect(page, existing_note_count: int) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = _page_box(page)
    size = NOTE_ICON_SIZE_PT
    offset = max(0, existing_note_count) * (size + NOTE_STACK_GAP_PT)
    left = x1 - NOTE_MARGIN_PT - size
    top = y1 - NOTE_MARGIN_PT - offset
    if top - size < y0 + NOTE_MARGIN_PT:
        top = y1 - NOTE_MARGIN_PT
        left = max(x0 + NOTE_MARGIN_PT, left - size - NOTE_STACK_GAP_PT)
    bottom = max(y0 + NOTE_MARGIN_PT, top - size)
    top = bottom + size
    return left, bottom, left + size, top


def _clamp_float(value: float, low: float, high: float) -> float:
    if high < low:
        return low
    return max(low, min(float(value), high))


def _stack_offset(existing_note_count: int) -> float:
    return max(0, existing_note_count) * (NOTE_ICON_SIZE_PT + NOTE_STACK_GAP_PT)


def _note_rect_for_position(
    page,
    position: str,
    existing_note_count: int = 0,
    *,
    x_percent: float = 90.0,
    y_percent: float = 10.0,
) -> tuple[float, float, float, float]:
    """Return a PDF /Rect for a sticky note icon.

    Presets use PDF coordinates (origin at bottom-left). Custom coordinates are
    easier for users: X is percent from left, Y is percent from top.
    """
    if position in ("", NOTE_POSITION_DEFAULT, NOTE_POSITION_TOP_RIGHT):
        return _default_note_rect(page, existing_note_count)

    x0, y0, x1, y1 = _page_box(page)
    size = NOTE_ICON_SIZE_PT
    margin = NOTE_MARGIN_PT
    page_w = max(size, x1 - x0)
    page_h = max(size, y1 - y0)
    offset = _stack_offset(existing_note_count)

    if position == NOTE_POSITION_TOP_LEFT:
        left = x0 + margin
        top = y1 - margin - offset
    elif position == NOTE_POSITION_BOTTOM_LEFT:
        left = x0 + margin
        top = y0 + margin + size + offset
    elif position == NOTE_POSITION_BOTTOM_RIGHT:
        left = x1 - margin - size
        top = y0 + margin + size + offset
    elif position == NOTE_POSITION_CUSTOM:
        x_ratio = _clamp_float(x_percent, 0.0, 100.0) / 100.0
        y_ratio = _clamp_float(y_percent, 0.0, 100.0) / 100.0
        left = x0 + (page_w - size) * x_ratio
        top = y1 - (page_h - size) * y_ratio
    else:
        return _default_note_rect(page, existing_note_count)

    left = _clamp_float(left, x0 + margin, x1 - margin - size)
    bottom = _clamp_float(top - size, y0 + margin, y1 - margin - size)
    return left, bottom, left + size, bottom + size


def _count_text_notes(page) -> int:
    try:
        annots = page.get("/Annots", [])
    except Exception:
        return 0
    return sum(1 for annot in annots if _annotation_subtype(annot) == "/Text")


def add_annotation(
    pdf: pikepdf.Pdf,
    *,
    page_idx: int,
    subtype: str,
    rect: tuple[float, float, float, float],
    content: str,
    author: str = "3T Reader",
    annot_id: str | None = None,
) -> str:
    """Add one supported annotation and return its stable PDF annotation id."""
    if subtype != "Text":
        raise ValueError(f"Unsupported annotation subtype: {subtype}")

    annot_id = annot_id or f"3t-note-{uuid.uuid4().hex}"
    page = pdf.pages[page_idx]
    left, bottom, right, top = [float(v) for v in rect]
    note = pikepdf.Dictionary(
        Type=pikepdf.Name.Annot,
        Subtype=pikepdf.Name("/Text"),
        Rect=pikepdf.Array([left, bottom, right, top]),
        Contents=pikepdf.String(content),
        T=pikepdf.String(author),
        M=_pdf_date_now(),
        NM=pikepdf.String(annot_id),
        Name=pikepdf.Name("/Note"),
        C=pikepdf.Array([1.0, 0.82, 0.22]),
        F=4,
        Open=False,
    )
    indirect = pdf.make_indirect(note)
    if "/Annots" not in page:
        page["/Annots"] = pikepdf.Array([indirect])
    else:
        page["/Annots"].append(indirect)
    return annot_id


def _clamp_note_rect_to_page(page, rect: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = _page_box(page)
    size = NOTE_ICON_SIZE_PT
    left, bottom, right, top = [float(v) for v in rect]
    center_x = (left + right) / 2.0
    center_y = (bottom + top) / 2.0
    center_x = _clamp_float(center_x, x0 + NOTE_MARGIN_PT + size / 2.0, x1 - NOTE_MARGIN_PT - size / 2.0)
    center_y = _clamp_float(center_y, y0 + NOTE_MARGIN_PT + size / 2.0, y1 - NOTE_MARGIN_PT - size / 2.0)
    return (
        center_x - size / 2.0,
        center_y - size / 2.0,
        center_x + size / 2.0,
        center_y + size / 2.0,
    )


_ARM_NOTE_TOOLS_JS = r"""(function(notes) {
    if (typeof window.__3tNoteToolsCleanup === 'function') {
        try { window.__3tNoteToolsCleanup(); } catch (_err) {}
    }

    function ensureBridge(callback) {
        if (typeof QWebChannel === 'undefined') {
            var script = document.createElement('script');
            script.src = 'qrc:///qtwebchannel/qwebchannel.js';
            script.onload = function() { ensureBridge(callback); };
            document.head.appendChild(script);
            return;
        }
        if (!(window.qt && qt.webChannelTransport)) {
            setTimeout(function() { ensureBridge(callback); }, 80);
            return;
        }
        new QWebChannel(qt.webChannelTransport, function(channel) {
            callback(channel.objects.noteToolsBridge || null);
        });
    }

    function closeMenu() {
        var old = document.getElementById('__3tNoteMenu');
        if (old && old.parentNode) old.parentNode.removeChild(old);
    }

    function showMenu(note, x, y, bridge) {
        closeMenu();
        var menu = document.createElement('div');
        menu.id = '__3tNoteMenu';
        menu.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;z-index:10050;min-width:132px;background:#fff;color:#111827;border:1px solid rgba(15,23,42,.18);box-shadow:0 10px 28px rgba(15,23,42,.22);border-radius:6px;padding:4px;font:13px sans-serif';
        function item(label, danger, fn) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = label;
            btn.style.cssText = 'display:block;width:100%;border:0;background:transparent;color:' + (danger ? '#dc2626' : '#111827') + ';text-align:left;padding:7px 9px;border-radius:4px;cursor:pointer';
            btn.addEventListener('mouseenter', function() { btn.style.background = '#f3f4f6'; });
            btn.addEventListener('mouseleave', function() { btn.style.background = 'transparent'; });
            btn.addEventListener('click', function(event) {
                event.preventDefault();
                event.stopPropagation();
                closeMenu();
                fn();
            }, true);
            menu.appendChild(btn);
        }
        item('Sửa ghi chú', false, function() { bridge.editNote(note.id, note.page_number); });
        item('Xóa ghi chú', true, function() { bridge.deleteNote(note.id, note.page_number); });
        document.body.appendChild(menu);
        setTimeout(function() {
            document.addEventListener('mousedown', closeMenu, {capture: true, once: true});
            document.addEventListener('keydown', closeMenu, {capture: true, once: true});
        }, 0);
    }

    function pageViewFor(viewer, pageNumber) {
        return viewer.getPageView ? viewer.getPageView(pageNumber - 1) : (viewer._pages && viewer._pages[pageNumber - 1]);
    }

    function bindNote(node, pageView, pageEl, note, bridge, cleanupFns) {
        var originalTransform = node.style.transform || '';
        var originalZIndex = node.style.zIndex || '';
        var originalOutline = node.style.outline || '';
        var originalOutlineOffset = node.style.outlineOffset || '';
        var pressed = false;
        var dragging = false;
        var startClientX = 0;
        var startClientY = 0;
        var pageRect = null;
        var dragImage = node.querySelector('img') || node;

        function blockNextClick(event) {
            event.preventDefault();
            event.stopPropagation();
            document.removeEventListener('click', blockNextClick, true);
        }
        function onMouseDown(event) {
            if (event.button !== 0) return;
            pressed = true;
            dragging = false;
            startClientX = event.clientX;
            startClientY = event.clientY;
            pageRect = pageEl.getBoundingClientRect();
        }
        function onMouseMove(event) {
            if (!pressed) return;
            var dx = event.clientX - startClientX;
            var dy = event.clientY - startClientY;
            if (!dragging && Math.hypot(dx, dy) < 4) return;
            dragging = true;
            event.preventDefault();
            event.stopPropagation();
            node.style.cursor = 'grabbing';
            node.style.zIndex = '10002';
            node.style.outline = '2px solid rgba(11,132,243,.6)';
            node.style.outlineOffset = '2px';
            node.style.transform = originalTransform + ' translate(' + dx + 'px,' + dy + 'px)';
            if (dragImage) dragImage.style.pointerEvents = 'none';
        }
        function onMouseUp(event) {
            if (!pressed) return;
            pressed = false;
            if (!dragging) return;
            event.preventDefault();
            event.stopPropagation();
            dragging = false;
            var rect = node.getBoundingClientRect();
            var cx = rect.left - pageRect.left + rect.width / 2;
            var cy = rect.top - pageRect.top + rect.height / 2;
            var pdfPoint = pageView.viewport.convertToPdfPoint(cx, cy);
            document.addEventListener('click', blockNextClick, true);
            bridge.moveNote(note.id, note.page_number, pdfPoint[0] - 9.0, pdfPoint[1] - 9.0, pdfPoint[0] + 9.0, pdfPoint[1] + 9.0);
        }
        function onDoubleClick(event) {
            event.preventDefault();
            event.stopPropagation();
            bridge.editNote(note.id, note.page_number);
        }
        function onContextMenu(event) {
            event.preventDefault();
            event.stopPropagation();
            showMenu(note, event.clientX, event.clientY, bridge);
        }

        node.dataset.threeTNoteBound = '1';
        node.dataset.threeTNoteId = note.id;
        node.title = 'Kéo để di chuyển. Đúp chuột để sửa. Chuột phải để xóa/sửa.';
        node.style.cursor = 'move';
        node.addEventListener('mousedown', onMouseDown, true);
        node.addEventListener('dblclick', onDoubleClick, true);
        node.addEventListener('contextmenu', onContextMenu, true);
        document.addEventListener('mousemove', onMouseMove, true);
        document.addEventListener('mouseup', onMouseUp, true);
        cleanupFns.push(function() {
            node.style.transform = originalTransform;
            node.style.zIndex = originalZIndex;
            node.style.cursor = '';
            node.style.outline = originalOutline;
            node.style.outlineOffset = originalOutlineOffset;
            node.removeEventListener('mousedown', onMouseDown, true);
            node.removeEventListener('dblclick', onDoubleClick, true);
            node.removeEventListener('contextmenu', onContextMenu, true);
            document.removeEventListener('mousemove', onMouseMove, true);
            document.removeEventListener('mouseup', onMouseUp, true);
            if (dragImage) dragImage.style.pointerEvents = '';
        });
    }

    function bindAll(bridge) {
        if (!bridge || !Array.isArray(notes) || !notes.length) return;
        var app = window.PDFViewerApplication;
        var viewer = app && app.pdfViewer;
        if (!viewer) return;
        var cleanupFns = [];
        var pending = notes.slice();
        function attempt() {
            var retry = [];
            for (var n = 0; n < pending.length; n += 1) {
                var note = pending[n];
                var pageView = pageViewFor(viewer, note.page_number);
                if (!pageView || !pageView.viewport || !pageView.div) {
                    retry.push(note);
                    continue;
                }
                var pageEl = pageView.div;
                var layer = pageEl.querySelector('.annotationLayer');
                if (!layer) {
                    retry.push(note);
                    continue;
                }
                var targetRect = pageView.viewport.convertToViewportRectangle(note.rect);
                var tx = (targetRect[0] + targetRect[2]) / 2;
                var ty = (targetRect[1] + targetRect[3]) / 2;
                var pageRect = pageEl.getBoundingClientRect();
                var nodes = Array.from(layer.querySelectorAll('.textAnnotation'));
                var target = null;
                var best = Number.POSITIVE_INFINITY;
                for (var i = 0; i < nodes.length; i += 1) {
                    if (nodes[i].dataset && nodes[i].dataset.threeTNoteBound === '1') continue;
                    var r = nodes[i].getBoundingClientRect();
                    var cx = r.left - pageRect.left + r.width / 2;
                    var cy = r.top - pageRect.top + r.height / 2;
                    var dist = Math.hypot(cx - tx, cy - ty);
                    if (dist < best) {
                        best = dist;
                        target = nodes[i];
                    }
                }
                if (target) bindNote(target, pageView, pageEl, note, bridge, cleanupFns);
            }
            pending = retry;
            if (pending.length) setTimeout(attempt, 160);
        }
        attempt();
        window.__3tNoteToolsCleanup = function() {
            closeMenu();
            cleanupFns.forEach(function(fn) { try { fn(); } catch (_err) {} });
        };
    }

    ensureBridge(bindAll);
})(__NOTES_JSON__);"""


_ARM_NOTE_TOOLS_JS = r"""(function(notes) {
    if (typeof window.__3tNoteToolsCleanup === 'function') {
        try { window.__3tNoteToolsCleanup(); } catch (_err) {}
    }

    function ensureBridge(callback) {
        if (typeof QWebChannel === 'undefined') {
            var script = document.createElement('script');
            script.src = 'qrc:///qtwebchannel/qwebchannel.js';
            script.onload = function() { ensureBridge(callback); };
            document.head.appendChild(script);
            return;
        }
        if (!(window.qt && qt.webChannelTransport)) {
            setTimeout(function() { ensureBridge(callback); }, 80);
            return;
        }
        new QWebChannel(qt.webChannelTransport, function(channel) {
            callback(channel.objects.noteToolsBridge || null);
        });
    }

    function ensureStyle() {
        if (document.getElementById('__3tAnnotationOverlayStyle')) return;
        var style = document.createElement('style');
        style.id = '__3tAnnotationOverlayStyle';
        style.textContent = [
            '.annotationLayer .textAnnotation{opacity:0!important;pointer-events:none!important;}',
            '.threeTNoteOverlay{position:absolute;z-index:10001;width:24px;height:24px;border:0;border-radius:4px;background:#facc15;color:#111827;box-shadow:0 2px 7px rgba(15,23,42,.25);cursor:move;font:16px/24px sans-serif;text-align:center;padding:0;}',
            '.threeTNoteOverlay:focus{outline:2px solid #0b84f3;outline-offset:2px;}',
            '.threeTMarkOverlay{position:absolute;z-index:9999;pointer-events:none;border-radius:2px;}'
        ].join('\n');
        document.head.appendChild(style);
    }

    function closeMenu() {
        var old = document.getElementById('__3tNoteMenu');
        if (old && old.parentNode) old.parentNode.removeChild(old);
    }

    function showMenu(note, x, y, bridge) {
        closeMenu();
        var menu = document.createElement('div');
        menu.id = '__3tNoteMenu';
        menu.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;z-index:10050;min-width:132px;background:#fff;color:#111827;border:1px solid rgba(15,23,42,.18);box-shadow:0 10px 28px rgba(15,23,42,.22);border-radius:6px;padding:4px;font:13px sans-serif';
        function item(label, danger, fn) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = label;
            btn.style.cssText = 'display:block;width:100%;border:0;background:transparent;color:' + (danger ? '#dc2626' : '#111827') + ';text-align:left;padding:7px 9px;border-radius:4px;cursor:pointer';
            btn.addEventListener('mouseenter', function() { btn.style.background = '#f3f4f6'; });
            btn.addEventListener('mouseleave', function() { btn.style.background = 'transparent'; });
            btn.addEventListener('click', function(event) {
                event.preventDefault();
                event.stopPropagation();
                closeMenu();
                fn();
            }, true);
            menu.appendChild(btn);
        }
        item('Sua ghi chu', false, function() { bridge.editNote(note.id, note.page_number); });
        item('Xoa ghi chu', true, function() { bridge.deleteNote(note.id, note.page_number); });
        document.body.appendChild(menu);
        setTimeout(function() {
            document.addEventListener('mousedown', closeMenu, {capture: true, once: true});
            document.addEventListener('keydown', closeMenu, {capture: true, once: true});
        }, 0);
    }

    function pageViewFor(viewer, pageNumber) {
        return viewer.getPageView ? viewer.getPageView(pageNumber - 1) : (viewer._pages && viewer._pages[pageNumber - 1]);
    }

    function removeOldOverlays() {
        document.querySelectorAll('.threeTNoteOverlay,.threeTMarkOverlay').forEach(function(el) { el.remove(); });
    }

    function positionForNote(pageView, note) {
        var rect = pageView.viewport.convertToViewportRectangle(note.rect);
        return {
            left: (rect[0] + rect[2]) / 2 - 12,
            top: (rect[1] + rect[3]) / 2 - 12
        };
    }

    function placeNode(node, pageView, note) {
        var pos = positionForNote(pageView, note);
        node.style.left = pos.left + 'px';
        node.style.top = pos.top + 'px';
    }

    function bindNote(node, pageView, pageEl, note, bridge, cleanupFns) {
        var pressed = false;
        var dragging = false;
        var startClientX = 0;
        var startClientY = 0;
        var startLeft = 0;
        var startTop = 0;

        function blockNextClick(event) {
            event.preventDefault();
            event.stopPropagation();
            document.removeEventListener('click', blockNextClick, true);
        }
        function onMouseDown(event) {
            if (event.button !== 0) return;
            pressed = true;
            dragging = false;
            startClientX = event.clientX;
            startClientY = event.clientY;
            startLeft = parseFloat(node.style.left || '0') || 0;
            startTop = parseFloat(node.style.top || '0') || 0;
        }
        function onMouseMove(event) {
            if (!pressed) return;
            var dx = event.clientX - startClientX;
            var dy = event.clientY - startClientY;
            if (!dragging && Math.hypot(dx, dy) < 4) return;
            dragging = true;
            event.preventDefault();
            event.stopPropagation();
            node.style.cursor = 'grabbing';
            node.style.left = Math.max(0, Math.min(startLeft + dx, pageEl.clientWidth - 24)) + 'px';
            node.style.top = Math.max(0, Math.min(startTop + dy, pageEl.clientHeight - 24)) + 'px';
        }
        function onMouseUp(event) {
            if (!pressed) return;
            pressed = false;
            if (!dragging) return;
            event.preventDefault();
            event.stopPropagation();
            dragging = false;
            node.style.cursor = 'move';
            var cx = parseFloat(node.style.left || '0') + 12;
            var cy = parseFloat(node.style.top || '0') + 12;
            var pdfPoint = pageView.viewport.convertToPdfPoint(cx, cy);
            note.rect = [pdfPoint[0] - 9.0, pdfPoint[1] - 9.0, pdfPoint[0] + 9.0, pdfPoint[1] + 9.0];
            document.addEventListener('click', blockNextClick, true);
            bridge.moveNote(note.id, note.page_number, note.rect[0], note.rect[1], note.rect[2], note.rect[3]);
        }
        function onDoubleClick(event) {
            event.preventDefault();
            event.stopPropagation();
            bridge.editNote(note.id, note.page_number);
        }
        function onContextMenu(event) {
            event.preventDefault();
            event.stopPropagation();
            showMenu(note, event.clientX, event.clientY, bridge);
        }

        node.title = 'Keo de di chuyen. Dup chuot de sua. Chuot phai de xoa/sua.';
        node.addEventListener('mousedown', onMouseDown, true);
        node.addEventListener('dblclick', onDoubleClick, true);
        node.addEventListener('contextmenu', onContextMenu, true);
        document.addEventListener('mousemove', onMouseMove, true);
        document.addEventListener('mouseup', onMouseUp, true);
        cleanupFns.push(function() {
            node.removeEventListener('mousedown', onMouseDown, true);
            node.removeEventListener('dblclick', onDoubleClick, true);
            node.removeEventListener('contextmenu', onContextMenu, true);
            document.removeEventListener('mousemove', onMouseMove, true);
            document.removeEventListener('mouseup', onMouseUp, true);
        });
    }

    function renderMarks(viewer, marks) {
        if (!Array.isArray(marks)) return;
        marks.forEach(function(mark) {
            var pageView = pageViewFor(viewer, mark.page_number);
            if (!pageView || !pageView.viewport || !pageView.div) return;
            (mark.rects || []).forEach(function(pdfRect) {
                var rect = pageView.viewport.convertToViewportRectangle(pdfRect);
                var left = Math.min(rect[0], rect[2]);
                var top = Math.min(rect[1], rect[3]);
                var width = Math.abs(rect[2] - rect[0]);
                var height = Math.abs(rect[3] - rect[1]);
                var el = document.createElement('div');
                el.className = 'threeTMarkOverlay';
                el.style.left = left + 'px';
                el.style.width = width + 'px';
                if (mark.style === 'underline') {
                    el.style.top = (top + height - 2) + 'px';
                    el.style.height = '2px';
                    el.style.background = mark.color || 'rgba(37,99,235,.85)';
                } else if (mark.style === 'strikeout') {
                    el.style.top = (top + height * 0.52) + 'px';
                    el.style.height = '2px';
                    el.style.background = mark.color || 'rgba(220,38,38,.85)';
                } else {
                    el.style.top = top + 'px';
                    el.style.height = height + 'px';
                    el.style.background = mark.color || 'rgba(250,204,21,.35)';
                }
                pageView.div.appendChild(el);
            });
        });
    }

    function bindAll(bridge) {
        if (!bridge || !Array.isArray(notes)) return;
        var app = window.PDFViewerApplication;
        var viewer = app && app.pdfViewer;
        if (!viewer) return;
        ensureStyle();
        removeOldOverlays();
        var cleanupFns = [];
        var noteItems = notes.filter(function(item) { return item && item.kind !== 'mark'; });
        var markItems = notes.filter(function(item) { return item && item.kind === 'mark'; });

        window.__3tNotesUpdateNote = function(updated) {
            if (!updated || !updated.id) return;
            var node = document.querySelector('.threeTNoteOverlay[data-three-t-note-id="' + updated.id + '"]');
            if (node && typeof updated.content === 'string') node.dataset.noteContent = updated.content;
        };
        window.__3tNotesDeleteNote = function(noteId) {
            document
                .querySelectorAll('.threeTNoteOverlay[data-three-t-note-id="' + noteId + '"]')
                .forEach(function(node) {
                    if (node && node.parentNode) node.parentNode.removeChild(node);
                });
        };

        noteItems.forEach(function(note) {
            var pageView = pageViewFor(viewer, note.page_number);
            if (!pageView || !pageView.viewport || !pageView.div) return;
            var node = document.createElement('button');
            node.type = 'button';
            node.className = 'threeTNoteOverlay';
            node.textContent = '\uD83D\uDCCE';
            node.dataset.threeTNoteId = note.id;
            node.dataset.noteContent = note.content || '';
            placeNode(node, pageView, note);
            pageView.div.appendChild(node);
            bindNote(node, pageView, pageView.div, note, bridge, cleanupFns);
        });
        renderMarks(viewer, markItems);

        window.__3tNoteToolsCleanup = function() {
            closeMenu();
            cleanupFns.forEach(function(fn) { try { fn(); } catch (_err) {} });
            removeOldOverlays();
        };
    }

    ensureBridge(bindAll);
})(__NOTES_JSON__);"""


class _NoteToolsBridge(QObject):
    def __init__(self, window, pdf_path: str):
        super().__init__(window)
        self._window = window
        self._pdf_path = pdf_path

    def _path_is_current(self) -> bool:
        current_path = getattr(self._window, "current_path", None)
        return bool(current_path and os.path.abspath(current_path) == os.path.abspath(self._pdf_path))

    def _run_js(self, script: str) -> None:
        try:
            getter = getattr(self._window, "_get_webview", None)
            web_view = getter() if callable(getter) else None
            if web_view is not None:
                web_view.page().runJavaScript(script)
        except Exception:
            pass

    @pyqtSlot(str, int, float, float, float, float)
    def moveNote(self, note_id: str, page_number: int, left: float, bottom: float, right: float, top: float):
        if not self._path_is_current():
            return
        try:
            raw_rect = (float(left), float(bottom), float(right), float(top))
            notes = _overlay_notes(self._window)
            note = notes.get(note_id) or _find_note_by_id(self._pdf_path, note_id) or {}
            note.update({
                "id": note_id,
                "page_number": int(page_number),
                "rect": [float(v) for v in raw_rect],
                "content": str(note.get("content") or ""),
            })
            notes[note_id] = note

            def _op(pdf):
                page_no = max(1, min(int(page_number), len(pdf.pages)))
                page = pdf.pages[page_no - 1]
                rect = _clamp_note_rect_to_page(page, raw_rect)
                _update_note_rect_by_id(
                    pdf,
                    page_idx=page_no - 1,
                    note_id=note_id,
                    new_rect=rect,
                )

            _queue_annotation_op(self._window, self._pdf_path, _op, delay_ms=350)
            page_no = int(page_number)
            if hasattr(self._window, "status"):
                self._window.status.showMessage(f"Đã di chuyển ghi chú trên trang {page_no}", 2500)
        except Exception as exc:
            show_warning(self._window, "Lỗi di chuyển ghi chú", str(exc))

    @pyqtSlot(str, int)
    def editNote(self, note_id: str, page_number: int):
        if not self._path_is_current():
            return
        try:
            note = _overlay_notes(self._window).get(note_id) or _find_note_by_id(self._pdf_path, note_id)
            if not note:
                show_warning(self._window, "Sửa ghi chú", "Không tìm thấy ghi chú này trong tài liệu.")
                return
            text, ok = QInputDialog.getMultiLineText(
                self._window,
                "Sửa ghi chú",
                "Nội dung ghi chú:",
                str(note.get("content") or ""),
            )
            text = (text or "").strip()
            if not ok:
                return
            if not text:
                show_warning(self._window, "Sửa ghi chú", "Nội dung ghi chú không được để trống.")
                return
            note = dict(note)
            note["content"] = text
            _overlay_notes(self._window)[note_id] = note

            def _op(pdf):
                _update_note_content_by_id(pdf, note_id=note_id, content=text)

            _queue_annotation_op(self._window, self._pdf_path, _op, delay_ms=350)
            payload = json.dumps({"id": note_id, "content": text}, ensure_ascii=False)
            self._run_js(f"if(window.__3tNotesUpdateNote) window.__3tNotesUpdateNote({payload});")
            if hasattr(self._window, "status"):
                self._window.status.showMessage(f"Da sua ghi chu trang {note.get('page_number') or page_number}.", 1800)
            return
            with pikepdf.open(self._pdf_path) as pdf:
                if not _update_note_content_by_id(pdf, note_id=note_id, content=text):
                    show_warning(self._window, "Sửa ghi chú", "Không tìm thấy ghi chú này trong tài liệu.")
                    return
                _save_pikepdf_reload(self._window, pdf)
            if hasattr(self._window, "status"):
                self._window.status.showMessage(f"Đã sửa ghi chú trang {note.get('page_number') or page_number}", 2500)
        except Exception as exc:
            show_warning(self._window, "Lỗi sửa ghi chú", str(exc))

    @pyqtSlot(str, int)
    def deleteNote(self, note_id: str, page_number: int):
        if not self._path_is_current():
            return
        try:
            _flush_annotation_queue(self._window)
            note = _overlay_notes(self._window).get(note_id) or _find_note_by_id(self._pdf_path, note_id)
            if not note:
                show_warning(self._window, "Xóa ghi chú", "Không tìm thấy ghi chú này trong tài liệu.")
                return
            preview = _shorten_note_content(str(note.get("content") or ""), 120)
            reply = QMessageBox.question(
                self._window,
                "Xóa ghi chú",
                f"Xóa ghi chú này?\n\n{preview}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            with pikepdf.open(self._pdf_path) as pdf:
                if not _delete_note_by_id(pdf, note_id=note_id):
                    show_warning(self._window, "Xóa ghi chú", "Không tìm thấy ghi chú này trong tài liệu.")
                    return
                _save_pikepdf_in_place(pdf, self._pdf_path)

            tombstone = dict(note)
            tombstone["_deleted"] = True
            _overlay_notes(self._window)[note_id] = tombstone
            self._run_js(
                "if(window.__3tNotesDeleteNote) window.__3tNotesDeleteNote(%s);"
                % json.dumps(note_id, ensure_ascii=False)
            )
            if hasattr(self._window, "status"):
                self._window.status.showMessage(f"Da xoa ghi chu trang {note.get('page_number') or page_number}.", 1800)
            return
        except Exception as exc:
            show_warning(self._window, "Lỗi xóa ghi chú", str(exc))


def enable_note_tools(window):
    """Arm all rendered PDF.js sticky note icons for drag/edit/delete."""
    path = getattr(window, "current_path", None)
    if not path:
        return
    try:
        getter = getattr(window, "_get_webview", None)
        web_view = getter() if callable(getter) else None
    except Exception:
        web_view = None
    if web_view is None:
        return

    try:
        notes = _notes_for_js(path)
    except Exception:
        notes = []
    notes = _merge_overlay_notes(window, notes)
    notes.extend(_overlay_marks_for_js(window, path))
    if not notes:
        return

    bridge = _NoteToolsBridge(window, path)
    channel = register_webchannel_object(web_view, window, "noteToolsBridge", bridge)
    window._note_tools_bridge = bridge
    window._note_tools_channel = channel

    script = _ARM_NOTE_TOOLS_JS.replace("__NOTES_JSON__", json.dumps(notes, ensure_ascii=False))
    QTimer.singleShot(80, lambda: web_view.page().runJavaScript(script))


def _overlay_notes(window) -> dict:
    notes = getattr(window, "_annotation_overlay_notes", None)
    if not isinstance(notes, dict):
        notes = {}
        window._annotation_overlay_notes = notes
    return notes


def _overlay_marks(window) -> list:
    marks = getattr(window, "_annotation_overlay_marks", None)
    if not isinstance(marks, list):
        marks = []
        window._annotation_overlay_marks = marks
    return marks


def _merge_overlay_notes(window, notes: list[dict]) -> list[dict]:
    merged = {str(item.get("id")): dict(item) for item in notes if item.get("id")}
    for note_id, item in _overlay_notes(window).items():
        if item.get("_deleted"):
            merged.pop(str(note_id), None)
        else:
            merged[str(note_id)] = dict(item)
    return list(merged.values())


def _overlay_marks_for_js(window, path: str) -> list[dict]:
    current = os.path.abspath(path)
    return [
        dict(item)
        for item in _overlay_marks(window)
        if os.path.abspath(str(item.get("path") or "")) == current
    ]


def _refresh_annotation_overlays(window) -> None:
    try:
        enable_note_tools(window)
    except Exception:
        pass


def _add_overlay_mark(
    window,
    path: str,
    *,
    page_number: int,
    rects: list[tuple],
    color: str,
    style: str = "highlight",
) -> None:
    _overlay_marks(window).append({
        "kind": "mark",
        "path": os.path.abspath(path),
        "page_number": int(page_number),
        "rects": [[float(v) for v in rect] for rect in rects],
        "color": color,
        "style": style,
    })
    _refresh_annotation_overlays(window)


def _update_note_rect_by_id(
    pdf: pikepdf.Pdf,
    *,
    page_idx: int,
    note_id: str,
    new_rect: tuple[float, float, float, float],
) -> bool:
    page = pdf.pages[page_idx]
    annots = page.get("/Annots", [])
    for annot_idx, annot in enumerate(annots):
        if _annotation_subtype(annot) != "/Text":
            continue
        current_id = _annotation_id(annot)
        if not current_id:
            rect = [float(v) for v in annot.get("/Rect", [])]
            current_id = _synthetic_note_id(page_idx + 1, annot_idx, rect, str(annot.get("/Contents", "")))
            annot["/NM"] = pikepdf.String(current_id)
        if current_id != note_id:
            continue
        annot["/Rect"] = pikepdf.Array([float(v) for v in new_rect])
        annot["/M"] = _pdf_date_now()
        return True
    return False


def _update_note_content_by_id(pdf: pikepdf.Pdf, *, note_id: str, content: str) -> bool:
    for page_idx, page in enumerate(pdf.pages):
        annots = page.get("/Annots", [])
        for annot_idx, annot in enumerate(annots):
            if _annotation_subtype(annot) != "/Text":
                continue
            current_id = _annotation_id(annot)
            if not current_id:
                rect = [float(v) for v in annot.get("/Rect", [])]
                current_id = _synthetic_note_id(page_idx + 1, annot_idx, rect, str(annot.get("/Contents", "")))
                annot["/NM"] = pikepdf.String(current_id)
            if current_id != note_id:
                continue
            annot["/Contents"] = pikepdf.String(content)
            annot["/M"] = _pdf_date_now()
            return True
    return False


def _delete_note_by_id(pdf: pikepdf.Pdf, *, note_id: str) -> bool:
    for page_idx, page in enumerate(pdf.pages):
        annots = page.get("/Annots", None)
        if annots is None:
            continue
        for idx, annot in enumerate(list(annots)):
            if _annotation_subtype(annot) != "/Text":
                continue
            current_id = _annotation_id(annot)
            if not current_id:
                rect = [float(v) for v in annot.get("/Rect", [])]
                current_id = _synthetic_note_id(page_idx + 1, idx, rect, str(annot.get("/Contents", "")))
            if current_id != note_id:
                continue
            del annots[idx]
            return True
    return False


def _find_note_by_id(pdf_path: str, note_id: str) -> dict | None:
    for item in load_annotations(pdf_path):
        if item.get("id") == note_id:
            return item
    return None


def _shorten_note_content(content: str, limit: int = 120) -> str:
    text = " ".join((content or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _notes_for_js(pdf_path: str) -> list[dict]:
    notes: list[dict] = []
    for item in load_annotations(pdf_path):
        rect = item.get("rect") or ()
        if not item.get("id") or len(rect) != 4:
            continue
        notes.append({
            "id": str(item["id"]),
            "page_number": int(item["page_number"]),
            "rect": [float(v) for v in rect],
            "content": str(item.get("content") or ""),
        })
    return notes


def _normalize_text(value: str) -> str:
    return " ".join((value or "").replace("\u00a0", " ").split())


def _tokenize_text(value: str) -> list[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []
    return [part for part in re.split(r"\s+", normalized) if part]


def _extract_words_with_pdfplumber(pdf_path: str, page_no: int) -> list[dict]:
    try:
        import pdfplumber
    except ImportError:
        return []

    words: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_no - 1]
        page_height = float(getattr(page, "height", 0.0) or 0.0)
        raw_words = page.extract_words(
            use_text_flow=False,
            keep_blank_chars=False,
            extra_attrs=["size"],
        ) or []
        for item in raw_words:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            left = float(item.get("x0", 0.0))
            right = float(item.get("x1", left))
            top_from_top = float(item.get("top", 0.0))
            bottom_from_top = float(item.get("bottom", top_from_top))
            if page_height > 0:
                top = page_height - top_from_top
                bottom = page_height - bottom_from_top
                if bottom > top:
                    bottom, top = top, bottom
            else:
                top = top_from_top
                bottom = bottom_from_top
            words.append({
                "text": text,
                "text_key": text.casefold(),
                "x0": left,
                "x1": right,
                "top": top,
                "bottom": bottom,
                "mid": (top + bottom) / 2.0,
                "size": float(item.get("size") or max(1.0, bottom - top)),
            })
    return words


def _line_rect_from_words(words: list[dict]) -> tuple[float, float, float, float]:
    left = min(float(word["x0"]) for word in words)
    right = max(float(word["x1"]) for word in words)
    bottom = min(float(word["bottom"]) for word in words)
    top = max(float(word["top"]) for word in words)
    return left, bottom, right, top


def _search_words_across_lines(words: list[dict], query_tokens: list[str]) -> list[tuple]:
    if not words or not query_tokens:
        return []

    normalized_words = [str(word["text_key"]) for word in words]
    matches: list[list[dict]] = []
    qlen = len(query_tokens)
    i = 0
    while i <= len(normalized_words) - qlen:
        if normalized_words[i:i + qlen] == query_tokens:
            matches.append(words[i:i + qlen])
            i += qlen
        else:
            i += 1

    rects: list[tuple] = []
    for match in matches:
        line_groups: list[list[dict]] = []
        current_group: list[dict] = []
        current_mid = None
        current_tol = 3.0

        for word in match:
            mid = float(word["mid"])
            tol = max(3.0, float(word["size"]) * 0.7)
            if current_group and current_mid is not None and abs(mid - current_mid) > max(current_tol, tol):
                line_groups.append(current_group)
                current_group = [word]
                current_mid = mid
                current_tol = tol
                continue

            current_group.append(word)
            if current_mid is None:
                current_mid = mid
                current_tol = tol
            else:
                count = len(current_group)
                current_mid = ((current_mid * (count - 1)) + mid) / count
                current_tol = max(current_tol, tol)

        if current_group:
            line_groups.append(current_group)

        for group in line_groups:
            if group:
                rects.append(_line_rect_from_words(group))

    return rects


def _search_text_on_page(pdf_path: str, page_no: int, text: str) -> list[tuple]:
    """Search text with pypdfium2. Returns [(left, bottom, right, top)] in PDF points."""
    import pypdfium2 as pdfium
    query_tokens = [token.casefold() for token in _tokenize_text(text)]
    if not query_tokens:
        return []

    words = _extract_words_with_pdfplumber(pdf_path, page_no)
    if words:
        rects = _search_words_across_lines(words, query_tokens)
        if rects:
            return rects

    rects = []
    doc = pdfium.PdfDocument(pdf_path)
    textpage = None
    searcher = None
    try:
        page = doc[page_no - 1]
        textpage = page.get_textpage()
        search_text = _normalize_text(text)
        if not search_text:
            return []
        searcher = textpage.search(search_text, match_case=False, match_whole_word=False)
        while True:
            res = searcher.get_next()
            if res is None:
                break
            # pypdfium2 v5+: get_next() returns (start_index, char_count)
            # Use count_rects + get_rect to get bounding boxes
            start, count = res
            n = textpage.count_rects(start, count)
            for i in range(n):
                r = textpage.get_rect(i)
                rects.append((float(r[0]), float(r[1]), float(r[2]), float(r[3])))
    finally:
        for obj in (searcher, textpage):
            try:
                close = getattr(obj, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass
        doc.close()
    return rects


def _page_rotation(page) -> int:
    try:
        return int(page.get("/Rotate", 0)) % 360
    except Exception:
        try:
            return int(page["/Rotate"]) % 360
        except Exception:
            return 0


def _normalize_box_for_page_rotation(
    box: tuple[float, float, float, float],
    page_w: float,
    page_h: float,
    rotation: int,
) -> tuple[float, float, float, float]:
    left, bottom, right, top = [float(v) for v in box]
    if rotation not in (90, 180, 270):
        return left, bottom, right, top

    def _map_point(x: float, y: float) -> tuple[float, float]:
        if rotation == 90:
            return y, page_h - x
        if rotation == 180:
            return page_w - x, page_h - y
        return page_w - y, x

    points = [
        _map_point(left, bottom),
        _map_point(left, top),
        _map_point(right, bottom),
        _map_point(right, top),
    ]
    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    return min(xs), min(ys), max(xs), max(ys)


def _add_pdf_annotation(pdf: pikepdf.Pdf, page_idx: int, subtype: str,
                         rects: list[tuple], color: list[float],
                         content: str = ""):
    """Add Highlight/Underline/StrikeOut/Text annotation using pikepdf."""
    _SUBTYPE = {
        "Highlight":  "/Highlight",
        "Underline":  "/Underline",
        "StrikeOut":  "/StrikeOut",
        "Text":       "/Text",
    }
    page = pdf.pages[page_idx]
    new_annots = []

    for (left, bottom, right, top) in rects:
        d = pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name(_SUBTYPE[subtype]),
            Rect=pikepdf.Array([left, bottom, right, top]),
            C=pikepdf.Array([float(c) for c in color]),
            F=4,
        )
        if subtype in ("Highlight", "Underline", "StrikeOut"):
            d["/QuadPoints"] = pikepdf.Array([
                left, top,    right, top,
                left, bottom, right, bottom,
            ])
        elif subtype == "Text":
            d["/Name"] = pikepdf.Name("/Note")
        if content:
            d["/Contents"] = pikepdf.String(content)
        if subtype == "Text":
            d["/Open"] = False
        new_annots.append(pdf.make_indirect(d))

    if "/Annots" not in page:
        page["/Annots"] = pikepdf.Array(new_annots)
    else:
        for a in new_annots:
            page["/Annots"].append(a)


# ── Highlight ─────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def highlight_text(window):
    """Highlight selected or searched text on current page."""
    wv = window._get_webview()

    def _apply(sel_text):
        text = (sel_text or "").strip()
        if not text:
            text, ok = QInputDialog.getText(
                window, "Tô sáng văn bản",
                "Nhập từ/cụm từ cần tô sáng:",
                QLineEdit.EchoMode.Normal,
            )
            if not ok or not text.strip():
                return
            text = text.strip()
        _do_highlight(window, text)

    if wv:
        wv.page().runJavaScript("window.getSelection().toString()", _apply)
    else:
        _apply("")


def _do_highlight(window, text: str):
    path = window.current_path
    page_no = _get_current_page(window)
    rects = _search_text_on_page(path, page_no, text)
    if not rects:
        show_warning(window, "Không tìm thấy",
            f'Không tìm thấy "{text}" trên trang {page_no}.')
        return
    try:
        _add_overlay_mark(
            window,
            path,
            page_number=page_no,
            rects=rects,
            color="rgba(250,204,21,.35)",
            style="highlight",
        )

        def _op(pdf):
            _add_pdf_annotation(pdf, page_no - 1, "Highlight", rects, [1.0, 1.0, 0.0])

        _queue_annotation_op(window, path, _op, delay_ms=350)
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã tô sáng {len(rects)} chỗ: \"{text}\"", 3000)
    except Exception as e:
        show_warning(window, "Lỗi tô sáng", str(e))


# ── Rotate ────────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def rotate_page_cw(window):
    """Rotate current page 90° clockwise."""
    _rotate_page(window, 90)


@require_document(show_message=True)
def rotate_page_ccw(window):
    """Rotate current page 90° counter-clockwise."""
    _rotate_page(window, -90)


def _rotate_page(window, degrees: int):
    path = window.current_path
    page_no = _get_current_page(window)
    try:
        with pikepdf.open(path) as pdf:
            page = pdf.pages[page_no - 1]
            try:
                current_rot = int(page["/Rotate"])
            except (KeyError, AttributeError):
                current_rot = 0
            page["/Rotate"] = (current_rot + degrees) % 360
            _save_pikepdf_reload(window, pdf)
        if hasattr(window, "status"):
            direction = "thuận chiều kim đồng hồ" if degrees > 0 else "ngược chiều kim đồng hồ"
            window.status.showMessage(f"Đã xoay trang {page_no} {direction}", 2000)
    except Exception as e:
        show_warning(window, "Lỗi xoay trang", str(e))


# ── Delete page ───────────────────────────────────────────────────────────────

@require_document(show_message=True)
def delete_current_page(window):
    """Delete the current page from the PDF."""
    path = window.current_path
    page_no = _get_current_page(window)
    try:
        with pikepdf.open(path) as pdf:
            total = len(pdf.pages)
            if total <= 1:
                show_warning(window, "Không thể xóa",
                    "Tài liệu chỉ có 1 trang, không thể xóa.")
                return
            reply = QMessageBox.question(
                window, "Xóa trang",
                f"Xóa trang {page_no}/{total}? Thao tác không thể hoàn tác.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            del pdf.pages[page_no - 1]
            _save_pikepdf_reload(window, pdf, keep_page=False)
        if hasattr(window, "status"):
            window.status.showMessage(f"Đã xóa trang {page_no}", 2000)
    except Exception as e:
        show_warning(window, "Lỗi xóa trang", str(e))


# ── Merge PDF ─────────────────────────────────────────────────────────────────

@require_document(show_message=True)
def merge_pdf(window):
    """Append another PDF to the current document."""
    other_path, _ = QFileDialog.getOpenFileName(
        window, "Chọn PDF cần ghép vào cuối", "", "PDF Files (*.pdf)"
    )
    if not other_path:
        return
    path = window.current_path
    try:
        with pikepdf.open(path) as pdf:
            with pikepdf.open(other_path) as other:
                pdf.pages.extend(other.pages)
            _save_pikepdf_reload(window, pdf, keep_page=False)
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã ghép PDF: {os.path.basename(other_path)}", 3000)
    except Exception as e:
        show_warning(window, "Lỗi ghép PDF", str(e))


# ── Extract pages ─────────────────────────────────────────────────────────────

@require_document(show_message=True)
def extract_pages(window):
    """Extract a range of pages to a new PDF file."""
    path = window.current_path
    with pikepdf.open(path) as _tmp:
        total = len(_tmp.pages)

    range_text, ok = QInputDialog.getText(
        window, "Trích xuất trang",
        f"Nhập trang cần trích (VD: 1-3,5,7-9). Tổng: {total} trang:",
        QLineEdit.EchoMode.Normal,
    )
    if not ok or not range_text.strip():
        return

    pages = _parse_page_range(range_text, total)
    if not pages:
        show_warning(window, "Lỗi", "Dải trang không hợp lệ.")
        return

    out_path, _ = QFileDialog.getSaveFileName(
        window, "Lưu trang trích xuất", "", "PDF Files (*.pdf)"
    )
    if not out_path:
        return

    try:
        dst = pikepdf.Pdf.new()
        with pikepdf.open(path) as src:
            for p in pages:
                dst.pages.append(src.pages[p - 1])
        dst.save(out_path)
        dst.close()
        show_info(window, "Trích xuất thành công",
            f"Đã lưu {len(pages)} trang vào:\n{out_path}")
    except Exception as e:
        show_warning(window, "Lỗi trích xuất", str(e))


def _parse_page_range(text: str, max_page: int) -> list[int]:
    pages = []
    for part in text.replace(" ", "").split(","):
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                start, end = max(1, int(a)), min(max_page, int(b))
                if start > end:
                    start, end = end, start
                pages.extend(range(start, end + 1))
            except ValueError:
                pass
        else:
            try:
                p = int(part)
                if 1 <= p <= max_page:
                    pages.append(p)
            except ValueError:
                pass
    return sorted(set(pages))


# ── Underline / Strikeout ─────────────────────────────────────────────────────

def _do_line_annot(window, text: str, annot_type: str):
    path = window.current_path
    page_no = _get_current_page(window)
    rects = _search_text_on_page(path, page_no, text)
    if not rects:
        show_warning(window, "Không tìm thấy",
            f'Không tìm thấy "{text}" trên trang {page_no}.')
        return
    try:
        subtype = "Underline" if annot_type == "underline" else "StrikeOut"
        color   = [0.0, 0.0, 1.0] if annot_type == "underline" else [1.0, 0.0, 0.0]
        overlay_style = "underline" if annot_type == "underline" else "strikeout"
        overlay_color = "rgba(37,99,235,.9)" if annot_type == "underline" else "rgba(220,38,38,.9)"
        _add_overlay_mark(
            window,
            path,
            page_number=page_no,
            rects=rects,
            color=overlay_color,
            style=overlay_style,
        )

        def _op(pdf):
            _add_pdf_annotation(pdf, page_no - 1, subtype, rects, color)

        _queue_annotation_op(window, path, _op, delay_ms=350)
        label = "gạch dưới" if annot_type == "underline" else "gạch ngang"
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã {label} {len(rects)} chỗ: \"{text}\"", 3000)
    except Exception as e:
        show_warning(window, "Lỗi chú thích", str(e))


@require_document(show_message=True)
def underline_text(window):
    """Gạch dưới văn bản được chọn hoặc nhập."""
    wv = window._get_webview()

    def _apply(sel_text):
        text = (sel_text or "").strip()
        if not text:
            text, ok = QInputDialog.getText(
                window, "Gạch dưới văn bản",
                "Nhập từ/cụm từ cần gạch dưới:",
                QLineEdit.EchoMode.Normal,
            )
            if not ok or not text.strip():
                return
            text = text.strip()
        _do_line_annot(window, text, "underline")

    if wv:
        wv.page().runJavaScript("window.getSelection().toString()", _apply)
    else:
        _apply("")


@require_document(show_message=True)
def strikeout_text(window):
    """Gạch ngang (strikeout) văn bản được chọn hoặc nhập."""
    wv = window._get_webview()

    def _apply(sel_text):
        text = (sel_text or "").strip()
        if not text:
            text, ok = QInputDialog.getText(
                window, "Gạch ngang văn bản",
                "Nhập từ/cụm từ cần gạch ngang:",
                QLineEdit.EchoMode.Normal,
            )
            if not ok or not text.strip():
                return
            text = text.strip()
        _do_line_annot(window, text, "strikeout")

    if wv:
        wv.page().runJavaScript("window.getSelection().toString()", _apply)
    else:
        _apply("")


# ── Comment (sticky note) ─────────────────────────────────────────────────────

@require_document(show_message=True)
def add_comment(window):
    """Add a sticky note, then allow dragging its rendered icon to refine placement."""
    path = getattr(window, "current_path", None)
    if not path:
        show_warning(window, "Không thể ghi chú", "Không tìm thấy tài liệu đang mở.")
        return

    content, ok = QInputDialog.getMultiLineText(
        window,
        "Thêm ghi chú",
        "Nội dung ghi chú:",
    )
    content = (content or "").strip()
    if not ok or not content:
        return

    page_no = _get_current_page(window)
    try:
        with pikepdf.open(path) as pdf:
            if page_no < 1 or page_no > len(pdf.pages):
                page_no = 1
            page = pdf.pages[page_no - 1]
            rect = _default_note_rect(page, _count_text_notes(page))
        note_id = f"3t-note-{uuid.uuid4().hex}"
        note = {
            "id": note_id,
            "page_number": page_no,
            "rect": [float(v) for v in rect],
            "content": content,
        }
        _overlay_notes(window)[note_id] = note

        def _op(pdf):
            add_annotation(
                pdf,
                page_idx=page_no - 1,
                subtype="Text",
                rect=rect,
                content=content,
                annot_id=note_id,
            )

        _queue_annotation_op(window, path, _op, delay_ms=250)
        enable_note_tools(window)
        if hasattr(window, "status"):
            window.status.showMessage(
                f"Đã thêm ghi chú vào trang {page_no}. Kéo icon để di chuyển, đúp chuột để sửa, chuột phải để xóa.",
                6000,
            )
        setattr(window, "_last_added_note_id", note_id)
    except Exception as exc:
        show_warning(window, "Lỗi thêm ghi chú", str(exc))
