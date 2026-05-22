"""Ribbon bar — thanh công cụ dạng tab kiểu Word/Excel."""
from __future__ import annotations

from packages.qt_compat.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QToolButton, QSizePolicy,
)
from packages.qt_compat.QtCore import Qt, QSize, Signal
from packages.qt_compat.QtGui import QAction


def _make_styles(dark: bool) -> dict:
    """Trả về dict stylesheet cho dark hoặc light mode."""
    if dark:
        bg_tabbar  = "#12122A"
        bg_panel   = "#1C1C36"
        border     = "#2A2A4A"
        tab_normal = "#7070A8"
        tab_sel_fg = "#E8F0FF"
        tab_acc    = "#5B6CF6"
        btn_fg     = "#C0C8E8"
        btn_hover  = "#252548"
        btn_chk    = "#252558"
        btn_chk_bd = "#5B6CF6"
        grp_lbl    = "#4A4A88"
        tab_hover_bg = "#18183A"
        sep        = "#2A2A4A"
    else:
        bg_tabbar  = "#E8E8F4"
        bg_panel   = "#F2F2FA"
        border     = "#C8C8DC"
        tab_normal = "#5050A0"
        tab_sel_fg = "#1A1A3A"
        tab_acc    = "#5B6CF6"
        btn_fg     = "#303060"
        btn_hover  = "#DCDCF0"
        btn_chk    = "#CDCDF0"
        btn_chk_bd = "#5B6CF6"
        grp_lbl    = "#8080B0"
        tab_hover_bg = "#DCDCF0"
        sep        = "#C8C8DC"

    tabrow = f"background:{bg_tabbar};border-bottom:1px solid {border};"

    tab_normal_ss = f"""
QToolButton {{
    background: transparent;
    color: {tab_normal};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 5px 16px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 0;
}}
QToolButton:hover {{ color: {tab_sel_fg}; background: {tab_hover_bg}; }}
"""

    tab_sel_ss = f"""
QToolButton {{
    background: {bg_panel};
    color: {tab_sel_fg};
    border: none;
    border-bottom: 2px solid {tab_acc};
    padding: 5px 16px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 0;
}}
"""

    panel_ss = f"""
QWidget#rib_panel {{
    background: {bg_panel};
    border-bottom: 1px solid {border};
}}
"""

    toolbtn_ss = f"""
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px 6px;
    color: {btn_fg};
    font-size: 10px;
    min-width: 40px;
    max-width: 72px;
}}
QToolButton:hover {{
    background: {btn_hover};
    border-color: {border};
    color: {tab_sel_fg};
}}
QToolButton:pressed, QToolButton:checked {{
    background: {btn_chk};
    border-color: {btn_chk_bd};
    color: {tab_sel_fg};
}}
QToolButton:disabled {{
    color: {grp_lbl};
}}
"""

    collapse_ss = f"""
QToolButton {{
    background: transparent;
    border: none;
    color: {tab_normal};
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 4px;
}}
QToolButton:hover {{ color: {tab_sel_fg}; background: {tab_hover_bg}; }}
"""

    sep_ss  = f"background:{sep};"
    grp_ss  = f"color:{grp_lbl};font-size:9px;font-weight:700;letter-spacing:0.5px;"

    return dict(
        tabrow=tabrow,
        tab_normal=tab_normal_ss,
        tab_sel=tab_sel_ss,
        panel=panel_ss,
        toolbtn=toolbtn_ss,
        collapse=collapse_ss,
        sep=sep_ss,
        grp=grp_ss,
        bg_panel=bg_panel,
        sep_color=sep,
    )


# Styles mặc định (dark) — dùng lúc tạo widget trước khi set_theme được gọi
_S = _make_styles(dark=True)


def make_ribbon_btn(icon, label: str, tooltip: str,
                    callback=None, checkable: bool = False,
                    icon_size: int = 28) -> QToolButton:
    btn = QToolButton()
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setStyleSheet(_S["toolbtn"])
    if icon:
        btn.setIcon(icon)
    btn.setText(label)
    btn.setToolTip(tooltip)
    btn.setStatusTip(tooltip)
    if checkable:
        btn.setCheckable(True)
    if callback:
        btn.clicked.connect(callback)
    return btn


def make_action_btn(action: QAction, label: str = "",
                    icon_size: int = 28) -> QToolButton:
    btn = QToolButton()
    btn.setDefaultAction(action)
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setStyleSheet(_S["toolbtn"])
    if label:
        action.setText(label)
    return btn


# ── RibbonGroup ───────────────────────────────────────────────────────────────

class RibbonGroup(QWidget):
    def __init__(self, group_label: str = "", parent=None):
        super().__init__(parent)
        self._buttons: list[QToolButton] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 2)
        outer.setSpacing(1)

        self._btn_row = QHBoxLayout()
        self._btn_row.setSpacing(3)
        self._btn_row.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        outer.addLayout(self._btn_row, 1)

        self._lbl = None
        if group_label:
            self._lbl = QLabel(group_label.upper())
            self._lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self._lbl.setStyleSheet(_S["grp"])
            outer.addWidget(self._lbl)

    def add(self, widget: QWidget):
        self._btn_row.addWidget(widget)
        if isinstance(widget, QToolButton):
            self._buttons.append(widget)

    def add_widget(self, w: QWidget):
        self.add(w)

    def apply_theme(self, styles: dict):
        for btn in self._buttons:
            btn.setStyleSheet(styles["toolbtn"])
        if self._lbl:
            self._lbl.setStyleSheet(styles["grp"])


# ── RibbonPanel ───────────────────────────────────────────────────────────────

class RibbonPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rib_panel")
        self.setStyleSheet(_S["panel"])
        self._groups: list[RibbonGroup] = []
        self._seps: list[QFrame] = []

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 0, 6, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

    def add_group(self, group: RibbonGroup, add_sep: bool = True):
        self._layout.addWidget(group)
        self._groups.append(group)
        if add_sep:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFixedWidth(1)
            sep.setStyleSheet(_S["sep"])
            self._seps.append(sep)
            self._layout.addWidget(sep)

    def add_widget(self, w: QWidget):
        self._layout.addWidget(w)

    def add_stretch(self):
        self._layout.addStretch()

    def apply_theme(self, styles: dict):
        self.setStyleSheet(styles["panel"])
        for g in self._groups:
            g.apply_theme(styles)
        for sep in self._seps:
            sep.setStyleSheet(styles["sep"])


# ── RibbonBar ─────────────────────────────────────────────────────────────────

class RibbonBar(QWidget):
    tab_changed = Signal(int)
    PANEL_H = 72

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._collapsed = False
        self._current_tab = -1
        self._tabs: list[QToolButton] = []
        self._panels: list[RibbonPanel] = []
        self._tab_ss_normal: list[str] = []
        self._tab_ss_sel: list[str] = []
        self._styles = _S

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Hàng tab
        self._tabrow = QWidget()
        self._tabrow.setFixedHeight(32)
        self._tabrow.setStyleSheet(_S["tabrow"])
        tab_layout = QHBoxLayout(self._tabrow)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        self._brand = QLabel(
            "<b style='color:#4A7AE0;font-size:13px;'>3T</b>"
            "<span style='color:#FF6820;font-size:13px;font-weight:700;'>Reader</span>"
        )
        self._brand.setStyleSheet(
            f"padding:0 12px;background:transparent;font-weight:700;letter-spacing:0.5px;"
        )
        tab_layout.addWidget(self._brand)

        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setFixedHeight(16)
        vsep.setFixedWidth(1)
        vsep.setStyleSheet(_S["sep"])
        self._brand_sep = vsep
        tab_layout.addWidget(vsep)

        self._tab_btn_container = QHBoxLayout()
        self._tab_btn_container.setContentsMargins(0, 0, 0, 0)
        self._tab_btn_container.setSpacing(0)
        tab_layout.addLayout(self._tab_btn_container)
        tab_layout.addStretch()

        self._collapse_btn = QToolButton()
        self._collapse_btn.setText("∧")
        self._collapse_btn.setToolTip("Thu gọn / Mở rộng ribbon")
        self._collapse_btn.setStyleSheet(_S["collapse"])
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        tab_layout.addWidget(self._collapse_btn)

        root.addWidget(self._tabrow)

        self._panel_container = QWidget()
        self._panel_container.setObjectName("rib_panel")
        self._panel_container.setStyleSheet(_S["panel"])
        self._panel_container.setFixedHeight(self.PANEL_H)

        pc_layout = QHBoxLayout(self._panel_container)
        pc_layout.setContentsMargins(0, 0, 0, 0)
        pc_layout.setSpacing(0)
        self._pc_layout = pc_layout

        root.addWidget(self._panel_container)

    # ── Public API ────────────────────────────────────────────────────────

    def add_tab(self, label: str, panel: RibbonPanel) -> int:
        idx = len(self._tabs)
        self._panels.append(panel)

        btn = QToolButton()
        btn.setText(label)
        btn.setCheckable(False)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setFixedHeight(30)
        btn.setProperty("sel", "0")
        btn.clicked.connect(lambda _checked=False, i=idx: self._select_tab(i))
        self._tabs.append(btn)
        self._tab_btn_container.addWidget(btn)

        panel.setParent(self._panel_container)
        self._pc_layout.addWidget(panel)
        panel.setVisible(False)

        if idx == 0:
            self._select_tab(0)

        return idx

    def select_tab(self, idx: int):
        self._select_tab(idx)

    @property
    def current_tab(self) -> int:
        return self._current_tab

    def set_theme(self, dark: bool):
        """Cập nhật toàn bộ màu ribbon theo theme sáng/tối."""
        self._styles = _make_styles(dark)
        s = self._styles

        self._tabrow.setStyleSheet(s["tabrow"])
        self._brand_sep.setStyleSheet(s["sep"])
        self._collapse_btn.setStyleSheet(s["collapse"])
        self._panel_container.setStyleSheet(s["panel"])

        for i, (btn, panel) in enumerate(zip(self._tabs, self._panels)):
            selected = (i == self._current_tab)
            btn.setStyleSheet(s["tab_sel"] if selected else s["tab_normal"])
            panel.apply_theme(s)

    # ── Internal ──────────────────────────────────────────────────────────

    def _select_tab(self, idx: int):
        if idx == self._current_tab and not self._collapsed:
            return
        if self._collapsed:
            self._collapsed = False
            self._panel_container.setVisible(True)
            self._collapse_btn.setText("∧")

        s = self._styles
        for i, (btn, panel) in enumerate(zip(self._tabs, self._panels)):
            selected = (i == idx)
            btn.setStyleSheet(s["tab_sel"] if selected else s["tab_normal"])
            panel.setVisible(selected)
        self._current_tab = idx
        self.tab_changed.emit(idx)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._panel_container.setVisible(not self._collapsed)
        self._collapse_btn.setText("∨" if self._collapsed else "∧")
