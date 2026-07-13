from packages.qt_compat.QtWidgets import (
    QDockWidget, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QLabel,
    QMenu,
)
from packages.qt_compat.QtGui import QPixmap, QImage, QIcon
from packages.qt_compat.QtCore import Qt, QSize, QObject, QTimer, pyqtSignal

from packages.pdf_engine import get_pdf_engine
import os


class ThumbnailLoader(QObject):
    thumbnailReady = pyqtSignal(int, QImage)
    finishedLoading = pyqtSignal()

    def __init__(self, pdf_path: str, page_numbers: list[int], render_scale: float = 0.45):
        super().__init__()
        self.pdf_path = pdf_path
        self.page_numbers = page_numbers
        self.render_scale = max(0.3, min(0.9, float(render_scale)))
        import threading
        self._interrupt_event = threading.Event()
        self._thread = None

    def start(self):
        import threading
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def requestInterruption(self):
        self._interrupt_event.set()

    def isRunning(self):
        return self._thread is not None and self._thread.is_alive()

    def run(self):
        try:
            doc = get_pdf_engine().open(self.pdf_path)
        except Exception:
            self.finishedLoading.emit()
            return

        try:
            for page_number in self.page_numbers:
                if self._interrupt_event.is_set():
                    break
                rendered = doc.render_page_rgb(page_number, scale=self.render_scale)
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
        self.setFixedWidth(190)

        self.list = QListWidget()
        self.list.setIconSize(QSize(170, 170))
        self.list.setGridSize(QSize(182, 226))
        self.list.setSpacing(8)
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        
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
        self._context_actions = {}
        self._pdf_path = None
        self._doc_signature = None
        self._page_count = 0
        self._loaded_pages = set()
        self._requested_pages = []
        self._pending_pages = []
        self._loader = None
        self._load_token = 0
        self._populate_token = 0
        self._populate_index = 1
        self._populate_batch_size = 40
        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(80)
        self._load_timer.timeout.connect(self._load_visible_thumbnails)
        self._populate_timer = QTimer(self)
        self._populate_timer.setSingleShot(True)
        self._populate_timer.setInterval(0)
        self._populate_timer.timeout.connect(self._populate_next_batch)
        self.list.itemClicked.connect(self._handle_click)
        self.list.verticalScrollBar().valueChanged.connect(self._schedule_visible_load)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._show_context_menu)

    def _thumbnail_render_scale(self) -> float:
        try:
            dpr = float(self.list.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        return max(0.45, min(0.9, 0.45 * dpr))

    def _handle_click(self, item):
        if self._on_click:
            self._on_click(self.list.row(item) + 1)

    def _show_context_menu(self, pos):
        item = self.list.itemAt(pos)
        if not item:
            return
        page_number = self.list.row(item) + 1
        menu = QMenu(self)
        act_goto = menu.addAction(f"Đi tới trang {page_number}")
        act_reload = menu.addAction("Tải lại thumbnail")
        menu.addSeparator()
        act_rotate = menu.addAction("Xoay trang")
        act_delete = menu.addAction("Xóa trang")
        act_extract = menu.addAction("Tách PDF...")
        act_insert_after = menu.addAction("Chèn trang sau")
        extra_actions = {
            act_rotate: "rotate",
            act_delete: "delete",
            act_extract: "extract",
            act_insert_after: "insert_after",
        }
        for action, key in extra_actions.items():
            action.setEnabled(callable(self._context_actions.get(key)))
        chosen = menu.exec(self.list.viewport().mapToGlobal(pos))
        if chosen == act_goto and self._on_click:
            self._on_click(page_number)
        elif chosen == act_reload:
            self._loaded_pages.discard(page_number)
            self._start_loader([page_number])
        elif chosen in extra_actions:
            callback = self._context_actions.get(extra_actions[chosen])
            if callable(callback):
                callback(page_number)

    def load_thumbnails(self, pdf_path: str, on_click, context_actions: dict | None = None):
        new_signature = self._read_doc_signature(pdf_path)
        if (
            self._pdf_path == pdf_path
            and self.list.count() > 0
            and self._doc_signature == new_signature
        ):
            self._on_click = on_click
            self._context_actions = context_actions or {}
            self._schedule_visible_load()
            return

        # Cùng file, nội dung đổi nhưng SỐ TRANG không đổi (xoay/sửa text/chú
        # thích): làm mới icon TẠI CHỖ — không clear() danh sách (clear gây
        # thumbnail nháy trắng + dựng lại toàn bộ = lag sau mỗi thao tác).
        if self._pdf_path == pdf_path and self.list.count() > 0:
            new_count = self._read_page_count(pdf_path)
            if new_count == self._page_count and new_count > 0:
                self._on_click = on_click
                self._context_actions = context_actions or {}
                self._doc_signature = new_signature
                self._loaded_pages.clear()
                self._requested_pages = []
                self._pending_pages = []
                self._schedule_visible_load()
                return

        self._load_token += 1
        self._populate_token = self._load_token
        self.list.clear()
        self._on_click = on_click
        self._context_actions = context_actions or {}
        self._pdf_path = pdf_path
        self._doc_signature = new_signature
        self._loaded_pages.clear()
        self._requested_pages = []
        self._pending_pages = []
        self._populate_timer.stop()
        self._populate_index = 1

        if self._loader and self._loader.isRunning():
            self._loader.requestInterruption()

        self._page_count = self._read_page_count(pdf_path)
        if self._page_count <= 0:
            return

        self._populate_next_batch()

    def _populate_next_batch(self):
        if self._populate_token != self._load_token:
            return
        if self._page_count <= 0 or self._populate_index > self._page_count:
            return

        end_page = min(self._page_count, self._populate_index + self._populate_batch_size - 1)
        for page_number in range(self._populate_index, end_page + 1):
            item = QListWidgetItem()
            item.setText(f"Trang {page_number}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(QSize(176, 220))
            self.list.addItem(item)

        self._populate_index = end_page + 1
        self._schedule_visible_load()

        if self._populate_index <= self._page_count:
            self._populate_timer.start(0)

    def _read_page_count(self, pdf_path: str) -> int:
        try:
            return get_pdf_engine().page_count(pdf_path)
        except Exception:
            return 0

    def _read_doc_signature(self, pdf_path: str):
        try:
            stat = os.stat(pdf_path)
            return (os.path.abspath(pdf_path), int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            return (os.path.abspath(pdf_path), 0, 0)

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

        current_token = self._load_token
        pdf_path = self._pdf_path
        self._loader = ThumbnailLoader(self._pdf_path, page_numbers, self._thumbnail_render_scale())
        self._loader.thumbnailReady.connect(
            lambda page_number, image, token=current_token, path=pdf_path: self._append_thumbnail(token, path, page_number, image)
        )
        self._loader.finishedLoading.connect(lambda token=current_token: self._finish_loading(token))
        self._loader.start()

    def _append_thumbnail(self, token: int, pdf_path: str, page_number: int, image: QImage):
        if token != self._load_token or pdf_path != self._pdf_path:
            return

        index = page_number - 1
        if not (0 <= index < self.list.count()):
            return

        self._loaded_pages.add(page_number)
        item = self.list.item(index)
        item.setIcon(QIcon(QPixmap.fromImage(image)))

    def _finish_loading(self, token: int):
        if token != self._load_token:
            return
        if self._pending_pages:
            pending_pages = [page_number for page_number in self._pending_pages if page_number not in self._loaded_pages]
            self._pending_pages = []
            self._start_loader(pending_pages)

    def highlight_page(self, page_number: int):
        """Tô sáng trang đang xem trong thanh bên."""
        try:
            page_number = int(page_number)
        except Exception:
            return
        while (
            self._page_count > 0
            and page_number > self.list.count()
            and self._populate_index <= self._page_count
        ):
            self._populate_next_batch()
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
        self._page_items: dict[int, list[QTreeWidgetItem]] = {}
        self._tree.itemClicked.connect(self._handle_click)
        self._tree.setVisible(False)

    def _handle_click(self, item: QTreeWidgetItem, _col: int):
        self._expand_to_item(item)
        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page and self._on_navigate:
            self._on_navigate(page)

    def _expand_to_item(self, item: QTreeWidgetItem):
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()

    def load_outline(self, pdf_path: str, on_navigate):
        self._on_navigate = on_navigate
        self._tree.clear()
        self._page_items = {}
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
            self._page_items.setdefault(int(page), []).append(item)

            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                stack[-1][1].addChild(item)
            else:
                self._tree.addTopLevelItem(item)

            stack.append((level, item))

        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setExpanded(True)

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
