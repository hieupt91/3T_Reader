"""Ribbon bar — thanh công cụ dạng tab kiểu Word/Excel."""
from __future__ import annotations

from packages.qt_compat.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QToolButton, QSizePolicy, QSpacerItem,
)
from packages.qt_compat.QtCore import Qt, QSize, Signal
from packages.qt_compat.QtGui import QFont, QAction

# ── Màu sắc ──────────────────────────────────────────────────────────────────
_BG_TABBAR   = "#12122A"
_BG_PANEL    = "#1C1C36"
_BG_PANEL2   = "#16163A"
_BORDER      = "#2A2A4A"
_TAB_NORMAL  = "#7070A8"
_TAB_SEL_FG  = "#E8F0FF"
_TAB_SEL_ACC = "#5B6CF6"
_BTN_FG      = "#C0C8E8"
_BTN_HOVER   = "#252548"
_BTN_PRESS   = "#1A1A40"
_BTN_CHK     = "#252558"
_BTN_CHK_BDR = "#5B6CF6"
_GRP_LBL     = "#4A4A88"

# ── Stylesheet ────────────────────────────────────────────────────────────────
_TABROW_SS = f"background:{_BG_TABBAR};border-bottom:1px solid {_BORDER};"

_TABbtn_SS = f"""
QToolButton {{
    background: transparent;
    color: {_TAB_NORMAL};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 5px 16px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 0;
}}
QToolButton:hover {{ color: #B0B8E8; background: #18183A; }}
QToolButton[sel="1"] {{
    color: {_TAB_SEL_FG};
    border-bottom: 2px solid {_TAB_SEL_ACC};
    background: {_BG_PANEL};
}}
"""

_PANEL_SS = f"""
QWidget#rib_panel {{
    background: {_BG_PANEL};
    border-bottom: 1px solid {_BORDER};
}}
"""

_TOOLBTN_SS = f"""
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px 6px;
    color: {_BTN_FG};
    font-size: 10px;
    min-width: 40px;
    max-width: 72px;
}}
QToolButton:hover {{
    background: {_BTN_HOVER};
    border-color: #3C3C68;
    color: #E0E8FF;
}}
QToolButton:pressed, QToolButton:checked {{
    background: {_BTN_CHK};
    border-color: {_BTN_CHK_BDR};
    color: #E8F0FF;
}}
QToolButton:disabled {{
    color: #3A3A60;
}}
"""

_COLLAPSE_BTN_SS = f"""
QToolButton {{
    background: transparent;
    border: none;
    color: {_TAB_NORMAL};
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 4px;
}}
QToolButton:hover {{ color: #B0B8E8; background: #18183A; }}
"""

_SEP_SS = f"background:{_BORDER};"
_GRP_LBL_SS = f"color:{_GRP_LBL};font-size:9px;font-weight:700;letter-spacing:0.5px;"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _vsep(h: int = 40) -> QFrame:
    """Đường phân cách dọc."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setFixedWidth(1)
    f.setFixedHeight(h)
    f.setStyleSheet(_SEP_SS)
    return f


def make_ribbon_btn(icon, label: str, tooltip: str,
                    callback=None, checkable: bool = False,
                    icon_size: int = 28) -> QToolButton:
    """Tạo QToolButton cho ribbon (icon lớn + text nhỏ bên dưới)."""
    btn = QToolButton()
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setStyleSheet(_TOOLBTN_SS)
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
    """Bọc QAction thành QToolButton có icon lớn + text nhỏ."""
    btn = QToolButton()
    btn.setDefaultAction(action)
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setStyleSheet(_TOOLBTN_SS)
    if label:
        action.setText(label)
    return btn


# ── RibbonGroup: nhóm button trong 1 tab ─────────────────────────────────────

class RibbonGroup(QWidget):
    """Nhóm buttons với nhãn ở dưới (như Office ribbon group)."""

    def __init__(self, group_label: str = "", parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 2)
        outer.setSpacing(1)

        self._btn_row = QHBoxLayout()
        self._btn_row.setSpacing(3)
        self._btn_row.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        outer.addLayout(self._btn_row, 1)

        if group_label:
            lbl = QLabel(group_label.upper())
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lbl.setStyleSheet(_GRP_LBL_SS)
            outer.addWidget(lbl)

    def add(self, widget: QWidget):
        self._btn_row.addWidget(widget)

    def add_widget(self, w: QWidget):
        self._btn_row.addWidget(w)


# ── RibbonPanel: nội dung 1 tab ──────────────────────────────────────────────

class RibbonPanel(QWidget):
    """Panel (1 tab) trong ribbon chứa các nhóm button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rib_panel")
        self.setStyleSheet(_PANEL_SS)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 0, 6, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

    def add_group(self, group: RibbonGroup, add_sep: bool = True):
        self._layout.addWidget(group)
        if add_sep:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFixedWidth(1)
            sep.setStyleSheet(_SEP_SS)
            self._layout.addWidget(sep)

    def add_widget(self, w: QWidget):
        self._layout.addWidget(w)

    def add_stretch(self):
        self._layout.addStretch()


# ── RibbonBar: widget chính ───────────────────────────────────────────────────

class RibbonBar(QWidget):
    """Ribbon bar kiểu Word/Excel — tab phía trên, tool panel phía dưới.

    Có thể thu gọn bằng nút ^ ở góc phải (chỉ hiện tab labels, ẩn panel).
    """

    tab_changed = Signal(int)

    # Panel height khi mở rộng
    PANEL_H = 72

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._collapsed = False
        self._current_tab = -1
        self._tabs: list[QToolButton] = []
        self._panels: list[RibbonPanel] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Hàng tab ─────────────────────────────────────────────────────
        self._tabrow = QWidget()
        self._tabrow.setFixedHeight(32)
        self._tabrow.setStyleSheet(_TABROW_SS)
        tab_layout = QHBoxLayout(self._tabrow)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        # Brand
        self._brand = QLabel(
            "<b style='color:#4A7AE0;font-size:13px;'>3T</b>"
            "<span style='color:#FF6820;font-size:13px;font-weight:700;'>Reader</span>"
        )
        self._brand.setStyleSheet(
            f"padding:0 12px;background:{_BG_TABBAR};"
            "font-weight:700;letter-spacing:0.5px;"
        )
        tab_layout.addWidget(self._brand)

        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setFixedHeight(16)
        vsep.setFixedWidth(1)
        vsep.setStyleSheet(_SEP_SS)
        tab_layout.addWidget(vsep)

        # Container cho các tab buttons
        self._tab_btn_container = QHBoxLayout()
        self._tab_btn_container.setContentsMargins(0, 0, 0, 0)
        self._tab_btn_container.setSpacing(0)
        tab_layout.addLayout(self._tab_btn_container)
        tab_layout.addStretch()

        # Nút thu/mở ribbon ∧/∨
        self._collapse_btn = QToolButton()
        self._collapse_btn.setText("∧")
        self._collapse_btn.setToolTip("Thu gọn / Mở rộng ribbon")
        self._collapse_btn.setStyleSheet(_COLLAPSE_BTN_SS)
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        tab_layout.addWidget(self._collapse_btn)

        root.addWidget(self._tabrow)

        # ── Panel container ───────────────────────────────────────────────
        self._panel_container = QWidget()
        self._panel_container.setObjectName("rib_panel")
        self._panel_container.setStyleSheet(_PANEL_SS)
        self._panel_container.setFixedHeight(self.PANEL_H)

        pc_layout = QHBoxLayout(self._panel_container)
        pc_layout.setContentsMargins(0, 0, 0, 0)
        pc_layout.setSpacing(0)
        self._pc_layout = pc_layout

        root.addWidget(self._panel_container)

    # ── Public API ────────────────────────────────────────────────────────

    def add_tab(self, label: str, panel: RibbonPanel) -> int:
        """Thêm 1 tab mới. Trả về index của tab."""
        idx = len(self._tabs)
        self._panels.append(panel)

        btn = QToolButton()
        btn.setText(label)
        btn.setCheckable(False)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setStyleSheet(_TABBN_SS := _TABBT_SS_NORMAL)
        btn.setFixedHeight(30)
        btn.setProperty("sel", "0")
        btn.clicked.connect(lambda _checked=False, i=idx: self._select_tab(i))
        self._tabs.append(btn)
        self._tab_btn_container.addWidget(btn)

        # Thêm panel vào container (ẩn trừ tab đầu)
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

    # ── Internal ──────────────────────────────────────────────────────────

    def _select_tab(self, idx: int):
        if idx == self._current_tab and not self._collapsed:
            return
        # Expand nếu đang thu gọn
        if self._collapsed:
            self._collapsed = False
            self._panel_container.setVisible(True)
            self._collapse_btn.setText("∧")

        for i, (btn, panel) in enumerate(zip(self._tabs, self._panels)):
            selected = (i == idx)
            btn.setProperty("sel", "1" if selected else "0")
            btn.setStyleSheet(_TABBN_SS := (_TABBT_SS_SEL if selected else _TABBT_SS_NORMAL))
            panel.setVisible(selected)
        self._current_tab = idx
        self.tab_changed.emit(idx)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._panel_container.setVisible(not self._collapsed)
        self._collapse_btn.setText("∨" if self._collapsed else "∧")


# Stylesheet variations for tab buttons (outside class to avoid redefine)
_TABBT_SS_NORMAL = f"""
QToolButton {{
    background: transparent;
    color: {_TAB_NORMAL};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 5px 16px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 0;
}}
QToolButton:hover {{ color: #B0B8E8; background: #18183A; }}
"""

_TABBT_SS_SEL = f"""
QToolButton {{
    background: {_BG_PANEL};
    color: {_TAB_SEL_FG};
    border: none;
    border-bottom: 2px solid {_TAB_SEL_ACC};
    padding: 5px 16px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 0;
}}
"""
