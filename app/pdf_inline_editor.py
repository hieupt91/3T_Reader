"""Inline PDF object editor — text box and image placement directly on the PDF canvas.

Flow:
  Text:  click tool → click on PDF page → type in overlay → Ctrl+Enter / panel button → insert
  Image: click tool → pick file → click on PDF → drag/resize preview → Enter / panel button → insert

Bridge reconnection strategy:
  Every injection always re-creates the QWebChannel connection so the bridge is never stale.
  The JS overlay is NOT removed on commit — the PDF viewer reload naturally cleans it up,
  which removes the blank "flash" between overlay disappearing and rebuilt PDF appearing.
"""
from __future__ import annotations

import base64
import os

from packages.qt_compat.QtCore import QObject, QEventLoop, Qt, pyqtSignal, pyqtSlot
from packages.qt_compat.QtGui import QColor
from packages.qt_compat.QtWidgets import (
    QColorDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout,
)


# ── Bridges (JS ↔ Python via QWebChannel) ────────────────────────────────────

class InlineTextBridge(QObject):
    ready     = pyqtSignal(int)                                   # page placed on
    confirmed = pyqtSignal(int, float, float, float, float, str)  # page,l,b,r,t,text
    cancelled = pyqtSignal()

    @pyqtSlot(int)
    def reportReady(self, page): self.ready.emit(page)

    @pyqtSlot(int, float, float, float, float, str)
    def confirmText(self, page, l, b, r, t, text):
        self.confirmed.emit(page, l, b, r, t, text)

    @pyqtSlot()
    def cancelEdit(self): self.cancelled.emit()


class InlineImageBridge(QObject):
    ready     = pyqtSignal(int)
    confirmed = pyqtSignal(int, float, float, float, float)       # page,l,b,r,t
    cancelled = pyqtSignal()

    @pyqtSlot(int)
    def reportReady(self, page): self.ready.emit(page)

    @pyqtSlot(int, float, float, float, float)
    def confirmImage(self, page, l, b, r, t):
        self.confirmed.emit(page, l, b, r, t)

    @pyqtSlot()
    def cancelEdit(self): self.cancelled.emit()


# ── Floating panel (font controls + Confirm/Cancel) ───────────────────────────

class InlineEditPanel(QFrame):
    committed = pyqtSignal()
    cancelled = pyqtSignal()
    font_changed = pyqtSignal(int, str)   # size, hex color

    def __init__(self, parent=None, *, mode: str = "text"):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._color = QColor(0, 0, 0)
        self._mode  = mode
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background:#1A1E30; border:1.5px solid #2A5090; border-radius:10px; }"
            "QLabel { color:#B0C8F0; font-size:12px; background:transparent; border:none; padding:0; }"
            "QSpinBox { background:#10121C; color:#D8E8FF; border:1px solid #304080; "
            "           border-radius:4px; padding:2px 6px; }"
            "QPushButton { border-radius:5px; padding:5px 14px; font-size:12px; font-weight:600; }"
        )
        self._setup_ui()
        self.adjustSize()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        icon  = "✏️" if self._mode == "text" else "🖼️"
        title = "Chèn văn bản vào PDF" if self._mode == "text" else "Chèn ảnh vào PDF"
        lbl   = QLabel(f"{icon}  {title}")
        lbl.setStyleSheet(
            "color:#7AAAE8; font-size:11px; font-weight:700; background:transparent; border:none;"
        )
        root.addWidget(lbl)

        if self._mode == "text":
            row = QHBoxLayout(); row.setSpacing(8)
            row.addWidget(QLabel("Cỡ chữ:"))
            self._size_spin = QSpinBox()
            self._size_spin.setRange(6, 96)
            self._size_spin.setValue(14)
            self._size_spin.setFixedWidth(64)
            self._size_spin.valueChanged.connect(self._emit_font)
            row.addWidget(self._size_spin)
            self._color_btn = QPushButton()
            self._color_btn.setFixedSize(72, 26)
            self._color_btn.clicked.connect(self._pick_color)
            self._refresh_color_btn()
            row.addWidget(self._color_btn)
            root.addLayout(row)

            hint = QLabel("Gõ trực tiếp trên PDF  ·  Ctrl+Enter để chèn  ·  Esc để hủy")
        else:
            hint = QLabel("Kéo di chuyển  ·  Kéo góc resize  ·  Enter xác nhận  ·  Esc hủy")

        hint.setStyleSheet("color:#3A4E6A; font-size:10px; background:transparent; border:none;")
        root.addWidget(hint)

        row2 = QHBoxLayout(); row2.setSpacing(8); row2.addStretch()
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet(
            "QPushButton{background:transparent;color:#FF6655;border:1.5px solid #FF6655;}"
            "QPushButton:hover{background:#3A1010;}"
        )
        btn_cancel.clicked.connect(self.cancelled)
        row2.addWidget(btn_cancel)

        ok_lbl = "Chèn vào PDF" if self._mode == "text" else "Đặt ảnh vào PDF"
        btn_ok = QPushButton(ok_lbl)
        btn_ok.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #FF7700,stop:1 #FF4400);color:white;border:none;}"
            "QPushButton:hover{background:#FF9900;}"
        )
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.committed)
        row2.addWidget(btn_ok)
        root.addLayout(row2)

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Màu chữ")
        if c.isValid():
            self._color = c
            self._refresh_color_btn()
            self._emit_font()

    def _refresh_color_btn(self):
        c    = self._color
        luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        txt  = "#000" if luma > 128 else "#FFF"
        self._color_btn.setStyleSheet(
            f"QPushButton{{background:{c.name()};color:{txt};border:1px solid #555;"
            "border-radius:4px;font-size:11px;}}"
        )
        self._color_btn.setText("Màu chữ")

    def _emit_font(self):
        if hasattr(self, "_size_spin"):
            self.font_changed.emit(self._size_spin.value(), self._color.name())

    def get_font_size(self) -> int:
        return self._size_spin.value() if hasattr(self, "_size_spin") else 14

    def get_color_tuple(self) -> tuple:
        c = self._color
        return (c.redF(), c.greenF(), c.blueF())

    def position_near(self, window):
        self.adjustSize()
        geo = window.frameGeometry()
        self.move(max(0, geo.right() - self.width() - 24), max(0, geo.top() + 80))


# ── JavaScript: inline text overlay ──────────────────────────────────────────
# Always re-injects fresh: clears old state, reconnects bridge via new QWebChannel.
# Does NOT remove overlay on commit — page reload naturally clears it (no flash).

INLINE_TEXT_JS = r"""
(function () {
    /* ── clear any leftover overlay from previous call ── */
    if (window.__3TTextState) {
        var _old = window.__3TTextState;
        if (_old.overlay && _old.overlay.parentNode)
            _old.overlay.parentNode.removeChild(_old.overlay);
    }
    window.__3TTextState   = { overlay: null, textarea: null, pageNumber: null, pageView: null };
    window.__3TTextBridge  = null;   /* will be set by fresh QWebChannel below */

    var S = window.__3TTextState;

    function getBox() {
        var ov = S.overlay;
        var l  = parseFloat(ov.style.left)  || 0;
        var t  = parseFloat(ov.style.top)   || 0;
        var w  = parseFloat(ov.style.width) || 200;
        var h  = parseFloat(ov.style.height)|| 44;
        var p1 = S.pageView.viewport.convertToPdfPoint(l,     t);
        var p2 = S.pageView.viewport.convertToPdfPoint(l + w, t + h);
        return { l:Math.min(p1[0],p2[0]), b:Math.min(p1[1],p2[1]),
                 r:Math.max(p1[0],p2[0]), t:Math.max(p1[1],p2[1]) };
    }

    /* called by Python panel "Chèn" button OR Ctrl+Enter in textarea */
    window.__3TTextCommit = function () {
        if (!S.textarea || !S.pageView) return;
        var text = S.textarea.value.trim();
        var br   = window.__3TTextBridge;
        if (!br) return;
        if (!text) { br.cancelEdit(); return; }
        var box = getBox();
        /* Keep overlay visible — page reload will remove it naturally */
        br.confirmText(S.pageNumber, box.l, box.b, box.r, box.t, text);
    };

    window.__3TTextCancel = function () {
        var br = window.__3TTextBridge;
        if (S.overlay && S.overlay.parentNode)
            S.overlay.parentNode.removeChild(S.overlay);
        S.overlay = null;
        document.body.style.cursor = '';
        if (br) br.cancelEdit();
    };

    /* update textarea font live when panel sliders change */
    window.__3TTextUpdateFont = function (size, colorHex) {
        if (S.textarea) {
            S.textarea.style.fontSize  = size + 'px';
            S.textarea.style.color     = colorHex;
        }
    };

    function startListen() {
        document.body.style.cursor = 'text';

        function clickHandler(e) {
            var page = e.target.closest('.page');
            if (!page) return;
            e.preventDefault(); e.stopPropagation();
            document.removeEventListener('click', clickHandler, true);
            document.body.style.cursor = '';

            var pn  = parseInt(page.dataset.pageNumber, 10);
            var pv  = PDFViewerApplication.pdfViewer;
            var pgv = pv.getPageView ? pv.getPageView(pn - 1) : pv._pages[pn - 1];
            var pr  = page.getBoundingClientRect();
            var cx  = e.clientX - pr.left;
            var cy  = e.clientY - pr.top;

            S.pageNumber = pn;
            S.pageView   = pgv;

            /* ── build overlay div ── */
            var ov = document.createElement('div');
            ov.style.cssText =
                'position:absolute;left:' + cx + 'px;top:' + cy + 'px;' +
                'width:220px;min-height:48px;' +
                'border:2px solid #1A7AFF;' +
                'background:rgba(255,255,255,0.97);' +
                'z-index:9999;box-sizing:border-box;border-radius:4px;' +
                'box-shadow:0 4px 20px rgba(26,122,255,0.4);cursor:move;';

            /* badge label */
            var badge = document.createElement('div');
            badge.textContent = '✏️ Văn bản — Ctrl+Enter để chèn';
            badge.style.cssText =
                'position:absolute;top:-26px;left:0;white-space:nowrap;' +
                'font-size:10px;color:#fff;background:#1A7AFF;' +
                'padding:3px 10px;border-radius:10px;pointer-events:none;' +
                'box-shadow:0 1px 6px rgba(0,0,0,0.3);';
            ov.appendChild(badge);

            /* textarea */
            var ta = document.createElement('textarea');
            ta.placeholder = 'Gõ văn bản…';
            ta.style.cssText =
                'display:block;width:calc(100% - 10px);min-height:36px;' +
                'margin:5px;border:none;outline:none;background:transparent;' +
                'resize:none;font-family:Arial,sans-serif;font-size:14px;' +
                'color:#000;line-height:1.5;overflow:hidden;cursor:text;';
            ta.addEventListener('input', function () {
                ta.style.height = 'auto';
                ta.style.height = ta.scrollHeight + 'px';
                ov.style.height = (ta.scrollHeight + 20) + 'px';
            });
            ov.appendChild(ta);

            /* resize corner */
            var rh = document.createElement('div');
            rh.style.cssText =
                'position:absolute;right:-7px;bottom:-7px;width:14px;height:14px;' +
                'background:#1A7AFF;border:2px solid #fff;border-radius:3px;' +
                'cursor:nwse-resize;z-index:10000;';
            ov.appendChild(rh);

            /* drag move */
            ov.addEventListener('mousedown', function (ev) {
                if (ev.target === rh || ev.target === ta) return;
                var sl = parseFloat(ov.style.left), st = parseFloat(ov.style.top);
                var sx = ev.clientX, sy = ev.clientY;
                function onM(e) {
                    ov.style.left = (sl + e.clientX - sx) + 'px';
                    ov.style.top  = (st + e.clientY - sy) + 'px';
                }
                function onU() {
                    document.removeEventListener('mousemove', onM, true);
                    document.removeEventListener('mouseup',   onU, true);
                }
                document.addEventListener('mousemove', onM, true);
                document.addEventListener('mouseup',   onU, true);
                ev.preventDefault();
            });

            /* resize drag */
            rh.addEventListener('mousedown', function (ev) {
                ev.stopPropagation();
                var sw = parseFloat(ov.style.width) || 220;
                var sh = parseFloat(ov.style.height)|| 48;
                var sx = ev.clientX, sy = ev.clientY;
                function onM(e) {
                    ov.style.width  = Math.max(80,  sw + e.clientX - sx) + 'px';
                    var nh = Math.max(36, sh + e.clientY - sy);
                    ov.style.height = nh + 'px';
                    ta.style.height = (nh - 20) + 'px';
                }
                function onU() {
                    document.removeEventListener('mousemove', onM, true);
                    document.removeEventListener('mouseup',   onU, true);
                }
                document.addEventListener('mousemove', onM, true);
                document.addEventListener('mouseup',   onU, true);
                ev.preventDefault();
            });

            /* keyboard shortcuts */
            ta.addEventListener('keydown', function (ev) {
                if (ev.key === 'Enter' && ev.ctrlKey) {
                    ev.preventDefault();
                    window.__3TTextCommit();
                }
                if (ev.key === 'Escape') { window.__3TTextCancel(); }
            });

            page.appendChild(ov);
            S.overlay  = ov;
            S.textarea = ta;
            ta.focus();

            var br = window.__3TTextBridge;
            if (br) br.reportReady(pn);
        }

        document.addEventListener('click', clickHandler, true);
    }

    /* ── Always re-connect to fresh bridge ── */
    function attach() {
        if (typeof QWebChannel === 'undefined') {
            var s = document.createElement('script');
            s.src = 'qrc:///qtwebchannel/qwebchannel.js';
            s.onload = attach;
            document.head.appendChild(s);
            return;
        }
        if (!(window.qt && qt.webChannelTransport)) {
            setTimeout(attach, 100);
            return;
        }
        new QWebChannel(qt.webChannelTransport, function (ch) {
            window.__3TTextBridge = ch.objects.inlineTextBridge || null;
            startListen();
        });
    }
    attach();
})();
"""


# ── JavaScript: inline image overlay ─────────────────────────────────────────

INLINE_IMAGE_JS = r"""
(function () {
    /* clear old overlay */
    if (window.__3TImgState && window.__3TImgState.overlay) {
        var _ov = window.__3TImgState.overlay;
        if (_ov.parentNode) _ov.parentNode.removeChild(_ov);
    }
    window.__3TImgState  = { overlay: null, pageNumber: null, pageView: null };
    window.__3TImgBridge = null;

    var S = window.__3TImgState;

    window.__3TImgConfirm = function () {
        if (!S.overlay || !S.pageView) return;
        var ov = S.overlay;
        var l  = parseFloat(ov.style.left)  || 0;
        var t  = parseFloat(ov.style.top)   || 0;
        var w  = parseFloat(ov.style.width) || 200;
        var h  = parseFloat(ov.style.height)|| 150;
        var p1 = S.pageView.viewport.convertToPdfPoint(l,     t);
        var p2 = S.pageView.viewport.convertToPdfPoint(l + w, t + h);
        var br = window.__3TImgBridge;
        /* keep overlay — page reload clears it */
        if (br) br.confirmImage(
            S.pageNumber,
            Math.min(p1[0],p2[0]), Math.min(p1[1],p2[1]),
            Math.max(p1[0],p2[0]), Math.max(p1[1],p2[1])
        );
    };

    window.__3TImgCancel = function () {
        if (S.overlay && S.overlay.parentNode)
            S.overlay.parentNode.removeChild(S.overlay);
        S.overlay = null;
        document.body.style.cursor = '';
        var br = window.__3TImgBridge;
        if (br) br.cancelEdit();
    };

    function startListen(imgUrl) {
        document.body.style.cursor = 'crosshair';

        function clickHandler(e) {
            var page = e.target.closest('.page');
            if (!page) return;
            e.preventDefault(); e.stopPropagation();
            document.removeEventListener('click', clickHandler, true);
            document.body.style.cursor = '';

            var pn  = parseInt(page.dataset.pageNumber, 10);
            var pv  = PDFViewerApplication.pdfViewer;
            var pgv = pv.getPageView ? pv.getPageView(pn - 1) : pv._pages[pn - 1];
            var pr  = page.getBoundingClientRect();
            var cx  = e.clientX - pr.left;
            var cy  = e.clientY - pr.top;

            S.pageNumber = pn;
            S.pageView   = pgv;

            var ov = document.createElement('div');
            ov.style.cssText =
                'position:absolute;left:' + (cx - 100) + 'px;top:' + (cy - 75) + 'px;' +
                'width:200px;height:150px;' +
                'border:2px solid #1A7AFF;z-index:9999;' +
                'box-sizing:border-box;border-radius:4px;' +
                'box-shadow:0 4px 20px rgba(26,122,255,0.4);' +
                'cursor:move;overflow:hidden;';

            var img = document.createElement('img');
            img.src = imgUrl;
            img.style.cssText = 'width:100%;height:100%;object-fit:contain;pointer-events:none;display:block;';
            ov.appendChild(img);

            var badge = document.createElement('div');
            badge.textContent = '🖼️ Ảnh — kéo di chuyển · kéo góc resize · Enter xác nhận';
            badge.style.cssText =
                'position:absolute;top:-26px;left:0;white-space:nowrap;' +
                'font-size:10px;color:#fff;background:#1A7AFF;' +
                'padding:3px 10px;border-radius:10px;pointer-events:none;' +
                'box-shadow:0 1px 6px rgba(0,0,0,0.3);';
            ov.appendChild(badge);

            var rh = document.createElement('div');
            rh.style.cssText =
                'position:absolute;right:-7px;bottom:-7px;width:14px;height:14px;' +
                'background:#1A7AFF;border:2px solid #fff;border-radius:3px;' +
                'cursor:nwse-resize;z-index:10000;';
            ov.appendChild(rh);

            /* drag */
            ov.addEventListener('mousedown', function (ev) {
                if (ev.target === rh) return;
                var sl=parseFloat(ov.style.left), st=parseFloat(ov.style.top);
                var sx=ev.clientX, sy=ev.clientY;
                function onM(e){ ov.style.left=(sl+e.clientX-sx)+'px'; ov.style.top=(st+e.clientY-sy)+'px'; }
                function onU(){ document.removeEventListener('mousemove',onM,true); document.removeEventListener('mouseup',onU,true); }
                document.addEventListener('mousemove',onM,true);
                document.addEventListener('mouseup',onU,true);
                ev.preventDefault();
            });

            /* resize */
            rh.addEventListener('mousedown', function (ev) {
                ev.stopPropagation();
                var sw=parseFloat(ov.style.width)||200, sh=parseFloat(ov.style.height)||150;
                var sx=ev.clientX, sy=ev.clientY;
                function onM(e){ ov.style.width=Math.max(40,sw+e.clientX-sx)+'px'; ov.style.height=Math.max(30,sh+e.clientY-sy)+'px'; }
                function onU(){ document.removeEventListener('mousemove',onM,true); document.removeEventListener('mouseup',onU,true); }
                document.addEventListener('mousemove',onM,true);
                document.addEventListener('mouseup',onU,true);
                ev.preventDefault();
            });

            /* keyboard */
            function kh(ev) {
                if (ev.key === 'Enter')  { window.__3TImgConfirm(); document.removeEventListener('keydown',kh,true); }
                if (ev.key === 'Escape') { window.__3TImgCancel();  document.removeEventListener('keydown',kh,true); }
            }
            document.addEventListener('keydown', kh, true);

            page.appendChild(ov);
            S.overlay = ov;

            var br = window.__3TImgBridge;
            if (br) br.reportReady(pn);
        }

        document.addEventListener('click', clickHandler, true);
    }

    function attach() {
        if (typeof QWebChannel === 'undefined') {
            var s = document.createElement('script');
            s.src = 'qrc:///qtwebchannel/qwebchannel.js';
            s.onload = attach;
            document.head.appendChild(s);
            return;
        }
        if (!(window.qt && qt.webChannelTransport)) {
            setTimeout(attach, 100);
            return;
        }
        new QWebChannel(qt.webChannelTransport, function (ch) {
            window.__3TImgBridge = ch.objects.inlineImageBridge || null;
            startListen(window.__3TInlineImageUrl || '');
        });
    }
    attach();
})();
"""


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_web_view(window):
    getter = getattr(window, "_get_webview", None)
    return getter() if callable(getter) else None


def _setup_webchannel(web_view, parent, name, bridge):
    from packages.qt_compat.QtWebChannel import QWebChannel as _WC
    ch = _WC(parent)
    ch.registerObject(name, bridge)
    web_view.page().setWebChannel(ch)
    return ch


def _teardown_webchannel(web_view):
    if web_view is None:
        return
    try:
        web_view.page().setWebChannel(None)
    except RuntimeError:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def run_inline_text(window) -> dict | None:
    """Inline text editor on PDF canvas.
    Returns {page_number, box, text, font_size, color_tuple} or None."""
    web_view = _get_web_view(window)
    if web_view is None:
        return None

    bridge = InlineTextBridge(window)
    _setup_webchannel(web_view, window, "inlineTextBridge", bridge)

    panel  = InlineEditPanel(window, mode="text")
    panel.position_near(window)
    result: dict = {}
    loop   = QEventLoop(window)

    # Panel font slider → update JS textarea styling live
    def _on_font(size, hex_color):
        web_view.page().runJavaScript(
            f"typeof window.__3TTextUpdateFont === 'function' && "
            f"window.__3TTextUpdateFont({size}, '{hex_color}');"
        )
    panel.font_changed.connect(_on_font)

    # Panel "Chèn" → capture font settings then trigger JS commit
    def _on_commit():
        result["font_size"]   = panel.get_font_size()
        result["color_tuple"] = panel.get_color_tuple()
        panel.hide()
        web_view.page().runJavaScript(
            "typeof window.__3TTextCommit === 'function' && window.__3TTextCommit();"
        )
    panel.committed.connect(_on_commit)

    # Panel "Hủy"
    def _on_cancel():
        panel.hide()
        web_view.page().runJavaScript(
            "typeof window.__3TTextCancel === 'function' && window.__3TTextCancel();"
        )
    panel.cancelled.connect(_on_cancel)

    # JS confirmed → store result
    def _confirmed(page, l, b, r, t, text):
        text = text.strip()
        if not text:
            result.clear()
        else:
            result.update({
                "page_number":  max(1, int(page)),
                "box":          (l, b, r, t),
                "text":         text,
                "font_size":    result.get("font_size", panel.get_font_size()),
                "color_tuple":  result.get("color_tuple", panel.get_color_tuple()),
            })
        if loop.isRunning(): loop.quit()

    def _cancelled():
        result.clear()
        if loop.isRunning(): loop.quit()

    def _ready(page):
        panel.show(); panel.raise_(); panel.activateWindow()

    bridge.ready.connect(_ready)
    bridge.confirmed.connect(_confirmed)
    bridge.cancelled.connect(_cancelled)

    if hasattr(window, "status"):
        window.status.showMessage(
            "Click vào vị trí trên PDF để đặt text box  ·  Esc hủy", 0
        )
    try:
        web_view.page().runJavaScript(INLINE_TEXT_JS)
        loop.exec()
    finally:
        panel.close()
        _teardown_webchannel(web_view)
        if hasattr(window, "status"):
            window.status.showMessage("", 0)

    return result if result.get("text") else None


def run_inline_image(window, image_path: str) -> dict | None:
    """Inline image placement on PDF canvas.
    Returns {page_number, box} or None."""
    web_view = _get_web_view(window)
    if web_view is None:
        return None

    # Encode image as data URL for JS preview (no file-system access from renderer)
    try:
        with open(image_path, "rb") as f:
            raw = f.read()
        ext  = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png",
                "bmp": "bmp", "webp": "webp"}.get(ext, "png")
        data_url = f"data:image/{mime};base64,{base64.b64encode(raw).decode()}"
    except Exception:
        data_url = ""

    bridge = InlineImageBridge(window)
    _setup_webchannel(web_view, window, "inlineImageBridge", bridge)

    panel  = InlineEditPanel(window, mode="image")
    panel.position_near(window)
    result: dict = {}
    loop   = QEventLoop(window)

    def _on_commit():
        panel.hide()
        web_view.page().runJavaScript(
            "typeof window.__3TImgConfirm === 'function' && window.__3TImgConfirm();"
        )
    def _on_cancel():
        panel.hide()
        web_view.page().runJavaScript(
            "typeof window.__3TImgCancel === 'function' && window.__3TImgCancel();"
        )
    panel.committed.connect(_on_commit)
    panel.cancelled.connect(_on_cancel)

    def _confirmed(page, l, b, r, t):
        result.update({"page_number": max(1, int(page)), "box": (l, b, r, t)})
        if loop.isRunning(): loop.quit()

    def _cancelled():
        result.clear()
        if loop.isRunning(): loop.quit()

    def _ready(page):
        panel.show(); panel.raise_(); panel.activateWindow()

    bridge.ready.connect(_ready)
    bridge.confirmed.connect(_confirmed)
    bridge.cancelled.connect(_cancelled)

    if hasattr(window, "status"):
        window.status.showMessage(
            "Click vào PDF để đặt ảnh  ·  Kéo/resize  ·  Enter xác nhận  ·  Esc hủy", 0
        )
    try:
        # Set image URL before injecting the script
        web_view.page().runJavaScript(f"window.__3TInlineImageUrl = {repr(data_url)};")
        web_view.page().runJavaScript(INLINE_IMAGE_JS)
        loop.exec()
    finally:
        panel.close()
        _teardown_webchannel(web_view)
        if hasattr(window, "status"):
            window.status.showMessage("", 0)

    return result if result.get("box") else None
