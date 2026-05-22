"""Dialog hiển thị kết quả OCR và cho phép copy / lưu file."""
from __future__ import annotations

import os
import threading

from packages.qt_compat.QtCore import Qt, QTimer, pyqtSignal, QObject
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QProgressBar, QFrame, QFileDialog,
    QApplication, QSizePolicy,
)

_STYLE = """
QDialog { background: #16162A; }
QLabel#title { color: #E8EEFF; font-size: 15px; font-weight: 700; }
QLabel#info  { color: #8080B0; font-size: 11px; }
QLabel#warn  { color: #f59e0b; font-size: 11px; }
QLabel#err   { color: #E05050; font-size: 11px; }
QTextEdit {
    background: #1A1A2E;
    color: #D0D8F8;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    font-family: "SF Mono", "Consolas", monospace;
    font-size: 12px;
    padding: 10px;
    line-height: 1.5;
}
QPushButton {
    background: #1E1E38;
    color: #B0B8E0;
    border: 1px solid #3A3A60;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover { background: #2A2A50; border-color: #6060C0; }
QPushButton:disabled { color: #444466; border-color: #2A2A44; }
QPushButton#btn_copy {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3b6fd4,stop:1 #5b4fd4);
    color: white; border: none;
}
QPushButton#btn_copy:hover { background: #4b7fe4; }
QProgressBar {
    background: #1A1A2E; border: 1px solid #2A2A4A;
    border-radius: 5px; height: 8px; text-align: center;
}
QProgressBar::chunk { background: #6366f1; border-radius: 4px; }
QFrame#divider { background: #2A2A4A; }
"""


class _Worker(QObject):
    progress  = pyqtSignal(int, str)   # (page_done, text_so_far)
    finished  = pyqtSignal(str, int)   # (full_text, total_pages)
    error     = pyqtSignal(str)

    def __init__(self, pdf_path: str, pages: list[int], high_quality: bool):
        super().__init__()
        self._path = pdf_path
        self._pages = pages
        self._hq = high_quality
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        from packages.ocr.engine import ocr_pdf_page
        all_text = []
        for i, pn in enumerate(self._pages, 1):
            if self._cancelled:
                break
            result = ocr_pdf_page(self._path, pn, high_quality=self._hq)
            if result.error and not result.text:
                self.error.emit(result.error)
                return
            header = f"{'─'*40}\n📄 Trang {pn}\n{'─'*40}\n"
            block = header + (result.text or "(không nhận dạng được văn bản)")
            all_text.append(block)
            combined = "\n\n".join(all_text)
            self.progress.emit(i, combined)
        self.finished.emit("\n\n".join(all_text), len(self._pages))


class OCRDialog(QDialog):
    """Dialog OCR — chạy trong background thread, hiển thị kết quả cuộn."""

    def __init__(self, parent, pdf_path: str, pages: list[int],
                 current_page: int = 1, high_quality: bool = False):
        super().__init__(parent)
        self.setWindowTitle("OCR Tiếng Việt – 3T Reader")
        self.setModal(True)
        self.resize(680, 560)
        self.setStyleSheet(_STYLE)

        self._pdf_path = pdf_path
        self._pages = pages
        self._hq = high_quality
        self._worker: _Worker | None = None
        self._thread = None
        self._final_text = ""

        self._build_ui(current_page)
        self._start()

    def _build_ui(self, current_page: int):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel(f"📖 OCR Trang {current_page}" if len(self._pages) == 1
                       else f"📖 OCR Toàn bộ ({len(self._pages)} trang)")
        title.setObjectName("title")
        hdr.addWidget(title)
        hdr.addStretch()
        root.addLayout(hdr)

        info_text = "Đang nhận dạng văn bản tiếng Việt…"
        self._lbl_info = QLabel(info_text)
        self._lbl_info.setObjectName("info")
        root.addWidget(self._lbl_info)

        # Progress bar (chỉ hiện khi nhiều trang)
        self._progress = QProgressBar()
        self._progress.setRange(0, len(self._pages))
        self._progress.setValue(0)
        if len(self._pages) == 1:
            self._progress.hide()
        root.addWidget(self._progress)

        # Text area
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setPlaceholderText("Văn bản sẽ xuất hiện ở đây…")
        self._text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._text_edit)

        # Divider
        div = QFrame(); div.setObjectName("divider"); div.setFixedHeight(1)
        root.addWidget(div)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)

        self._btn_cancel = QPushButton("Hủy")
        self._btn_cancel.clicked.connect(self._on_cancel)

        self._btn_copy = QPushButton("📋  Sao chép tất cả")
        self._btn_copy.setObjectName("btn_copy")
        self._btn_copy.setEnabled(False)
        self._btn_copy.clicked.connect(self._on_copy)

        self._btn_save = QPushButton("💾  Lưu .txt")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)

        btn_row.addWidget(self._btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_copy)
        root.addLayout(btn_row)

    def _start(self):
        self._worker = _Worker(self._pdf_path, self._pages, self._hq)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._thread = threading.Thread(target=self._worker.run, daemon=True)
        self._thread.start()

    def _on_progress(self, done: int, text_so_far: str):
        self._progress.setValue(done)
        self._lbl_info.setText(f"Đang xử lý trang {done}/{len(self._pages)}…")
        self._text_edit.setPlainText(text_so_far)
        # Auto-scroll xuống
        sb = self._text_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_finished(self, full_text: str, total: int):
        self._final_text = full_text
        words = len(full_text.split()) if full_text else 0
        self._lbl_info.setObjectName("info")
        self._lbl_info.setText(
            f"✓ Hoàn thành {total} trang — ~{words} từ nhận dạng được"
        )
        self._lbl_info.setStyleSheet("color:#4fc080;font-size:11px")
        self._progress.setValue(len(self._pages))
        self._text_edit.setPlainText(full_text or "(Không tìm thấy văn bản)")
        self._btn_cancel.setText("Đóng")
        self._btn_copy.setEnabled(bool(full_text))
        self._btn_save.setEnabled(bool(full_text))

    def _on_error(self, msg: str):
        self._lbl_info.setText(f"Lỗi: {msg}")
        self._lbl_info.setStyleSheet("color:#E05050;font-size:11px")
        self._btn_cancel.setText("Đóng")

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
        self.reject()

    def _on_copy(self):
        QApplication.clipboard().setText(self._final_text)
        orig = self._btn_copy.text()
        self._btn_copy.setText("✓  Đã sao chép!")
        QTimer.singleShot(1500, lambda: self._btn_copy.setText(orig))

    def _on_save(self):
        default_name = os.path.splitext(os.path.basename(self._pdf_path))[0] + "_ocr.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu kết quả OCR",
            os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "Text files (*.txt)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._final_text)
            orig = self._btn_save.text()
            self._btn_save.setText("✓  Đã lưu!")
            QTimer.singleShot(1500, lambda: self._btn_save.setText(orig))
