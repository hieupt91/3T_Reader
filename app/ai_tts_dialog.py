"""Dialog đọc văn bản (Text-to-Speech) — native macOS `say`.

Đọc to nội dung trang PDF hiện tại. Người dùng có thể chỉnh văn bản trước
khi đọc, chọn giọng và tốc độ. Phát/Dừng qua tiến trình `say`; hoàn tất được
phát hiện bằng QTimer poll trên main thread (không dùng worker thread → không
có rủi ro GUI cross-thread).
"""
from __future__ import annotations

from packages.qt_compat.QtCore import Qt, QTimer
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QComboBox, QSlider, QSizePolicy,
)

from packages.tts import (
    is_available, list_voices, start_speaking, stop_speaking,
)

_STYLE = """
QDialog { background: #16162A; }
QLabel#title  { color: #E8EEFF; font-size: 15px; font-weight: 700; }
QLabel#status { color: #8080B0; font-size: 11px; }
QLabel#lbl    { color: #C0C8F0; font-size: 12px; }
QTextEdit {
    background: #1A1A2E;
    color: #D0D8F8;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    font-size: 13px;
    padding: 10px;
    line-height: 1.5;
}
QComboBox {
    background: #1E1E38; color: #E0E8FF;
    border: 1px solid #3A3A60; border-radius: 7px;
    padding: 6px 10px; font-size: 12px; min-width: 180px;
}
QComboBox:hover { border-color: #6060C0; }
QSlider::groove:horizontal { height: 4px; background: #2A2A4A; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 14px; margin: -6px 0; border-radius: 7px;
    background: #5b4fd4;
}
QPushButton {
    background: #1E1E38; color: #B0B8E0;
    border: 1px solid #3A3A60; border-radius: 7px;
    padding: 8px 18px; font-size: 12px; font-weight: 600;
}
QPushButton:hover  { background: #2A2A50; border-color: #6060C0; }
QPushButton:disabled { color: #444466; border-color: #2A2A44; }
QPushButton#btn_play {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3b6fd4,stop:1 #5b4fd4);
    color: white; border: none;
}
QPushButton#btn_play:hover { background: #4b7fe4; }
QFrame#divider { background: #2A2A4A; }
"""

_RATE_MIN = 120
_RATE_MAX = 320
_RATE_DEFAULT = 180


def _extract_page_text(pdf_path: str, page_no: int) -> str:
    """Trích text trang hiện tại qua pypdfium2, có PDFIUM_LOCK."""
    import pypdfium2 as pdfium
    from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_path)
        try:
            page = doc[page_no - 1]
            textpage = page.get_textpage()
            return (textpage.get_text_range() or "").strip()
        finally:
            doc.close()


class AITTSDialog(QDialog):
    """Dialog đọc to trang PDF hiện tại bằng giọng hệ thống macOS."""

    def __init__(self, parent, pdf_path: str, current_page: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Đọc văn bản")
        self.setModal(False)
        self.setMinimumWidth(600)
        self.resize(660, 540)
        self.setStyleSheet(_STYLE)

        self._pdf_path = pdf_path
        self._current_page = current_page
        self._proc = None

        # Poll timer phát hiện `say` chạy xong (trên main thread)
        self._poll = QTimer(self)
        self._poll.setInterval(300)
        self._poll.timeout.connect(self._check_finished)

        self._build_ui()
        self._load_page_text()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel(f"Đọc văn bản — Trang {self._current_page}")
        title.setObjectName("title")
        root.addWidget(title)

        # Voice + rate controls
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(12)

        lbl_voice = QLabel("Giọng:")
        lbl_voice.setObjectName("lbl")
        self._combo_voice = QComboBox()
        self._populate_voices()

        lbl_rate = QLabel("Tốc độ:")
        lbl_rate.setObjectName("lbl")
        self._slider_rate = QSlider(Qt.Orientation.Horizontal)
        self._slider_rate.setMinimum(_RATE_MIN)
        self._slider_rate.setMaximum(_RATE_MAX)
        self._slider_rate.setValue(_RATE_DEFAULT)
        self._slider_rate.setFixedWidth(140)
        self._lbl_rate_val = QLabel(f"{_RATE_DEFAULT} wpm")
        self._lbl_rate_val.setObjectName("status")
        self._slider_rate.valueChanged.connect(
            lambda v: self._lbl_rate_val.setText(f"{v} wpm")
        )

        ctrl_row.addWidget(lbl_voice)
        ctrl_row.addWidget(self._combo_voice)
        ctrl_row.addStretch()
        ctrl_row.addWidget(lbl_rate)
        ctrl_row.addWidget(self._slider_rate)
        ctrl_row.addWidget(self._lbl_rate_val)
        root.addLayout(ctrl_row)

        # Status
        self._lbl_status = QLabel("Sẵn sàng đọc.")
        self._lbl_status.setObjectName("status")
        root.addWidget(self._lbl_status)

        # Editable text
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Nội dung trang sẽ hiện ở đây…")
        self._text_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._text_edit)

        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        root.addWidget(div)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_close = QPushButton("Đóng")
        self._btn_close.clicked.connect(self.reject)

        self._btn_stop = QPushButton("Dừng")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)

        self._btn_play = QPushButton("▶  Đọc")
        self._btn_play.setObjectName("btn_play")
        self._btn_play.clicked.connect(self._on_play)

        btn_row.addWidget(self._btn_close)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_stop)
        btn_row.addWidget(self._btn_play)
        root.addLayout(btn_row)

        if not is_available():
            self._btn_play.setEnabled(False)
            self._lbl_status.setText(
                "Đọc văn bản chỉ hỗ trợ trên macOS (dùng lệnh hệ thống `say`)."
            )

    def _populate_voices(self):
        self._combo_voice.addItem("Mặc định hệ thống", None)
        for v in list_voices():
            self._combo_voice.addItem(v.label, v.name)

    def _load_page_text(self):
        try:
            text = _extract_page_text(self._pdf_path, self._current_page)
        except Exception as e:
            text = ""
            self._lbl_status.setText(f"Không đọc được nội dung trang: {e}")
        if text:
            self._text_edit.setPlainText(text)
        else:
            self._text_edit.setPlaceholderText(
                "Trang này không có văn bản trích được (có thể là ảnh scan)."
            )

    # ── Playback ──────────────────────────────────────────────────────────
    def _on_play(self):
        text = self._text_edit.toPlainText().strip()
        if not text:
            self._lbl_status.setText("Không có văn bản để đọc.")
            return

        # Nếu đang đọc thì dừng phiên cũ trước
        self._on_stop()

        voice = self._combo_voice.currentData()
        rate = self._slider_rate.value()
        try:
            self._proc = start_speaking(text, voice=voice, rate_wpm=rate)
        except Exception as e:
            self._lbl_status.setStyleSheet("color:#E05050;font-size:11px")
            self._lbl_status.setText(f"Lỗi: {e}")
            return

        self._btn_play.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._lbl_status.setStyleSheet("color:#4fc080;font-size:11px")
        self._lbl_status.setText("Đang đọc…")
        self._poll.start()

    def _on_stop(self):
        self._poll.stop()
        stop_speaking(self._proc)
        self._proc = None
        self._reset_idle("Đã dừng.")

    def _check_finished(self):
        if self._proc is None or self._proc.poll() is not None:
            self._poll.stop()
            self._proc = None
            self._reset_idle("Đọc xong.")

    def _reset_idle(self, msg: str):
        self._btn_play.setEnabled(is_available())
        self._btn_stop.setEnabled(False)
        self._lbl_status.setStyleSheet("color:#8080B0;font-size:11px")
        self._lbl_status.setText(msg)

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def set_pdf(self, pdf_path: str, current_page: int = 1):
        """Đổi tài liệu/trang khi user chuyển tab mà vẫn giữ dialog mở."""
        self._on_stop()
        self._pdf_path = pdf_path
        self._current_page = current_page
        self._load_page_text()

    def reject(self):
        self._on_stop()
        super().reject()

    def closeEvent(self, event):
        self._on_stop()
        super().closeEvent(event)
