from packages.qt_compat.QtWidgets import QTabWidget
from packages.qt_compat.QtCore import Qt


class TabManager(QTabWidget):
    """QTabWidget with 3T Reader tab host defaults wired in one place."""

    def __init__(self, window, *, on_context_menu):
        super().__init__(window)
        self.window = window
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        tab_bar = self.tabBar()
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(on_context_menu)
