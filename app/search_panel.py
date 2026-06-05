from packages.qt_compat.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QToolButton

from app.actions.document import execute_search
from app.icon_utils import svg_icon


class SearchPanel(QFrame):
    def __init__(self, window):
        super().__init__(window.tab_widget)
        self.window = window
        self.setObjectName("SearchPanel")
        self.setVisible(False)
        self._build()

    def _build(self):
        window = self.window
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        title = QLabel("Tìm")
        title.setObjectName("SearchTitle")
        row.addWidget(title)

        window.search_input = QLineEdit()
        window.search_input.setObjectName("SearchInput")
        window.search_input.setPlaceholderText("Nhập từ khóa, Enter để tìm")
        window.search_input.returnPressed.connect(
            lambda: search_from_panel(window, find_previous=False, force_new=False)
        )
        row.addWidget(window.search_input, 1)

        window.btn_search_prev = QToolButton()
        window.btn_search_prev.setObjectName("SearchBtn")
        window.btn_search_prev.setToolTip("Tìm trước đó (Shift+F3)")
        window.btn_search_prev.setIcon(svg_icon("chevron_left.svg", size=16, color=window._search_arrow_color()))
        window.btn_search_prev.clicked.connect(
            lambda: search_from_panel(window, find_previous=True, force_new=False)
        )
        row.addWidget(window.btn_search_prev)

        window.btn_search_next = QToolButton()
        window.btn_search_next.setObjectName("SearchBtn")
        window.btn_search_next.setToolTip("Tìm tiếp (F3)")
        window.btn_search_next.setIcon(svg_icon("chevron_right.svg", size=16, color=window._search_arrow_color()))
        window.btn_search_next.clicked.connect(
            lambda: search_from_panel(window, find_previous=False, force_new=False)
        )
        row.addWidget(window.btn_search_next)

        window.btn_search_close = QToolButton()
        window.btn_search_close.setObjectName("SearchBtnClose")
        window.btn_search_close.setToolTip("Đóng tìm kiếm (Esc)")
        window.btn_search_close.setText("Đóng")
        window.btn_search_close.clicked.connect(lambda: hide_search_panel(window))
        row.addWidget(window.btn_search_close)

        self.adjustSize()


def build_search_panel(window):
    window.search_panel = SearchPanel(window)
    reposition_search_panel(window)
    return window.search_panel


def reposition_search_panel(window):
    if not hasattr(window, "search_panel"):
        return
    margin = 14
    tab_bar_h = window.tab_widget.tabBar().height() if window.tab_widget.count() > 0 else 0
    window.search_panel.adjustSize()
    max_width = max(340, window.tab_widget.width() - (margin * 2))
    panel_width = min(500, max_width)
    window.search_panel.setFixedWidth(panel_width)
    x = max(margin, window.tab_widget.width() - window.search_panel.width() - margin)
    y = tab_bar_h + margin
    window.search_panel.move(x, y)


def show_search_panel(window):
    if not window.current_path:
        window.status.showMessage("Vui lòng mở tệp PDF trước khi tìm kiếm", 3000)
        return
    reposition_search_panel(window)
    window.search_panel.show()
    window.search_panel.raise_()
    if window.search_query and not window.search_input.text().strip():
        window.search_input.setText(window.search_query)
    window.search_input.setFocus()
    window.search_input.selectAll()


def hide_search_panel(window):
    window.search_panel.hide()


def search_from_panel(window, *, find_previous: bool, force_new: bool):
    query = window.search_input.text().strip()
    if not query:
        window.status.showMessage("Nhập từ khóa để tìm kiếm", 2500)
        return
    is_new = force_new or (query != (window.search_query or ""))
    execute_search(window, query, find_previous=find_previous, new_search=is_new)
