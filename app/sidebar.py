import fitz
from PyQt6.QtWidgets import QDockWidget, QListWidget, QListWidgetItem
from PyQt6.QtGui import QPixmap, QImage, QIcon
from PyQt6.QtCore import Qt, QSize, QThread, QTimer, pyqtSignal


class ThumbnailLoader(QThread):
    thumbnailReady = pyqtSignal(int, QImage)
    finishedLoading = pyqtSignal()

    def __init__(self, pdf_path: str, page_numbers: list[int]):
        super().__init__()
        self.pdf_path = pdf_path
        self.page_numbers = page_numbers

    def run(self):
        try:
            doc = fitz.open(self.pdf_path)
        except Exception:
            self.finishedLoading.emit()
            return

        try:
            for page_number in self.page_numbers:
                if self.isInterruptionRequested():
                    break
                page = doc.load_page(page_number - 1)
                pix = page.get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
                image = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
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
            doc = fitz.open(pdf_path)
            count = doc.page_count
            doc.close()
            return count
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