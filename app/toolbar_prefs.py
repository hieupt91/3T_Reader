"""Toolbar customization — cho phép người dùng ghim / ẩn từng nhóm công cụ."""
from __future__ import annotations

from packages.qt_compat.QtCore import QSettings
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame, QScrollArea, QWidget,
)

# (group_id, display_name, icon_char, action_attrs)
TOOLBAR_GROUPS: list[tuple[str, str, str, list[str]]] = [
    ("file",  "File & Lưu",       "📁", ["act_open", "act_recent", "act_save", "act_print"]),
    ("nav",   "Điều hướng trang", "◀▶", ["act_prev", "act_next"]),
    ("zoom",  "Zoom",             "🔍", ["act_zoom_in", "act_zoom_out", "act_fit"]),
    ("edit",  "Chỉnh sửa PDF",   "✏️",  ["act_highlight", "act_insert_text", "act_insert_image",
                                          "act_draw", "act_redact", "act_delete_object", "act_undo"]),
    ("view",  "Giao diện",        "🎨", ["act_theme_toggle", "act_fullscreen"]),
]

_SETTINGS_KEY = "3TReader/toolbar"


def load_prefs() -> dict[str, bool]:
    s = QSettings()
    prefs: dict[str, bool] = {}
    for gid, *_ in TOOLBAR_GROUPS:
        prefs[gid] = bool(s.value(f"{_SETTINGS_KEY}/{gid}", True))
    return prefs


def save_prefs(prefs: dict[str, bool]) -> None:
    s = QSettings()
    for gid, visible in prefs.items():
        s.setValue(f"{_SETTINGS_KEY}/{gid}", visible)
    s.sync()


def apply_prefs(window, prefs: dict[str, bool]) -> None:
    """Ẩn/hiện toolbar widget (không ảnh hưởng menu)."""
    toolbar = window.toolbar
    for gid, _name, _icon, attrs in TOOLBAR_GROUPS:
        visible = prefs.get(gid, True)
        for attr in attrs:
            action = getattr(window, attr, None)
            if action is None:
                continue
            widget = toolbar.widgetForAction(action)
            if widget:
                widget.setVisible(visible)

    # Ẩn/hiện page_spin, total_label theo group nav
    nav_vis = prefs.get("nav", True)
    for w in (getattr(window, "page_spin", None), getattr(window, "total_label", None)):
        if w is not None:
            w.setVisible(nav_vis)

    # Ẩn/hiện zoom_spin theo group zoom
    zoom_vis = prefs.get("zoom", True)
    spin = getattr(window, "zoom_spin", None)
    if spin is not None:
        spin.setVisible(zoom_vis)


class ToolbarCustomizeDialog(QDialog):
    """Dialog tuỳ chỉnh thanh công cụ: ghim / tắt từng nhóm."""

    def __init__(self, parent, current_prefs: dict[str, bool]):
        super().__init__(parent)
        self.setWindowTitle("Tuỳ chỉnh thanh công cụ")
        self.setModal(True)
        self.setMinimumWidth(380)
        self._prefs = dict(current_prefs)
        self._checks: dict[str, QCheckBox] = {}
        self._setup_ui()
        self.adjustSize()

    def _setup_ui(self):
        root = QVBoxLayout(self)

        header = QLabel("Chọn nhóm công cụ muốn hiển thị trên thanh toolbar:")
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: bold; margin-bottom: 4px;")
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        vbox = QVBoxLayout(inner)
        vbox.setSpacing(6)

        for gid, name, icon, _ in TOOLBAR_GROUPS:
            pinned = self._prefs.get(gid, True)
            cb = QCheckBox(f"{icon}  {name}")
            cb.setChecked(pinned)
            cb.toggled.connect(lambda checked, g=gid: self._on_toggle(g, checked))
            self._checks[gid] = cb
            vbox.addWidget(cb)

        vbox.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #555;")
        root.addWidget(sep)

        # Buttons
        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Khôi phục mặc định")
        btn_reset.clicked.connect(self._reset)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Áp dụng")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    def _on_toggle(self, gid: str, checked: bool):
        self._prefs[gid] = checked

    def _reset(self):
        for gid in self._prefs:
            self._prefs[gid] = True
        for gid, cb in self._checks.items():
            cb.setChecked(True)

    def get_prefs(self) -> dict[str, bool]:
        # Sync checkboxes to prefs (checkboxes are the ground truth)
        for gid, cb in self._checks.items():
            self._prefs[gid] = cb.isChecked()
        return dict(self._prefs)
