"""Welcome screen shown when no PDF is open."""
from __future__ import annotations

import os

from packages.qt_compat.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from packages.qt_compat.QtCore import Qt, QSize, QEvent
from packages.qt_compat.QtSvgWidgets import QSvgWidget

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


class WelcomeWidget(QWidget):
    """Landing page shown on the empty tab before any PDF is opened."""

    def __init__(self, parent=None, *, on_open=None, on_recent=None):
        super().__init__(parent)
        self._on_open = on_open
        self._on_recent = on_recent
        self._cards: list[QFrame] = []
        self._card_title_labels: list[QLabel] = []
        self._card_desc_labels: list[QLabel] = []
        self._setup_ui()

    # ── Theme-aware re-styling ──────────────────────────────────────────────

    def changeEvent(self, event: QEvent):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._apply_theme_styles()

    def _is_dark(self) -> bool:
        try:
            from styles.theme import is_dark
            return is_dark()
        except Exception:
            return True

    def _apply_theme_styles(self):
        dark = self._is_dark()
        if dark:
            card_bg     = "#1A1A2E"
            card_border = "#2A2A48"
            title_color = "#C8D8F8"
            desc_color  = "#5577AA"
            hint_color  = "#3A4F6A"
            tag_color   = "#5577BB"
        else:
            card_bg     = "#F0F2FA"
            card_border = "#D0D5EC"
            title_color = "#0D1E6A"
            desc_color  = "#4466AA"
            hint_color  = "#8899BB"
            tag_color   = "#4466AA"

        card_style = (
            f"QFrame {{ background:{card_bg}; border:1px solid {card_border};"
            f"  border-radius:12px; }}"
        )
        for card in self._cards:
            card.setStyleSheet(card_style)
        for lbl in self._card_title_labels:
            lbl.setStyleSheet(
                f"font-size:12px; font-weight:700; color:{title_color};"
                "background:transparent; border:none;"
            )
        for lbl in self._card_desc_labels:
            lbl.setStyleSheet(
                f"font-size:10px; color:{desc_color}; background:transparent; border:none;"
            )
        if hasattr(self, "_hint_lbl"):
            self._hint_lbl.setStyleSheet(f"color:{hint_color}; font-size:11px;")
        if hasattr(self, "_tag_lbl"):
            self._tag_lbl.setStyleSheet(
                f"color:{tag_color}; font-size:12px; letter-spacing:3px; font-weight:600;"
            )
        # WelcomeTitle (READER)
        from packages.qt_compat.QtWidgets import QApplication
        for w in self.findChildren(type(self._tag_lbl)):
            if w.objectName() == "WelcomeTitle":
                reader_color = "#E8F0FF" if dark else "#1A2880"
                w.setStyleSheet(
                    f"font-size:46px; font-weight:700; color:{reader_color};"
                    "background:transparent; border:none; letter-spacing:2px;"
                )

    # ── UI build ───────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.setSpacing(0)
        root.setContentsMargins(40, 48, 40, 40)

        # Tiêu đề text thuần
        self._logo_widget = None
        title_row = QHBoxLayout()
        title_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_3t = QLabel("3T")
        lbl_3t.setStyleSheet(
            "font-size:46px; font-weight:900; color:#FF7700;"
            "background:transparent; border:none; letter-spacing:2px;"
        )
        lbl_3t.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_reader = QLabel(" READER")
        lbl_reader.setObjectName("WelcomeTitle")
        lbl_reader.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_row.addStretch()
        title_row.addWidget(lbl_3t)
        title_row.addWidget(lbl_reader)
        title_row.addStretch()
        root.addLayout(title_row)

        root.addSpacing(10)

        # Tagline
        self._tag_lbl = QLabel("ĐỌC MỌI LÚC  ·  HIỂU MỌI NƠI")
        self._tag_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._tag_lbl)

        root.addSpacing(40)

        # Feature cards
        features = [
            ("📖", "Đọc PDF mượt mà",    "Hỗ trợ file lớn, xem toàn trang"),
            ("✏️", "Chỉnh sửa trực tiếp", "Chèn text, ảnh, vẽ, tô sáng"),
            ("🔏", "Ký số USB Token",     "Viettel CA, VNPT CA, FPT CA"),
            ("🔒", "Bảo mật cao",         "Mã hoá, che nội dung nhạy cảm"),
        ]
        pills_row = QHBoxLayout()
        pills_row.setSpacing(16)
        pills_row.addStretch()
        for icon, title_txt, desc in features:
            card = QFrame()
            card.setFixedWidth(158)
            self._cards.append(card)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(6)
            card_layout.setContentsMargins(12, 14, 12, 14)

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(
                "font-size:26px; background:transparent; border:none;"
            )
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(icon_lbl)

            title_lbl = QLabel(title_txt)
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_lbl.setWordWrap(True)
            self._card_title_labels.append(title_lbl)
            card_layout.addWidget(title_lbl)

            desc_lbl = QLabel(desc)
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_lbl.setWordWrap(True)
            self._card_desc_labels.append(desc_lbl)
            card_layout.addWidget(desc_lbl)

            pills_row.addWidget(card)
        pills_row.addStretch()
        root.addLayout(pills_row)

        root.addSpacing(44)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.addStretch()

        btn_open = QPushButton("   Mở tệp PDF   ")
        btn_open.setFixedHeight(44)
        btn_open.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 #FF7700, stop:1 #FF4400); color:white; font-size:14px;"
            "  font-weight:700; border-radius:8px; padding:0 28px; border:none; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 #FF9900, stop:1 #FF5500); }"
            "QPushButton:pressed { background:#FF4400; }"
        )
        if self._on_open:
            btn_open.clicked.connect(self._on_open)
        btn_row.addWidget(btn_open)

        btn_recent = QPushButton("   Mở gần đây   ")
        btn_recent.setFixedHeight(44)
        btn_recent.setStyleSheet(
            "QPushButton { background:transparent; color:#FF7700; font-size:14px;"
            "  font-weight:700; border-radius:8px; padding:0 28px;"
            "  border:2px solid #FF7700; }"
            "QPushButton:hover { background:rgba(255,119,0,0.1); }"
            "QPushButton:pressed { background:rgba(255,119,0,0.2); }"
        )
        if self._on_recent:
            btn_recent.clicked.connect(self._on_recent)
        btn_row.addWidget(btn_recent)

        btn_row.addStretch()
        root.addLayout(btn_row)

        root.addSpacing(20)

        # Hint
        self._hint_lbl = QLabel("hoặc kéo & thả tệp PDF vào cửa sổ này")
        self._hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._hint_lbl)

        # Apply initial styles
        self._apply_theme_styles()
