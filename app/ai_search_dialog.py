"""Dialog tìm kiếm theo nghĩa (Semantic Search) với PDF."""
from __future__ import annotations

import os
import threading

from packages.qt_compat.QtCore import Qt, QTimer
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QFrame, QSizePolicy,
)
from styles.theme import is_dark


def _build_style(dark: bool) -> str:
    if dark:
        return """
QDialog { background: #16162A; }
QLabel#title  { color: #E8EEFF; font-size: 15px; font-weight: 700; }
QLabel#status { color: #8080B0; font-size: 11px; }
QLineEdit {
    background: #1E1E38;
    color: #E0E8FF;
    border: 1px solid #3A3A60;
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus { border-color: #6060C0; }
QPushButton {
    background: #1E1E38;
    color: #B0B8E0;
    border: 1px solid #3A3A60;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover  { background: #2A2A50; border-color: #6060C0; }
QPushButton:disabled { color: #444466; border-color: #2A2A44; }
QPushButton#btn_search {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #8b5cf6);
    color: white; border: none;
    min-width: 90px;
}
QPushButton#btn_search:hover { background: #7374f8; }
QPushButton#btn_build {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3b6fd4,stop:1 #5b4fd4);
    color: white; border: none;
}
QPushButton#btn_build:hover { background: #4b7fe4; }
QListWidget {
    background: #12122A;
    color: #D0D8F8;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    font-size: 13px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #1E1E3A;
    border-radius: 6px;
}
QListWidget::item:selected {
    background: #1E1E48;
    color: #E8F0FF;
    border-left: 3px solid #6366f1;
}
QListWidget::item:hover {
    background: #1A1A3A;
}
QFrame#divider { background: #2A2A4A; }
"""
    return """
QDialog { background: #F8FAFF; }
QLabel#title  { color: #0F172A; font-size: 15px; font-weight: 700; }
QLabel#status { color: #475569; font-size: 11px; }
QLineEdit {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus { border-color: #2563EB; }
QPushButton {
    background: #E2E8F0;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover  { background: #CBD5E1; border-color: #94A3B8; }
QPushButton:disabled { color: #94A3B8; border-color: #CBD5E1; }
QPushButton#btn_search {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #7C3AED);
    color: white; border: none;
    min-width: 90px;
}
QPushButton#btn_search:hover { background: #3B82F6; }
QPushButton#btn_build {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3b6fd4,stop:1 #5b4fd4);
    color: white; border: none;
}
QPushButton#btn_build:hover { background: #4b7fe4; }
QListWidget {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    font-size: 13px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #E2E8F0;
    border-radius: 6px;
}
QListWidget::item:selected {
    background: #E0F2FE;
    color: #0F172A;
    border-left: 3px solid #2563EB;
}
QListWidget::item:hover {
    background: #F1F5F9;
}
QFrame#divider { background: #CBD5E1; }
"""


def _get_search_cache_dir() -> str:
    from packages.platform.paths import get_cache_dir
    import pathlib
    base = get_cache_dir()
    sub = pathlib.Path(base) / "semantic_search"
    sub.mkdir(parents=True, exist_ok=True)
    return str(sub)


class AISearchDialog(QDialog):
    """Dialog tìm kiếm theo nghĩa — non-modal, giữ nguyên khi đọc."""

    def __init__(self, parent, pdf_path: str):
        super().__init__(parent)
        self.setWindowTitle("Tìm kiếm theo nghĩa (Semantic Search)")
        self.setModal(False)
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        self.resize(750, 580)
        self.setStyleSheet(_build_style(is_dark()))
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        self._pdf_path = pdf_path
        self._index = None
        self._building = False
        self._results: list = []
        self._closed = False
        self._pdf_token = 0

        self._build_ui()
        self._try_load_index()

    def _has_openai_api_key(self) -> bool:
        if os.environ.get("OPENAI_API_KEY"):
            return True
        try:
            from app.actions.ai_actions import load_ai_config

            load_ai_config()
        except Exception:
            pass
        return bool(os.environ.get("OPENAI_API_KEY"))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        # Header
        title = QLabel("Tìm kiếm theo nghĩa (Semantic Search)")
        title.setObjectName("title")
        root.addWidget(title)

        # Search row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Nhập từ khóa hoặc câu hỏi để tìm kiếm…")
        self._input.returnPressed.connect(self._on_search)
        search_row.addWidget(self._input, 1)

        self._btn_search = QPushButton("Tìm kiếm")
        self._btn_search.setObjectName("btn_search")
        self._btn_search.clicked.connect(self._on_search)
        self._btn_search.setEnabled(False)
        search_row.addWidget(self._btn_search)
        root.addLayout(search_row)

        # Build index button (hidden initially)
        self._btn_build = QPushButton("Xây dựng Index (cần OpenAI API key)")
        self._btn_build.setObjectName("btn_build")
        self._btn_build.clicked.connect(self._on_build_index)
        self._btn_build.setVisible(False)
        root.addWidget(self._btn_build)

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        root.addWidget(div)

        # Results list
        self._list = QListWidget()
        self._list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._list.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self._list)

        # Status bar
        self._lbl_status = QLabel("Đang kiểm tra cache…")
        self._lbl_status.setObjectName("status")
        root.addWidget(self._lbl_status)

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _try_load_index(self):
        """Thử tải index từ cache, nếu không có thì hiện nút xây dựng."""
        cache_dir = _get_search_cache_dir()
        pdf_path = self._pdf_path
        token = self._pdf_token

        def _load():
            try:
                from packages.ai.semantic_search import load_index
                idx = load_index(pdf_path, cache_dir)
                return idx, None
            except Exception as exc:
                return None, str(exc)

        def _done(idx, err):
            if self._closed or token != self._pdf_token or pdf_path != self._pdf_path:
                return
            if idx is not None:
                self._index = idx
                self._set_status("Index đã sẵn sàng. Nhập từ khóa để tìm kiếm.", color="#4fc080")
                self._btn_search.setEnabled(True)
                self._btn_build.setVisible(False)
            else:
                if err:
                    self._set_status(f"Chưa có index: {err}", color="#f59e0b")
                else:
                    self._set_status("Chưa có index. Nhấn nút bên trên để xây dựng.", color="#f59e0b")
                self._btn_build.setVisible(True)
                self._btn_search.setEnabled(False)

        result_holder = [None, None]

        def _thread():
            result_holder[0], result_holder[1] = _load()
            QTimer.singleShot(0, lambda: _done(result_holder[0], result_holder[1]))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_build_index(self):
        if self._building:
            return

        if not self._has_openai_api_key():
            self._set_status(
                "Semantic search cần OPENAI_API_KEY. Vào menu AI → Cài đặt AI để nhập key.",
                color="#E05050",
            )
            return

        self._building = True
        self._btn_build.setEnabled(False)
        self._btn_search.setEnabled(False)
        self._set_status("Đang xây dựng index…", color="#6366f1")
        pdf_path = self._pdf_path
        token = self._pdf_token

        result_holder = [None, None]

        def _progress(msg: str):
            QTimer.singleShot(0, lambda m=msg: self._set_status(
                f"Đang xây dựng index: {m}", color="#6366f1"
            ))

        def _thread():
            try:
                from packages.ai.semantic_search import build_index, save_index
                idx, err = build_index(pdf_path, _progress)
                result_holder[0] = idx
                result_holder[1] = err
                if idx is not None:
                    try:
                        save_index(idx, _get_search_cache_dir())
                    except Exception as save_err:
                        result_holder[1] = str(save_err)
            except Exception as exc:
                result_holder[1] = str(exc)
            QTimer.singleShot(0, _build_done)

        def _build_done():
            if self._closed or token != self._pdf_token or pdf_path != self._pdf_path:
                self._building = False
                return
            self._building = False
            idx, err = result_holder
            if idx is not None:
                self._index = idx
                self._set_status("Index đã xây dựng và lưu thành công. Nhập từ khóa để tìm kiếm.", color="#4fc080")
                self._btn_search.setEnabled(True)
                self._btn_build.setVisible(False)
            else:
                self._btn_build.setEnabled(True)
                self._set_status(f"Lỗi khi xây dựng index: {err or 'Không xác định'}", color="#E05050")

        threading.Thread(target=_thread, daemon=True).start()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search(self):
        if self._index is None or self._building:
            return
        query = self._input.text().strip()
        if not query:
            return

        if not self._has_openai_api_key():
            self._set_status(
                "Semantic search cần OPENAI_API_KEY. Vào menu AI → Cài đặt AI để nhập key.",
                color="#E05050",
            )
            return

        self._btn_search.setEnabled(False)
        self._set_status("Đang tìm kiếm…", color="#6366f1")
        self._list.clear()
        pdf_path = self._pdf_path
        token = self._pdf_token

        result_holder = [None, None]

        def _thread():
            try:
                from packages.ai.semantic_search import search
                chunks, err = search(self._index, query, top_k=5)
                result_holder[0] = chunks
                result_holder[1] = err
            except Exception as exc:
                result_holder[1] = str(exc)
            QTimer.singleShot(0, _search_done)

        def _search_done():
            if self._closed or token != self._pdf_token or pdf_path != self._pdf_path:
                self._btn_search.setEnabled(self._index is not None and not self._building)
                return
            self._btn_search.setEnabled(True)
            chunks, err = result_holder
            if err:
                self._set_status(f"Lỗi tìm kiếm: {err}", color="#E05050")
                return
            if not chunks:
                self._set_status("Không tìm thấy kết quả phù hợp.", color="#f59e0b")
                return

            self._results = chunks
            for chunk in chunks:
                preview = chunk.text[:120].replace("\n", " ")
                if len(chunk.text) > 120:
                    preview += "…"
                item = QListWidgetItem(
                    f"Trang {chunk.page}  (độ liên quan: {chunk.score:.2f})\n{preview}"
                )
                item.setData(Qt.ItemDataRole.UserRole, chunk.page)
                self._list.addItem(item)

            self._set_status(f"{len(chunks)} kết quả tìm thấy.", color="#4fc080")

        threading.Thread(target=_thread, daemon=True).start()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_item_clicked(self, item: QListWidgetItem):
        page_num = item.data(Qt.ItemDataRole.UserRole)
        if page_num is None:
            return
        try:
            parent = self.parent()
            if parent is not None:
                viewer = getattr(parent, "viewer", None)
                if viewer is not None:
                    viewer.jump_to_page(page_num)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_pdf(self, pdf_path: str):
        """Cập nhật khi PDF thay đổi — reset index và kết quả."""
        if pdf_path == self._pdf_path:
            return
        self._pdf_token += 1
        self._pdf_path = pdf_path
        self._index = None
        self._list.clear()
        self._results = []
        self._btn_search.setEnabled(False)
        self._btn_build.setVisible(False)
        self._set_status("Tài liệu đã thay đổi. Đang kiểm tra cache…", color="#8080B0")
        self._try_load_index()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, text: str, color: str = "#8080B0"):
        if self._closed:
            return
        self._lbl_status.setText(text)
        self._lbl_status.setStyleSheet(f"color:{color};font-size:11px;")

    def closeEvent(self, event):
        self._closed = True
        parent = self.parent()
        if parent is not None and getattr(parent, "_ai_search_dialog", None) is self:
            parent._ai_search_dialog = None
        super().closeEvent(event)
