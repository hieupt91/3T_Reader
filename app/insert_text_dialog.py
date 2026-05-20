from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QSpinBox, QTextEdit, QComboBox,
    QDialogButtonBox, QColorDialog, QFontComboBox, QWidget,
)
from packages.qt_compat.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from packages.qt_compat.QtCore import Qt


class InsertTextDialog(QDialog):
    """Dialog chèn văn bản với lựa chọn font, cỡ chữ, màu, bold/italic."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chèn văn bản vào PDF")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._color = QColor(0, 0, 0)
        self._setup_ui()
        self.adjustSize()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Hàng 1: Font + Cỡ chữ ─────────────────────────────────────────
        row1 = QHBoxLayout()

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Helvetica"))
        self.font_combo.setMaximumWidth(200)
        row1.addWidget(QLabel("Font:"))
        row1.addWidget(self.font_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 96)
        self.size_spin.setValue(12)
        self.size_spin.setSuffix(" pt")
        self.size_spin.setFixedWidth(72)
        row1.addWidget(QLabel("Cỡ:"))
        row1.addWidget(self.size_spin)

        row1.addStretch()
        layout.addLayout(row1)

        # ── Hàng 2: Bold / Italic / Màu ───────────────────────────────────
        row2 = QHBoxLayout()

        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setFixedSize(32, 32)
        self.btn_bold.setFont(QFont("", 10, QFont.Weight.Bold))
        self.btn_bold.setToolTip("In đậm")

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedSize(32, 32)
        f = QFont("", 10)
        f.setItalic(True)
        self.btn_italic.setFont(f)
        self.btn_italic.setToolTip("In nghiêng")

        self.color_btn = QPushButton("  Màu chữ")
        self.color_btn.setFixedHeight(32)
        self.color_btn.setToolTip("Chọn màu chữ")
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()

        row2.addWidget(self.btn_bold)
        row2.addWidget(self.btn_italic)
        row2.addSpacing(8)
        row2.addWidget(self.color_btn)
        row2.addStretch()
        layout.addLayout(row2)

        # ── Vùng nhập text ─────────────────────────────────────────────────
        layout.addWidget(QLabel("Nội dung:"))
        self.text_edit = QTextEdit()
        self.text_edit.setMinimumHeight(120)
        self.text_edit.setPlaceholderText("Nhập nội dung cần chèn vào PDF...")
        layout.addWidget(self.text_edit)

        # ── Hướng dẫn ─────────────────────────────────────────────────────
        hint = QLabel("Sau khi nhấn OK → click vào vị trí trên PDF để đặt văn bản.")
        hint.setStyleSheet("color: #8888aa; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ── Buttons ────────────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Chọn màu chữ")
        if c.isValid():
            self._color = c
            self._update_color_btn()

    def _update_color_btn(self):
        c = self._color
        luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        text_color = "#000" if luma > 128 else "#fff"
        self.color_btn.setStyleSheet(
            f"background:{c.name()}; color:{text_color}; border-radius:4px; padding:0 8px;"
        )

    def _on_accept(self):
        if self.text_edit.toPlainText().strip():
            self.accept()

    # ── Public getters ─────────────────────────────────────────────────────

    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def get_font_size(self) -> int:
        return self.size_spin.value()

    def get_font_name(self) -> str:
        return self.font_combo.currentFont().family()

    def get_color_tuple(self) -> tuple[float, float, float]:
        c = self._color
        return (c.red() / 255.0, c.green() / 255.0, c.blue() / 255.0)

    def is_bold(self) -> bool:
        return self.btn_bold.isChecked()

    def is_italic(self) -> bool:
        return self.btn_italic.isChecked()
