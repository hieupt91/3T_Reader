from packages.qt_compat.QtWidgets import (
    QDockWidget, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QLabel,
)
from packages.qt_compat.QtGui import QPixmap, QImage, QIcon
from packages.qt_compat.QtCore import Qt, QSize, QThread, QTimer, pyqtSignal

from packages.pdf_engine import get_pdf_engine


class ThumbnailLoader(QThread):
    thumbnailReady = pyqtSignal(int, QImage)
    finishedLoading = pyqtSignal()

    def __init__(self, pdf_path: str, page_numbers: list[int]):
        super().__init__()
        self.pdf_path = pdf_path
        self.page_numbers = page_numbers

    def run(self):
        try:
            doc = get_pdf_engine().open(self.pdf_path)
        except Exception:
            self.finishedLoading.emit()
            return

        try:
            for page_number in self.page_numbers:
                if self.isInterruptionRequested():
                    break
                rendered = doc.render_page_rgb(page_number, scale=0.3)
                image = QImage(
                    rendered.samples,
                    rendered.width,
                    rendered.height,
                    rendered.stride,
                    QImage.Format.Format_RGB888,
                ).copy()
                self.thumbnailReady.emit(page_number, image)
        finally:
            doc.close()
            self.finishedLoading.emit()


class ThumbnailSidebar(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Trang", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setFixedWidth(180)

        self.list = QListWidget()
        self.list.setIconSize(QSize(132, 176))
        self.list.setSpacing(8)
        self.list.setUniformItemSizes(True)
        self.list.setStyleSheet("""
            QListWidget {
                background-color: #0d0d12;
                border: none;
                padding: 10px 6px;
            }
            QListWidget::item {
                background-color: transparent;
                border-radius: 8px;
                padding: 6px 4px;
                color: #8a8aa6;
                font-size: 11px;
                text-align: center;
            }
            QListWidget::item:selected {
                background-color: #1f1f30;
                color: #ffffff;
                border: 1px solid #6c63ff;
            }
            QListWidget::item:hover {
                background-color: #181824;
            }
            QListWidget:focus {
                outline: none;
            }
        """)
        self.setWidget(self.list)
        self._on_click = None
        self._pdf_path = None
        self._page_count = 0
        self._loaded_pages = set()
        self._requested_pages = []
        self._pending_pages = []
        self._loader = None
        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(80)
        self._load_timer.timeout.connect(self._load_visible_thumbnails)
        self.list.itemClicked.connect(self._handle_click)
        self.list.verticalScrollBar().valueChanged.connect(self._schedule_visible_load)

    def _handle_click(self, item):
        if self._on_click:
            self._on_click(self.list.row(item) + 1)

    def load_thumbnails(self, pdf_path: str, on_click):
        self.list.clear()
        self._on_click = on_click
        self._pdf_path = pdf_path
        self._loaded_pages.clear()
        self._requested_pages = []
        self._pending_pages = []

        if self._loader and self._loader.isRunning():
            self._loader.requestInterruption()
            self._loader.wait()

        self._page_count = self._read_page_count(pdf_path)
        for page_number in range(1, self._page_count + 1):
            item = QListWidgetItem()
            item.setText(f"Trang {page_number}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list.addItem(item)

        self._schedule_visible_load()

    def _read_page_count(self, pdf_path: str) -> int:
        try:
            return get_pdf_engine().page_count(pdf_path)
        except Exception:
            return 0

    def _schedule_visible_load(self):
        if self._page_count <= 0:
            return
        self._load_timer.start()

    def _visible_page_range(self) -> tuple[int, int]:
        if self._page_count <= 0:
            return (1, 0)

        viewport = self.list.viewport()
        top_item = self.list.itemAt(12, 12)
        bottom_item = self.list.itemAt(12, max(12, viewport.height() - 12))

        first = self.list.row(top_item) + 1 if top_item else 1
        last = self.list.row(bottom_item) + 1 if bottom_item else min(self._page_count, first + 5)

        first = max(1, first - 2)
        last = min(self._page_count, last + 2)
        return (first, last)

    def _load_visible_thumbnails(self):
        first, last = self._visible_page_range()
        if first > last:
            return

        pages = [page_number for page_number in range(first, last + 1) if page_number not in self._loaded_pages]
        if not pages:
            return

        self._requested_pages = pages
        self._start_loader(pages)

    def _start_loader(self, page_numbers: list[int]):
        if not self._pdf_path or not page_numbers:
            return

        if self._loader and self._loader.isRunning():
            self._pending_pages = page_numbers
            self._loader.requestInterruption()
            return

        self._loader = ThumbnailLoader(self._pdf_path, page_numbers)
        self._loader.thumbnailReady.connect(self._append_thumbnail)
        self._loader.finishedLoading.connect(self._finish_loading)
        self._loader.start()

    def _append_thumbnail(self, page_number: int, image: QImage):
        index = page_number - 1
        if not (0 <= index < self.list.count()):
            return

        self._loaded_pages.add(page_number)
        item = self.list.item(index)
        item.setIcon(QIcon(QPixmap.fromImage(image)))

    def _finish_loading(self):
        if self._pending_pages:
            pending_pages = [page_number for page_number in self._pending_pages if page_number not in self._loaded_pages]
            self._pending_pages = []
            self._start_loader(pending_pages)

    def highlight_page(self, page_number: int):
        """Tô sáng trang đang xem trong thanh bên."""
        index = page_number - 1
        if 0 <= index < self.list.count():
            self.list.setCurrentRow(index)
            self.list.scrollToItem(
                self.list.item(index),
                QListWidget.ScrollHint.PositionAtCenter
            )
            self._schedule_visible_load()


class BookmarkSidebar(QDockWidget):
    """Hiển thị mục lục (Table of Contents / Outline) của PDF."""

    def __init__(self, parent=None):
        super().__init__("Mục lục", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setFixedWidth(220)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._empty_label = QLabel("Tệp PDF này\nkhông có mục lục.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #6a6a8a; font-size: 12px; padding: 20px;")

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setStyleSheet("""
            QTreeWidget {
                background-color: #0d0d12;
                border: none;
                padding: 6px 4px;
                color: #c8c8e0;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px 4px;
                border-radius: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #1f1f38;
                color: #ffffff;
            }
            QTreeWidget::item:hover {
                background-color: #181830;
            }
            QTreeWidget:focus { outline: none; }
        """)

        layout.addWidget(self._empty_label)
        layout.addWidget(self._tree)
        self.setWidget(container)

        self._on_navigate = None
        self._tree.itemClicked.connect(self._handle_click)
        self._tree.setVisible(False)

    def _handle_click(self, item: QTreeWidgetItem, _col: int):
        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page and self._on_navigate:
            self._on_navigate(page)

    def load_outline(self, pdf_path: str, on_navigate):
        self._on_navigate = on_navigate
        self._tree.clear()
        outline = self._read_outline(pdf_path)

        if not outline:
            self._tree.setVisible(False)
            self._empty_label.setVisible(True)
            return

        self._empty_label.setVisible(False)
        self._tree.setVisible(True)

        stack: list[tuple[int, QTreeWidgetItem]] = []
        for level, title, page in outline:
            item = QTreeWidgetItem([title.strip() or f"Trang {page}"])
            item.setData(0, Qt.ItemDataRole.UserRole, page)
            item.setToolTip(0, f"Trang {page}  —  {title.strip()}")

            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                stack[-1][1].addChild(item)
            else:
                self._tree.addTopLevelItem(item)

            stack.append((level, item))

        self._tree.expandAll()

    def clear(self):
        self._tree.clear()
        self._tree.setVisible(False)
        self._empty_label.setVisible(True)

    def _read_outline(self, pdf_path: str) -> list[tuple[int, str, int]]:
        try:
            import pikepdf
            toc: list[tuple[int, str, int]] = []
            with pikepdf.open(pdf_path) as doc:
                page_idx: dict = {}
                for i, pg in enumerate(doc.pages):
                    try:
                        page_idx[pg.obj.objgen] = i + 1
                    except Exception:
                        pass
                with doc.open_outline() as outline:
                    def _collect(items, level: int = 1):
                        for item in items:
                            page_no = 1
                            try:
                                dest = item.destination
                                if isinstance(dest, list) and dest:
                                    pg_ref = dest[0]
                                    page_no = page_idx.get(getattr(pg_ref, "objgen", None), 1)
                            except Exception:
                                pass
                            if item.title:
                                toc.append((level, item.title, page_no))
                            if item.children:
                                _collect(item.children, level + 1)
                    _collect(outline.root)
            return toc
        except Exception:
            return []
