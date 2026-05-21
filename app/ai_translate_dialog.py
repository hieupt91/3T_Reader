"""Dialog dịch thuật tài liệu PDF — Việt ↔ Anh."""
from __future__ import annotations

import os
import threading

from packages.qt_compat.QtCore import Qt, QTimer, QObject, pyqtSignal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QFileDialog, QButtonGroup, QRadioButton,
    QSizePolicy,
)

_STYLE = """
QDialog { background: #16162A; }
QLabel#title  { color: #E8EEFF; font-size: 15px; font-weight: 700; }
QLabel#status { color: #8080B0; font-size: 11px; }
QTextEdit {
    background: #1A1A2E;
    color: #D0D8F8;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    font-size: 13px;
    padding: 10px;
    line-height: 1.5;
}
QRadioButton { color: #C0C8F0; font-size: 13px; }
QRadioButton::indicator { width: 15px; height: 15px; }
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
QPushButton#btn_translate {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3b6fd4,stop:1 #5b4fd4);
    color: white; border: none;
}
QPushButton#btn_translate:hover { background: #4b7fe4; }
QFrame#divider { background: #2A2A4A; }
"""


class _TranslateWorker(QObject):
    finished = pyqtSignal(object)   # TranslationResult
    error    = pyqtSignal(str)

    def __init__(self, pdf_path: str, page_num: int,
                 source_lang: str, target_lang: str):
        super().__init__()
        self._pdf_path    = pdf_path
        self._page_num    = page_num
        self._source_lang = source_lang
        self._target_lang = target_lang

    def run(self):
        try:
            from packages.ai.translate import translate_pdf_page
            result = translate_pdf_page(
                self._pdf_path, self._page_num,
                self._source_lang, self._target_lang,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class AITranslateDialog(QDialog):
    """Dialog dịch thuật trang PDF hiện tại."""

    def __init__(self, parent, pdf_path: str, current_page: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Dịch thuật tài liệu")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.resize(660, 520)
        self.setStyleSheet(_STYLE)

        self._pdf_path    = pdf_path
        self._current_page = current_page
        self._result_text  = ""
        self._worker: _TranslateWorker | None = None

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel(f"Dịch thuật tài liệu — Trang {self._current_page}")
        title.setObjectName("title")
        root.addWidget(title)

        # Language selector
        lang_row = QHBoxLayout()
        lang_row.setSpacing(20)

        self._radio_vi_en = QRadioButton("Việt → Anh")
        self._radio_en_vi = QRadioButton("Anh → Việt")
        self._radio_vi_en.setChecked(True)

        self._lang_group = QButtonGroup(self)
        self._lang_group.addButton(self._radio_vi_en, 0)
        self._lang_group.addButton(self._radio_en_vi, 1)

        lang_row.addWidget(self._radio_vi_en)
        lang_row.addWidget(self._radio_en_vi)
        lang_row.addStretch()
        root.addLayout(lang_row)

        # Status label
        self._lbl_status = QLabel("Sẵn sàng dịch.")
        self._lbl_status.setObjectName("status")
        root.addWidget(self._lbl_status)

        # Result area
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setPlaceholderText("Bản dịch sẽ xuất hiện ở đây…")
        self._text_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._text_edit)

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        root.addWidget(div)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_close = QPushButton("Đóng")
        self._btn_close.clicked.connect(self.reject)

        self._btn_translate = QPushButton("Dịch trang hiện tại")
        self._btn_translate.setObjectName("btn_translate")
        self._btn_translate.clicked.connect(self._on_translate)

        self._btn_save = QPushButton("Lưu bản dịch (.txt)")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)

        btn_row.addWidget(self._btn_close)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_translate)
        root.addLayout(btn_row)

    def _on_translate(self):
        from packages.ai.provider import is_ai_available
        if not is_ai_available():
            self._text_edit.setPlainText(
                "Chưa cấu hình API key AI. Vào Settings để cài đặt."
            )
            self._lbl_status.setText("Chưa có API key.")
            return

        source_lang = "vi" if self._radio_vi_en.isChecked() else "en"
        target_lang = "en" if source_lang == "vi" else "vi"

        self._btn_translate.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._lbl_status.setText("Đang dịch…")
        self._text_edit.setPlainText("Đang dịch…")

        self._worker = _TranslateWorker(
            self._pdf_path, self._current_page, source_lang, target_lang
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        thread = threading.Thread(target=self._worker.run, daemon=True)
        thread.start()

    def _on_finished(self, result):
        self._btn_translate.setEnabled(True)
        if result.success:
            self._result_text = result.translated
            self._text_edit.setPlainText(self._result_text)
            self._lbl_status.setStyleSheet("color:#4fc080;font-size:11px")
            self._lbl_status.setText("Dịch hoàn thành.")
            self._btn_save.setEnabled(True)
        else:
            self._text_edit.setPlainText(f"Lỗi: {result.error}")
            self._lbl_status.setStyleSheet("color:#E05050;font-size:11px")
            self._lbl_status.setText(f"Lỗi: {result.error}")

    def _on_error(self, msg: str):
        self._btn_translate.setEnabled(True)
        self._text_edit.setPlainText(f"Lỗi: {msg}")
        self._lbl_status.setStyleSheet("color:#E05050;font-size:11px")
        self._lbl_status.setText(f"Lỗi: {msg}")

    def _on_save(self):
        base = os.path.splitext(os.path.basename(self._pdf_path))[0]
        default_name = f"{base}_trang{self._current_page}_dichthuat.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu bản dịch",
            os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "Text files (*.txt)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._result_text)
            orig = self._btn_save.text()
            self._btn_save.setText("Đã lưu!")
            QTimer.singleShot(1500, lambda: self._btn_save.setText(orig))
