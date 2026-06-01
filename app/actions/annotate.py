import os
import re
import uuid
from datetime import datetime, timezone

import pikepdf

from packages.qt_compat.QtCore import QEventLoop, QTimer
from packages.qt_compat.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)
from app.actions._guard import require_document
from app.actions._pdf_save import make_staged_pdf_path, replace_document_with_staged
from app.dialogs import show_warning, show_info


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
            for annot in annots:
                if _annotation_subtype(annot) != "/Text":
                    continue
                rect = [float(v) for v in annot.get("/Rect", [])]
                items.append({
                    "id": _annotation_id(annot),
                    "page_number": idx,
                    "type": "Text",
                    "content": str(annot.get("/Contents", "")),
                    "author": str(annot.get("/T", "")),
                    "modified": str(annot.get("/M", "")),
                    "rect": tuple(rect) if len(rect) == 4 else (),
                })
    return items


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
) -> str:
    """Add one supported annotation and return its stable PDF annotation id."""
    if subtype != "Text":
        raise ValueError(f"Unsupported annotation subtype: {subtype}")

    annot_id = f"3t-note-{uuid.uuid4().hex}"
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


_NOTE_PIN_PLACEMENT_JS = r"""(function(pageNum, pdfLeft, pdfBottom, pdfRight, pdfTop) {
    if (typeof window.__3tNotePlacementCleanup === 'function') {
        try { window.__3tNotePlacementCleanup(); } catch (_err) {}
    }
    window.__3tNotePlacementResult = null;

    function cleanup() {
        var old = document.getElementById('__3tNotePinOverlay');
        if (old && old.parentNode) old.parentNode.removeChild(old);
        var bar = document.getElementById('__3tNotePinBar');
        if (bar && bar.parentNode) bar.parentNode.removeChild(bar);
        document.removeEventListener('keydown', onKeyDown, true);
        document.removeEventListener('mousemove', onMouseMove, true);
        document.removeEventListener('mouseup', onMouseUp, true);
        window.__3tNotePlacementCleanup = null;
    }

    function finish(payload) {
        cleanup();
        window.__3tNotePlacementResult = payload;
    }

    function onKeyDown(event) {
        if (event.key === 'Escape') {
            finish({type: 'cancel'});
        }
    }

    window.__3tNotePlacementCleanup = cleanup;

    var app = window.PDFViewerApplication;
    var viewer = app && app.pdfViewer;
    var pageView = viewer && (viewer.getPageView
        ? viewer.getPageView(pageNum - 1)
        : (viewer._pages && viewer._pages[pageNum - 1]));
    if (!pageView || !pageView.viewport || !pageView.div) {
        finish({type: 'error', message: 'PDF viewer chưa sẵn sàng để đặt ghi chú.'});
        return;
    }

    var pageEl = pageView.div;
    var viewport = pageView.viewport;
    var coords = viewport.convertToViewportRectangle([pdfLeft, pdfBottom, pdfRight, pdfTop]);
    var centerX = (coords[0] + coords[2]) / 2;
    var centerY = (coords[1] + coords[3]) / 2;
    var dragging = false;

    var pin = document.createElement('div');
    pin.id = '__3tNotePinOverlay';
    pin.title = 'Kéo để đặt vị trí ghi chú';
    pin.innerHTML = '<div class="pin-head"></div><div class="pin-tip"></div>';
    pin.style.cssText = [
        'position:absolute',
        'width:30px',
        'height:38px',
        'z-index:10000',
        'cursor:grab',
        'user-select:none',
        'touch-action:none',
        'filter:drop-shadow(0 4px 6px rgba(0,0,0,.35))'
    ].join(';');

    var style = document.createElement('style');
    style.textContent = [
        '#__3tNotePinOverlay .pin-head{position:absolute;left:4px;top:0;width:22px;height:22px;border-radius:50%;background:#facc15;border:2px solid #92400e;box-sizing:border-box;}',
        '#__3tNotePinOverlay .pin-tip{position:absolute;left:13px;top:18px;width:4px;height:19px;background:#92400e;border-radius:2px;transform:rotate(18deg);transform-origin:top center;}',
        '#__3tNotePinBar{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:10001;background:rgba(15,23,42,.94);color:#fff;border-radius:8px;padding:10px 12px;font:13px sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.35);display:flex;gap:10px;align-items:center;}',
        '#__3tNotePinBar button{border:0;border-radius:6px;padding:7px 12px;font-weight:600;cursor:pointer;}',
        '#__3tNotePinSave{background:#16a34a;color:#fff;}',
        '#__3tNotePinCancel{background:#e2e8f0;color:#0f172a;}'
    ].join('\n');
    pin.appendChild(style);
    pageEl.appendChild(pin);

    function clamp(value, minValue, maxValue) {
        return Math.max(minValue, Math.min(value, maxValue));
    }

    function setPinPosition(x, y) {
        centerX = clamp(x, 12, Math.max(12, pageEl.clientWidth - 12));
        centerY = clamp(y, 12, Math.max(12, pageEl.clientHeight - 12));
        pin.style.left = (centerX - 15) + 'px';
        pin.style.top = (centerY - 32) + 'px';
    }

    function currentPdfRect() {
        var center = viewport.convertToPdfPoint(centerX, centerY);
        var half = 9.0;
        return [
            center[0] - half,
            center[1] - half,
            center[0] + half,
            center[1] + half
        ];
    }

    function eventToPagePoint(event) {
        var rect = pageEl.getBoundingClientRect();
        return {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
        };
    }

    function onMouseMove(event) {
        if (!dragging) return;
        event.preventDefault();
        event.stopPropagation();
        var point = eventToPagePoint(event);
        setPinPosition(point.x, point.y);
    }

    function onMouseUp(event) {
        if (!dragging) return;
        event.preventDefault();
        event.stopPropagation();
        dragging = false;
        pin.style.cursor = 'grab';
    }

    pin.addEventListener('mousedown', function(event) {
        event.preventDefault();
        event.stopPropagation();
        dragging = true;
        pin.style.cursor = 'grabbing';
        var point = eventToPagePoint(event);
        setPinPosition(point.x, point.y);
    }, true);
    document.addEventListener('mousemove', onMouseMove, true);
    document.addEventListener('mouseup', onMouseUp, true);
    document.addEventListener('keydown', onKeyDown, true);

    var bar = document.createElement('div');
    bar.id = '__3tNotePinBar';
    bar.innerHTML = '<span>Kéo ghim đến vị trí cần đặt</span><button id="__3tNotePinSave">Lưu vị trí</button><button id="__3tNotePinCancel">Hủy</button>';
    document.body.appendChild(bar);
    document.getElementById('__3tNotePinSave').addEventListener('click', function(event) {
        event.preventDefault();
        finish({type: 'save', page_number: pageNum, box: currentPdfRect()});
    });
    document.getElementById('__3tNotePinCancel').addEventListener('click', function(event) {
        event.preventDefault();
        finish({type: 'cancel'});
    });

    setPinPosition(centerX, centerY);
})(%d, %f, %f, %f, %f);"""


_CLEAR_NOTE_PIN_PLACEMENT_JS = """(function() {
    if (typeof window.__3tNotePlacementCleanup === 'function') {
        try { window.__3tNotePlacementCleanup(); } catch (_err) {}
    }
    var old = document.getElementById('__3tNotePinOverlay');
    if (old && old.parentNode) old.parentNode.removeChild(old);
    var bar = document.getElementById('__3tNotePinBar');
    if (bar && bar.parentNode) bar.parentNode.removeChild(bar);
    window.__3tNotePlacementResult = null;
})();"""


def _place_note_pin_on_viewer(
    window,
    *,
    page_no: int,
    default_rect: tuple[float, float, float, float],
) -> dict | None:
    web_view = None
    try:
        getter = getattr(window, "_get_webview", None)
        web_view = getter() if callable(getter) else None
    except Exception:
        web_view = None
    if web_view is None:
        return {"type": "save", "page_number": page_no, "box": default_rect}

    result: dict = {}
    loop = QEventLoop(window)
    poll_timer = QTimer(window)
    poll_timer.setInterval(80)

    def _poll_result(js_result):
        if not isinstance(js_result, dict) or not js_result.get("type"):
            return
        result.update(js_result)
        poll_timer.stop()
        if loop.isRunning():
            loop.quit()

    def _poll():
        web_view.page().runJavaScript("window.__3tNotePlacementResult", _poll_result)

    poll_timer.timeout.connect(_poll)
    if hasattr(window, "status"):
        window.status.showMessage("Kéo ghim ghi chú đến vị trí cần đặt, rồi bấm Lưu vị trí. Esc để hủy.", 0)

    try:
        web_view.page().runJavaScript(_CLEAR_NOTE_PIN_PLACEMENT_JS)
        web_view.page().runJavaScript(_NOTE_PIN_PLACEMENT_JS % (page_no, *default_rect))
        poll_timer.start()
        loop.exec()
    finally:
        poll_timer.stop()
        web_view.page().runJavaScript(_CLEAR_NOTE_PIN_PLACEMENT_JS)
        if hasattr(window, "status"):
            window.status.showMessage("", 0)

    return result or None


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
        with pikepdf.open(path) as pdf:
            _add_pdf_annotation(pdf, page_no - 1, "Highlight", rects, [1.0, 1.0, 0.0])
            _save_pikepdf_reload(window, pdf)
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
        with pikepdf.open(path) as pdf:
            _add_pdf_annotation(pdf, page_no - 1, subtype, rects, color)
            _save_pikepdf_reload(window, pdf)
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
    """Add a standards-compliant sticky note by dragging a pin on the PDF page."""
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
            default_rect = _default_note_rect(page, _count_text_notes(page))

        placement = _place_note_pin_on_viewer(
            window,
            page_no=page_no,
            default_rect=default_rect,
        )
        if not placement or placement.get("type") == "cancel":
            return
        if placement.get("type") == "error":
            show_warning(window, "Không thể đặt ghi chú", str(placement.get("message") or "PDF viewer chưa sẵn sàng."))
            return

        page_no = int(placement.get("page_number") or page_no)
        with pikepdf.open(path) as pdf:
            if page_no < 1 or page_no > len(pdf.pages):
                page_no = 1
            page = pdf.pages[page_no - 1]
            raw_rect = placement.get("box") or default_rect
            rect = _clamp_note_rect_to_page(page, tuple(float(v) for v in raw_rect))
            note_id = add_annotation(
                pdf,
                page_idx=page_no - 1,
                subtype="Text",
                rect=rect,
                content=content,
            )
            _save_pikepdf_reload(window, pdf)
        if hasattr(window, "status"):
            window.status.showMessage(f"Đã thêm ghi chú vào trang {page_no}", 3000)
        setattr(window, "_last_added_note_id", note_id)
    except Exception as exc:
        show_warning(window, "Lỗi thêm ghi chú", str(exc))
