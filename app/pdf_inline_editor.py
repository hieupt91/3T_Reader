"""Inline PDF object editor — text box and image placement directly on the PDF canvas.

Flow:
  Text:  click tool → click on PDF page → type in overlay → Ctrl+Enter / panel button → insert
  Image: click tool → pick file → click on PDF → drag/resize preview → Enter / panel button → insert

Bridge strategy:
  Inline tools use the stable shared viewer QWebChannel helper/proxy.
  The JS overlay is NOT removed on commit — the PDF viewer reload naturally cleans it up,
  which removes the blank "flash" between overlay disappearing and rebuilt PDF appearing.
"""
from __future__ import annotations

import base64
import os

from packages.qt_compat.QtCore import QObject, QEventLoop, Qt, pyqtSignal, pyqtSlot
from packages.qt_compat.QtGui import QColor, QImage
from packages.qt_compat.QtWidgets import (
    QColorDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSlider, QSpinBox, QToolButton, QVBoxLayout,
)

from app.dialogs import show_warning
from styles.theme import is_dark


def _place_near_parent(parent, width: int, height: int, *, dx: int = 24, dy: int = 80):
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
    font_changed = pyqtSignal(int, str, bool, bool)   # size, hex color, bold, underline
    rotation_changed = pyqtSignal(int)

    def __init__(self, parent=None, *, mode: str = "text"):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._color = QColor(0, 0, 0)
        self._mode  = mode
        self.setFrameShape(QFrame.Shape.StyledPanel)
        dark = is_dark()
        self._panel_dark = dark
        if dark:
            self.setStyleSheet(
                "QFrame { background:#1A1E30; border:1.5px solid #2A5090; border-radius:8px; }"
                "QLabel { color:#B0C8F0; font-size:12px; background:transparent; border:none; padding:0; }"
                "QSpinBox { background:#10121C; color:#D8E8FF; border:1px solid #304080; "
                "           border-radius:4px; padding:2px 6px; }"
                "QPushButton { border-radius:5px; padding:5px 14px; font-size:12px; font-weight:600; }"
            )
        else:
            self.setStyleSheet(
                "QFrame { background:#F8FAFC; border:1.5px solid #CBD5E1; border-radius:8px; }"
                "QLabel { color:#334155; font-size:12px; background:transparent; border:none; padding:0; }"
                "QSpinBox { background:#FFFFFF; color:#0F172A; border:1px solid #CBD5E1; "
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
            ("color:#7AAAE8;" if self._panel_dark else "color:#1D4ED8;")
            + " font-size:11px; font-weight:700; background:transparent; border:none;"
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

            if self._panel_dark:
                _fmt_ss = (
                    "QToolButton{background:#10121C;color:#D8E8FF;border:1px solid #304080;"
                    "border-radius:4px;font-size:13px;font-weight:700;}"
                    "QToolButton:checked{background:#2A4080;border-color:#6080C0;color:#FFFFFF;}"
                    "QToolButton:hover{border-color:#4060A0;}"
                )
            else:
                _fmt_ss = (
                    "QToolButton{background:#FFFFFF;color:#0F172A;border:1px solid #CBD5E1;"
                    "border-radius:4px;font-size:13px;font-weight:700;}"
                    "QToolButton:checked{background:#DBEAFE;border-color:#2563EB;color:#1D4ED8;}"
                    "QToolButton:hover{border-color:#2563EB;}"
                )
            self._bold_btn = QToolButton()
            self._bold_btn.setText("B")
            self._bold_btn.setCheckable(True)
            self._bold_btn.setFixedSize(30, 26)
            self._bold_btn.setStyleSheet(_fmt_ss)
            self._bold_btn.toggled.connect(lambda _: self._emit_font())
            row.addWidget(self._bold_btn)

            self._under_btn = QToolButton()
            self._under_btn.setText("U")
            self._under_btn.setCheckable(True)
            self._under_btn.setFixedSize(30, 26)
            self._under_btn.setStyleSheet(
                _fmt_ss.replace("font-weight:700", "font-weight:400")
            )
            self._under_btn.toggled.connect(lambda _: self._emit_font())
            row.addWidget(self._under_btn)

            root.addLayout(row)
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(QLabel("Xoay:"))
        self._rotation_slider = QSlider(Qt.Orientation.Horizontal)
        self._rotation_slider.setRange(-180, 180)
        self._rotation_slider.setSingleStep(1)
        self._rotation_slider.setPageStep(15)
        self._rotation_slider.setValue(0)
        self._rotation_slider.setFixedWidth(160)
        row.addWidget(self._rotation_slider)
        self._rotation_spin = QSpinBox()
        self._rotation_spin.setRange(-180, 180)
        self._rotation_spin.setSingleStep(1)
        self._rotation_spin.setSuffix("°")
        self._rotation_spin.setFixedWidth(72)
        row.addWidget(self._rotation_spin)
        row.addStretch()
        root.addLayout(row)

        def _set_rotation(value: int):
            if hasattr(self, "_rotation_slider") and self._rotation_slider.value() != value:
                self._rotation_slider.blockSignals(True)
                self._rotation_slider.setValue(value)
                self._rotation_slider.blockSignals(False)
            if hasattr(self, "_rotation_spin") and self._rotation_spin.value() != value:
                self._rotation_spin.blockSignals(True)
                self._rotation_spin.setValue(value)
                self._rotation_spin.blockSignals(False)
            self.rotation_changed.emit(value)

        self._rotation_slider.valueChanged.connect(_set_rotation)
        self._rotation_spin.valueChanged.connect(_set_rotation)

        hint = (
            QLabel("Gõ trực tiếp trên PDF  ·  Ctrl+Enter để chèn  ·  Esc để hủy")
            if self._mode == "text"
            else QLabel("Kéo di chuyển  ·  Kéo góc resize  ·  Enter xác nhận  ·  Esc hủy")
        )

        hint.setStyleSheet(
            ("color:#7C8DB8;" if self._panel_dark else "color:#64748B;")
            + " font-size:10px; background:transparent; border:none;"
        )
        root.addWidget(hint)

        row2 = QHBoxLayout(); row2.setSpacing(8); row2.addStretch()
        btn_cancel = QPushButton("Hủy")
        if self._panel_dark:
            btn_cancel.setStyleSheet(
                "QPushButton{background-color:transparent;color:#FF6655;border:1.5px solid #FF6655;}"
                "QPushButton:hover{background-color:#3A1010;}"
            )
        else:
            btn_cancel.setStyleSheet(
                "QPushButton{background-color:#FFFFFF;color:#B91C1C;border:1.5px solid #FCA5A5;}"
                "QPushButton:hover{background-color:#FEE2E2;}"
            )
        btn_cancel.clicked.connect(self.cancelled)
        row2.addWidget(btn_cancel)

        ok_lbl = "Chèn vào PDF" if self._mode == "text" else "Đặt ảnh vào PDF"
        btn_ok = QPushButton(ok_lbl)
        if self._panel_dark:
            btn_ok.setStyleSheet(
                "QPushButton{background-color:#FF6600;color:white;border:none;}"
                "QPushButton:hover{background-color:#FF9900;}"
            )
        else:
            btn_ok.setStyleSheet(
                "QPushButton{background-color:#2563EB;color:white;border:none;}"
                "QPushButton:hover{background-color:#1D4ED8;}"
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
            f"background-color:{c.name()};color:{txt};border:1px solid #555555;"
            "border-radius:4px;font-size:11px;"
        )
        self._color_btn.setText("Màu chữ")

    def _emit_font(self):
        if hasattr(self, "_size_spin"):
            bold  = self._bold_btn.isChecked()  if hasattr(self, "_bold_btn")  else False
            under = self._under_btn.isChecked() if hasattr(self, "_under_btn") else False
            self.font_changed.emit(self._size_spin.value(), self._color.name(), bold, under)

    def get_font_size(self) -> int:
        return self._size_spin.value() if hasattr(self, "_size_spin") else 14

    def get_bold(self) -> bool:
        return self._bold_btn.isChecked() if hasattr(self, "_bold_btn") else False

    def get_underline(self) -> bool:
        return self._under_btn.isChecked() if hasattr(self, "_under_btn") else False

    def set_font_state(self, font_size: int, color_hex: str,
                       bold: bool = False, underline: bool = False):
        """Pre-set font controls when editing existing text."""
        if hasattr(self, "_size_spin"):
            self._size_spin.setValue(font_size)
        c = QColor(color_hex)
        if c.isValid():
            self._color = c
            self._refresh_color_btn()
        if hasattr(self, "_bold_btn"):
            self._bold_btn.setChecked(bold)
        if hasattr(self, "_under_btn"):
            self._under_btn.setChecked(underline)

    def get_color_tuple(self) -> tuple:
        c = self._color
        return (c.redF(), c.greenF(), c.blueF())

    def get_rotation(self) -> int:
        return self._rotation_spin.value() if hasattr(self, "_rotation_spin") else 0

    def set_rotation(self, value: int):
        if hasattr(self, "_rotation_spin"):
            self._rotation_spin.setValue(int(value))

    def position_near(self, window):
        self.adjustSize()
        x, y = _place_near_parent(window, self.width(), self.height(), dx=24, dy=80)
        self.move(x, y)


# ── JavaScript: inline text overlay ──────────────────────────────────────────
# Always re-injects fresh: clears old state and uses the shared bridge helper.
# Does NOT remove overlay on commit — page reload naturally clears it (no flash).

# Inline text/image JS loaded from external files.
from app.js_loader import load_js as _load_js
INLINE_TEXT_JS = _load_js("inline_text_bridge.js")
INLINE_IMAGE_JS = _load_js("inline_image_bridge.js")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_web_view(window):
    getter = getattr(window, "_get_webview", None)
    return getter() if callable(getter) else None


def _setup_webchannel(web_view, parent, name, bridge):
    from app.webchannel import register_webchannel_object

    return register_webchannel_object(web_view, parent, name, bridge)


def _teardown_webchannel(web_view):
    if web_view is None:
        return
    try:
        from app.webchannel import unregister_webchannel_object

        unregister_webchannel_object(web_view)
    except RuntimeError:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def run_inline_text(window, prefill: dict | None = None) -> dict | None:
    """Inline text editor on PDF canvas.
    Returns {page_number, box, text, font_size, color_tuple, bold, underline} or None.
    Pass prefill={text, font_size, color_hex, bold, underline} to pre-fill the editor."""
    web_view = _get_web_view(window)
    if web_view is None:
        return None

    bridge = InlineTextBridge(window)
    _setup_webchannel(web_view, window, "inlineTextBridge", bridge)

    panel  = InlineEditPanel(window, mode="text")
    if prefill:
        panel.set_font_state(
            prefill.get("font_size", 14),
            prefill.get("color_hex", "#000000"),
            prefill.get("bold", False),
            prefill.get("underline", False),
        )
        if "rotation" in prefill:
            panel.set_rotation(prefill.get("rotation", 0))
    panel.position_near(window)
    result: dict = {}
    loop   = QEventLoop(window)

    # Panel font controls → update JS textarea styling live
    def _on_font(size, hex_color, bold, underline):
        b = "true" if bold else "false"
        u = "true" if underline else "false"
        web_view.page().runJavaScript(
            f"typeof window.__3TTextUpdateFont === 'function' && "
            f"window.__3TTextUpdateFont({size}, '{hex_color}', {b}, {u});"
        )
    panel.font_changed.connect(_on_font)

    def _on_rotation(angle):
        web_view.page().runJavaScript(
            f"typeof window.__3TTextUpdateRotation === 'function' && "
            f"window.__3TTextUpdateRotation({int(angle)});"
        )
    panel.rotation_changed.connect(_on_rotation)

    # Panel "Chèn" → capture font settings then trigger JS commit
    def _on_commit():
        result["font_size"]   = panel.get_font_size()
        result["color_tuple"] = panel.get_color_tuple()
        result["bold"]        = panel.get_bold()
        result["underline"]   = panel.get_underline()
        result["rotation"]    = panel.get_rotation()
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
                "bold":         result.get("bold", panel.get_bold()),
                "underline":    result.get("underline", panel.get_underline()),
                "rotation":     result.get("rotation", panel.get_rotation()),
            })
        if loop.isRunning(): loop.quit()

    def _cancelled():
        result.clear()
        if loop.isRunning(): loop.quit()

    def _ready(page):
        panel.show(); panel.raise_(); panel.activateWindow()
        _on_rotation(panel.get_rotation())

    bridge.ready.connect(_ready)
    bridge.confirmed.connect(_confirmed)
    bridge.cancelled.connect(_cancelled)

    if hasattr(window, "status"):
        window.status.showMessage(
            "Click vào vị trí trên PDF để đặt text box  ·  Esc hủy", 0
        )
    try:
        if prefill:
            import json as _json
            pf_js = _json.dumps({
                "text":      prefill.get("text", ""),
                "font_size": prefill.get("font_size", 14),
                "color_hex": prefill.get("color_hex", "#000000"),
                "bold":      bool(prefill.get("bold", False)),
                "underline": bool(prefill.get("underline", False)),
                "rotation":  int(prefill.get("rotation", 0)),
            })
            web_view.page().runJavaScript(f"window.__3TTextPrefill = {pf_js};")
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
        image = QImage.fromData(raw)
        if image.isNull():
            show_warning(window, "Không đọc được ảnh", "Không thể mở file ảnh đã chọn. Vui lòng chọn file khác.")
            return None
        image_info = {
            "width": int(image.width()),
            "height": int(image.height()),
            "mime": mime,
            "has_alpha": bool(image.hasAlphaChannel()),
        }
        data_url = f"data:image/{mime};base64,{base64.b64encode(raw).decode()}"
    except Exception:
        show_warning(window, "Không đọc được ảnh", "Không thể mở file ảnh đã chọn. Vui lòng chọn file khác.")
        return None

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

    def _on_rotation(angle):
        web_view.page().runJavaScript(
            f"typeof window.__3TImgUpdateRotation === 'function' && "
            f"window.__3TImgUpdateRotation({int(angle)});"
        )
    panel.rotation_changed.connect(_on_rotation)

    def _confirmed(page, l, b, r, t):
        result.update({
            "page_number": max(1, int(page)),
            "box": (l, b, r, t),
            "rotation": panel.get_rotation(),
        })
        if loop.isRunning(): loop.quit()

    def _cancelled():
        result.clear()
        if loop.isRunning(): loop.quit()

    def _ready(page):
        panel.show(); panel.raise_(); panel.activateWindow()
        _on_rotation(panel.get_rotation())

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
        web_view.page().runJavaScript(f"window.__3TInlineImageInfo = {repr(image_info)};")
        web_view.page().runJavaScript(INLINE_IMAGE_JS)
        loop.exec()
    finally:
        panel.close()
        _teardown_webchannel(web_view)
        if hasattr(window, "status"):
            window.status.showMessage("", 0)

    return result if result.get("box") else None
