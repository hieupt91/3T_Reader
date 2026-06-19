"""Dialog dịch thuật tài liệu PDF — đa ngôn ngữ, đa engine, tự động nhận diện."""
from __future__ import annotations

import os

from packages.qt_compat.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QFileDialog, QComboBox, QProgressBar,
    QTabWidget, QWidget, QSizePolicy, QSplitter, QSpinBox,
    QCheckBox, QMessageBox,
)
from styles.theme import is_dark

from packages.ai.translate import (
    AUTO_DETECT, SUPPORTED_LANGUAGES, detect_language,
    translate_text, translate_pdf_page, translate_pdf_document,
    TranslationResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────────────────────────────────────

def _style(dark: bool) -> str:
    if dark:
        bg, card, border = "#13132A", "#1A1A2E", "#2A2A48"
        text, muted = "#D8E0FF", "#7080B0"
        accent = "#5B8DEF"
        btn_bg = "#1E1E3C"
        btn_border = "#3A3A60"
    else:
        bg, card, border = "#F4F6FF", "#FFFFFF", "#D0D5EC"
        text, muted = "#0F172A", "#5570A0"
        accent = "#2563EB"
        btn_bg = "#E8EEFF"
        btn_border = "#C0C8E8"

    return f"""
QDialog {{ background: {bg}; }}
QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; background: {card}; }}
QTabBar::tab {{
    background: {btn_bg}; color: {muted}; border: 1px solid {border};
    border-bottom: none; border-radius: 6px 6px 0 0;
    padding: 6px 18px; font-size: 12px; font-weight: 600;
}}
QTabBar::tab:selected {{ background: {card}; color: {text}; border-bottom: 1px solid {card}; }}
QTextEdit {{
    background: {card}; color: {text};
    border: 1px solid {border}; border-radius: 8px;
    font-size: 13px; padding: 10px; line-height: 1.6;
}}
QComboBox {{
    background: {btn_bg}; color: {text}; border: 1px solid {border};
    border-radius: 6px; padding: 5px 10px; font-size: 12px; min-width: 160px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {card}; color: {text}; border: 1px solid {border};
    selection-background-color: {accent}; selection-color: white;
}}
QSpinBox {{
    background: {btn_bg}; color: {text}; border: 1px solid {border};
    border-radius: 6px; padding: 4px 8px; font-size: 12px; min-width: 60px;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; }}
QLabel#title {{ color: {text}; font-size: 15px; font-weight: 700; }}
QLabel#status {{ color: {muted}; font-size: 11px; }}
QLabel#lang_detected {{ color: {accent}; font-size: 11px; font-weight: 600; }}
QLabel#section {{ color: {muted}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QProgressBar {{
    background: {btn_bg}; border: 1px solid {border};
    border-radius: 5px; height: 8px; text-align: center; color: {text}; font-size: 10px;
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
QPushButton {{
    background: {btn_bg}; color: {text};
    border: 1px solid {btn_border}; border-radius: 7px;
    padding: 7px 16px; font-size: 12px; font-weight: 600;
}}
QPushButton:hover {{ border-color: {accent}; color: {accent}; }}
QPushButton:disabled {{ color: {muted}; border-color: {border}; }}
QPushButton#btn_primary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3B6FD4,stop:1 #5B4FD4);
    color: white; border: none; padding: 8px 22px;
}}
QPushButton#btn_primary:hover {{ background: #4B7FE4; }}
QPushButton#btn_primary:disabled {{ background: {border}; color: {muted}; }}
QPushButton#btn_google {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4285F4,stop:1 #34A853);
    color: white; border: none; padding: 8px 22px;
}}
QPushButton#btn_google:hover {{ background: #5296FF; }}
QFrame#divider {{ background: {border}; max-height: 1px; }}
QCheckBox {{ color: {text}; font-size: 12px; }}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Worker thread
# ─────────────────────────────────────────────────────────────────────────────

class _TranslateWorker(QObject):
    finished = pyqtSignal(object, str)   # (TranslationResult, actual_source_lang)
    progress = pyqtSignal(int, int, str) # (current, total, status)
    error    = pyqtSignal(str)

    def __init__(self, task_fn, supports_progress: bool = False):
        super().__init__()
        self._task_fn = task_fn
        self._supports_progress = supports_progress

    def run(self):
        try:
            if self._supports_progress:
                result = self._task_fn(self.progress.emit)
            else:
                result = self._task_fn()
            if isinstance(result, tuple):
                self.finished.emit(result[0], result[1])
            else:
                self.finished.emit(result, "")
        except Exception as e:
            self.error.emit(str(e))


class _DetectWorker(QObject):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        try:
            code, name = detect_language(self._text)
            self.finished.emit(code, name)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Main Dialog
# ─────────────────────────────────────────────────────────────────────────────

class AITranslateDialog(QDialog):
    """Dialog dịch thuật tài liệu — đa ngôn ngữ, tự động nhận diện."""

    def __init__(self, parent, pdf_path: str, current_page: int = 1,
                 selected_text: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Dịch thuật tài liệu")
        self.setModal(True)
        self.setMinimumSize(720, 560)
        self.resize(800, 640)
        self.setStyleSheet(_style(is_dark()))

        self._pdf_path     = pdf_path
        self._current_page = current_page
        self._selected_text = selected_text or ""
        self._result_text  = ""
        self._thread       = None
        self._worker       = None
        self._detect_thread = None
        self._detect_worker = None
        self._detected_src  = ""

        self._build_ui()

        # Nếu có text đã chọn → chuyển sang tab "Đoạn văn bản" và điền vào
        if self._selected_text:
            self._tabs.setCurrentIndex(0)
            self._input_edit.setPlainText(self._selected_text)
            QTimer.singleShot(300, self._auto_detect_input)

    def _cleanup(self):
        if hasattr(self, "_progress"):
            self._progress.setRange(0, 100)
            self._progress.setVisible(False)
        if getattr(self, "_thread", None) and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(500)
        if getattr(self, "_detect_thread", None) and self._detect_thread.isRunning():
            self._detect_thread.quit()
            self._detect_thread.wait(500)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🌐 Dịch thuật")
        title.setObjectName("title")
        hdr.addWidget(title)
        hdr.addStretch()

        # Engine selector
        hdr.addWidget(QLabel("Engine:"))
        self._engine_combo = QComboBox()
        self._engine_combo.addItem("🤖 AI (Gemini/OpenAI/Claude)", "ai")
        self._engine_combo.addItem("🌐 Google Translate (miễn phí)", "google")
        self._engine_combo.addItem("💾 Từ điển Offline (Tải từ VPS)", "offline")
        hdr.addWidget(self._engine_combo)
        root.addLayout(hdr)

        # Language row
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)

        # Source language
        src_lbl = QLabel("Từ:")
        src_lbl.setObjectName("section")
        lang_row.addWidget(src_lbl)

        self._src_combo = QComboBox()
        self._src_combo.addItem("🔍 Tự động nhận diện", AUTO_DETECT)
        for code, name in SUPPORTED_LANGUAGES.items():
            self._src_combo.addItem(name, code)
        lang_row.addWidget(self._src_combo)

        # Detected indicator
        self._lbl_detected = QLabel("")
        self._lbl_detected.setObjectName("lang_detected")
        lang_row.addWidget(self._lbl_detected)

        # Swap button
        btn_swap = QPushButton("⇄")
        btn_swap.setFixedWidth(36)
        btn_swap.setToolTip("Đổi chiều dịch")
        btn_swap.clicked.connect(self._swap_languages)
        lang_row.addWidget(btn_swap)

        # Target language
        tgt_lbl = QLabel("Sang:")
        tgt_lbl.setObjectName("section")
        lang_row.addWidget(tgt_lbl)

        self._tgt_combo = QComboBox()
        for code, name in SUPPORTED_LANGUAGES.items():
            self._tgt_combo.addItem(name, code)
        # Mặc định: Tiếng Anh
        self._set_combo_by_code(self._tgt_combo, "en")
        lang_row.addWidget(self._tgt_combo)

        lang_row.addStretch()
        root.addLayout(lang_row)

        # Tabs
        self._tabs = QTabWidget()
        self._build_tab_text()
        self._build_tab_page()
        self._build_tab_document()
        root.addWidget(self._tabs)

        # Status + Progress
        self._lbl_status = QLabel("Sẵn sàng.")
        self._lbl_status.setObjectName("status")
        root.addWidget(self._lbl_status)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Bottom buttons
        div = QFrame()
        div.setObjectName("divider")
        root.addWidget(div)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        btn_row.addStretch()

        self._btn_save = QPushButton("💾 Lưu bản dịch")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self._btn_save)

        self._btn_copy = QPushButton("📋 Sao chép")
        self._btn_copy.setEnabled(False)
        self._btn_copy.clicked.connect(self._on_copy)
        btn_row.addWidget(self._btn_copy)

        self._btn_tts = QPushButton("Read Aloud")
        self._btn_tts.setEnabled(False)
        self._btn_tts.clicked.connect(self._on_tts)
        btn_row.addWidget(self._btn_tts)

        root.addLayout(btn_row)

    def _build_tab_text(self):
        """Tab 1: Dịch đoạn văn bản nhập tay."""
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setSpacing(6)

        lbl = QLabel("NHẬP / DÁN VĂN BẢN CẦN DỊCH")
        lbl.setObjectName("section")
        lay.addWidget(lbl)

        self._input_edit = QTextEdit()
        self._input_edit.setPlaceholderText(
            "Dán văn bản cần dịch vào đây…\n"
            "Hỗ trợ nhiều ngôn ngữ. Chọn 'Tự động nhận diện' để phát hiện tự động."
        )
        self._input_edit.setMinimumHeight(120)
        self._input_edit.textChanged.connect(self._on_input_changed)
        lay.addWidget(self._input_edit, 1)

        lbl2 = QLabel("KẾT QUẢ DỊCH")
        lbl2.setObjectName("section")
        lay.addWidget(lbl2)

        self._text_result = QTextEdit()
        self._text_result.setReadOnly(True)
        self._text_result.setPlaceholderText("Bản dịch sẽ xuất hiện ở đây…")
        self._text_result.setMinimumHeight(120)
        lay.addWidget(self._text_result, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_detect = QPushButton("🔍 Nhận diện ngôn ngữ")
        self._btn_detect.clicked.connect(self._auto_detect_input)
        btn_row.addWidget(self._btn_detect)

        btn_translate = QPushButton("🚀 Dịch ngay")
        btn_translate.setObjectName("btn_primary")
        btn_translate.clicked.connect(lambda: self._do_translate_text(""))
        btn_row.addWidget(btn_translate)
        lay.addLayout(btn_row)

        self._tabs.addTab(tab, "✏️ Đoạn văn bản")

    def _build_tab_page(self):
        """Tab 2: Dịch trang PDF hiện tại."""
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setSpacing(6)

        page_row = QHBoxLayout()
        page_row.addWidget(QLabel("Dịch trang số:"))
        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setMaximum(9999)
        self._page_spin.setValue(self._current_page)
        page_row.addWidget(self._page_spin)
        page_row.addStretch()
        lay.addLayout(page_row)

        lbl = QLabel("KẾT QUẢ DỊCH TRANG")
        lbl.setObjectName("section")
        lay.addWidget(lbl)

        self._page_result = QTextEdit()
        self._page_result.setReadOnly(True)
        self._page_result.setPlaceholderText("Bản dịch trang sẽ xuất hiện ở đây…")
        lay.addWidget(self._page_result, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_translate = QPushButton("🚀 Dịch trang này")
        btn_translate.setObjectName("btn_primary")
        btn_translate.clicked.connect(lambda: self._do_translate_page(""))
        btn_row.addWidget(btn_translate)
        lay.addLayout(btn_row)

        self._tabs.addTab(tab, "📄 Trang hiện tại")

    def _build_tab_document(self):
        """Tab 3: Dịch toàn bộ tài liệu."""
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setSpacing(8)

        range_row = QHBoxLayout()
        self._chk_all = QCheckBox("Dịch tất cả các trang")
        self._chk_all.setChecked(True)
        self._chk_all.toggled.connect(self._on_range_toggle)
        range_row.addWidget(self._chk_all)

        range_row.addWidget(QLabel("  Từ trang:"))
        self._from_spin = QSpinBox()
        self._from_spin.setMinimum(1)
        self._from_spin.setMaximum(9999)
        self._from_spin.setValue(1)
        self._from_spin.setEnabled(False)
        range_row.addWidget(self._from_spin)

        range_row.addWidget(QLabel("đến trang:"))
        self._to_spin = QSpinBox()
        self._to_spin.setMinimum(1)
        self._to_spin.setMaximum(9999)
        self._to_spin.setValue(self._current_page)
        self._to_spin.setEnabled(False)
        range_row.addWidget(self._to_spin)
        range_row.addStretch()
        lay.addLayout(range_row)

        lbl = QLabel("KẾT QUẢ DỊCH TOÀN TÀI LIỆU")
        lbl.setObjectName("section")
        lay.addWidget(lbl)

        self._doc_result = QTextEdit()
        self._doc_result.setReadOnly(True)
        self._doc_result.setPlaceholderText(
            "Bản dịch toàn bộ tài liệu sẽ xuất hiện ở đây…\n"
            "Mỗi trang sẽ được phân cách bằng dấu ═══"
        )
        lay.addWidget(self._doc_result, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_export = QPushButton("📄 Lưu ra file .txt")
        btn_export.clicked.connect(self._export_document)
        btn_row.addWidget(btn_export)

        btn_translate = QPushButton("🚀 Dịch toàn tài liệu")
        btn_translate.setObjectName("btn_primary")
        btn_translate.clicked.connect(lambda: self._do_translate_document(""))
        btn_row.addWidget(btn_translate)
        lay.addLayout(btn_row)

        self._tabs.addTab(tab, "📚 Toàn tài liệu")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_combo_by_code(self, combo: QComboBox, code: str):
        for i in range(combo.count()):
            if combo.itemData(i) == code:
                combo.setCurrentIndex(i)
                return

    def _get_src(self) -> str:
        return self._src_combo.currentData() or AUTO_DETECT

    def _get_tgt(self) -> str:
        return self._tgt_combo.currentData() or "en"

    def _swap_languages(self):
        """Đổi chiều: src ↔ tgt (bỏ qua nếu src=auto)."""
        src = self._get_src()
        tgt = self._get_tgt()
        if src == AUTO_DETECT:
            # Nếu đã nhận diện được → đổi bằng mã thực
            if self._detected_src:
                self._set_combo_by_code(self._src_combo, tgt)
                self._set_combo_by_code(self._tgt_combo, self._detected_src)
        else:
            self._set_combo_by_code(self._src_combo, tgt)
            self._set_combo_by_code(self._tgt_combo, src)

    def _active_result_widget(self) -> QTextEdit:
        idx = self._tabs.currentIndex()
        if idx == 0:
            return self._text_result
        elif idx == 1:
            return self._page_result
        return self._doc_result

    def _set_status(self, msg: str, color: str = ""):
        self._lbl_status.setText(msg)
        if color:
            self._lbl_status.setStyleSheet(f"color:{color}; font-size:11px;")
        else:
            self._lbl_status.setStyleSheet("")

    def _set_busy(self, busy: bool):
        self._progress.setVisible(busy)
        if busy:
            self._progress.setRange(0, 0)
        self._btn_save.setEnabled(not busy and bool(self._result_text))
        self._btn_copy.setEnabled(not busy and bool(self._result_text))
        self._btn_tts.setEnabled(not busy and bool(self._result_text))

    def _on_range_toggle(self, all_pages: bool):
        self._from_spin.setEnabled(not all_pages)
        self._to_spin.setEnabled(not all_pages)

    def _on_input_changed(self):
        self._lbl_detected.setText("")
        self._detected_src = ""

    # ── Language Detection ────────────────────────────────────────────────────

    def _auto_detect_input(self):
        text = self._input_edit.toPlainText().strip()
        if not text:
            return
        if self._detect_thread and self._detect_thread.isRunning():
            return
        self._lbl_detected.setText("Dang nhan dien...")
        self._btn_detect.setEnabled(False)
        self._detect_thread = QThread()
        self._detect_worker = _DetectWorker(text)
        self._detect_worker.moveToThread(self._detect_thread)
        self._detect_thread.started.connect(self._detect_worker.run)
        self._detect_worker.finished.connect(self._on_detect_done)
        self._detect_worker.error.connect(self._on_detect_error)
        self._detect_worker.finished.connect(self._detect_thread.quit)
        self._detect_worker.error.connect(self._detect_thread.quit)
        self._detect_thread.finished.connect(self._detect_thread.deleteLater)
        self._detect_thread.start()

    # Translate actions

    def _do_translate_text(self, engine_override: str = ""):
        text = self._input_edit.toPlainText().strip()
        if not text:
            self._set_status("Hãy nhập văn bản cần dịch.", "#E05050")
            return

        engine = engine_override or self._engine_combo.currentData()
        src = self._get_src()
        tgt = self._get_tgt()

        self._text_result.setPlainText("Đang dịch…")
        self._set_busy(True)
        self._set_status(f"Đang dịch bằng {engine.upper()}…")

        def _task():
            return translate_text(text, src, tgt, engine)

        self._run_task(_task, self._text_result)

    def _do_translate_page(self, engine_override: str = ""):
        if not self._pdf_path:
            self._set_status("Chưa mở tệp PDF.", "#E05050")
            return

        engine = engine_override or self._engine_combo.currentData()
        page = self._page_spin.value()
        src = self._get_src()
        tgt = self._get_tgt()

        self._page_result.setPlainText("Đang trích xuất và dịch trang…")
        self._set_busy(True)
        self._set_status(f"Đang dịch trang {page} bằng {engine.upper()}…")

        def _task():
            from packages.ai.translate import _extract_page_text, translate_text as _tt
            text, err = _extract_page_text(self._pdf_path, page)
            if err:
                return TranslationResult(
                    original="", translated="", source_lang=src,
                    target_lang=tgt, engine=engine, error=err
                ), src
            if not text:
                return TranslationResult(
                    original="", translated="", source_lang=src,
                    target_lang=tgt, engine=engine,
                    error="Trang không có văn bản (PDF ảnh — dùng OCR trước)."
                ), src
            return _tt(text, src, tgt, engine)

        self._run_task(_task, self._page_result)

    def _do_translate_document(self, engine_override: str = ""):
        if not self._pdf_path:
            self._set_status("Chưa mở tệp PDF.", "#E05050")
            return

        engine = engine_override or self._engine_combo.currentData()
        src = self._get_src()
        tgt = self._get_tgt()
        all_pages = self._chk_all.isChecked()
        page_range = None if all_pages else (self._from_spin.value(), self._to_spin.value())

        self._doc_result.setPlainText("Đang dịch toàn tài liệu…")
        self._set_busy(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._set_status("Đang khởi động dịch toàn tài liệu…")

        def _task(progress_signal):
            from packages.ai.translate import translate_pdf_document as _tpd
            doc_result = _tpd(
                self._pdf_path, src, tgt, engine,
                page_range=page_range,
                progress_callback=progress_signal,
            )
            # Gộp kết quả thành một TranslationResult
            combined = TranslationResult(
                original="", translated=doc_result.full_text,
                source_lang=src, target_lang=tgt, engine=engine,
                error=None if doc_result.success else "Một số trang dịch thất bại."
            )
            return combined, src

        self._run_task(_task, self._doc_result, supports_progress=True)

    def _run_task(self, task_fn, result_widget: QTextEdit, supports_progress: bool = False):
        """Chạy task trong thread riêng, cập nhật result_widget khi xong."""
        if ((self._thread and self._thread.isRunning()) or (self._detect_thread and self._detect_thread.isRunning())):
            self._set_status("Đang có tác vụ dịch khác chạy, vui lòng chờ.", "#E05050")
            return

        self._current_target_widget = result_widget
        self._thread = QThread()
        self._worker = _TranslateWorker(task_fn, supports_progress=supports_progress)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_detect_done(self, code: str, name: str):
        self._detected_src = code
        self._lbl_detected.setText(f"Detected: {name}")
        self._btn_detect.setEnabled(True)
        self._detect_thread = None
        self._detect_worker = None

    def _on_detect_error(self, msg: str):
        self._lbl_detected.setText(f"Detect failed: {msg}")
        self._btn_detect.setEnabled(True)
        self._detect_thread = None
        self._detect_worker = None

    def _on_worker_progress(self, current: int, total: int, status: str):
        pct = int(current * 100 / max(total, 1))
        self._progress.setValue(pct)
        self._set_status(status)

    def _on_done(self, result: TranslationResult, actual_src: str):
        widget = getattr(self, "_current_target_widget", self._active_result_widget())
        self._set_busy(False)
        self._progress.setVisible(False)

        if actual_src and actual_src != AUTO_DETECT:
            self._detected_src = actual_src
            src_name = SUPPORTED_LANGUAGES.get(actual_src, actual_src.upper())
            self._lbl_detected.setText(f"✅ Ngôn ngữ phát hiện: {src_name}")

        if result and result.success:
            self._result_text = result.translated
            widget.setPlainText(self._result_text)
            tgt_name = SUPPORTED_LANGUAGES.get(result.target_lang, result.target_lang)
            if result.engine == "ai":
                engine_name = "AI"
            elif result.engine == "offline":
                engine_name = "Offline VPS"
            else:
                engine_name = "Google Translate"
            self._set_status(f"✅ Dịch hoàn thành ({engine_name} → {tgt_name})", "#4FC080")
            self._btn_save.setEnabled(True)
            self._btn_copy.setEnabled(True)
            self._btn_tts.setEnabled(True)
        else:
            err = result.error if result else "Lỗi không xác định"
            widget.setPlainText(f"❌ Lỗi: {err}")
            self._set_status(f"Lỗi: {err}", "#E05050")

    def _on_error(self, msg: str):
        self._set_busy(False)
        self._active_result_widget().setPlainText(f"❌ Lỗi: {msg}")
        self._set_status(f"Lỗi: {msg}", "#E05050")

    # ── Save / Copy ───────────────────────────────────────────────────────────

    def _on_copy(self):
        if not self._result_text:
            return
        from packages.qt_compat.QtWidgets import QApplication
        QApplication.clipboard().setText(self._result_text)
        self._lbl_status.setText("Copied to Clipboard!")
        orig = self._btn_copy.text()
        self._btn_copy.setText("✅ Đã sao chép!")
        QTimer.singleShot(1500, lambda: self._btn_copy.setText(orig))

    def _on_tts(self):
        if not self._result_text:
            return
        from app.actions.tts_dialog import TTSDialog
        dlg = TTSDialog(self, page_text=self._result_text, selected_text=self._result_text)
        dlg.exec()

    def _on_save(self):
        if not self._result_text:
            return
        base = os.path.splitext(os.path.basename(self._pdf_path or "document"))[0]
        tgt = self._get_tgt()
        default_name = f"{base}_dichthuat_{tgt}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu bản dịch",
            os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "Text files (*.txt);;All files (*)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._result_text)
            orig = self._btn_save.text()
            self._btn_save.setText("✅ Đã lưu!")
            QTimer.singleShot(1500, lambda: self._btn_save.setText(orig))

    def _export_document(self):
        """Xuất bản dịch toàn tài liệu ra file."""
        text = self._doc_result.toPlainText().strip()
        if not text or text.startswith("Đang") or text.startswith("❌"):
            QMessageBox.information(self, "Thông báo", "Chưa có bản dịch để lưu.")
            return
        self._result_text = text
        self._on_save()

    def closeEvent(self, event):
        self._cleanup()
        if ((self._thread and self._thread.isRunning()) or (self._detect_thread and self._detect_thread.isRunning())):
            self._set_status("Đang chờ hoàn tất. Đóng lại sau khi xong.", "#E05050")
            event.ignore()
            return
        super().closeEvent(event)

    def reject(self):
        self._cleanup()
        super().reject()
