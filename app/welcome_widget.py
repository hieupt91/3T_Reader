"""Welcome screen shown when no PDF is open."""
from __future__ import annotations

import os

from packages.qt_compat.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from packages.qt_compat.QtCore import Qt, QSize, QEvent, QUrl
from packages.qt_compat.QtGui import QDesktopServices
from packages.qt_compat.QtSvgWidgets import QSvgWidget
from packages.platform.recent import load_recent
from app.version import APP_VERSION
from app.icon_utils import svg_icon

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_ROOT = os.path.dirname(os.path.dirname(__file__))


class WelcomeWidget(QWidget):
    """Landing page shown on the empty tab before any PDF is opened."""

    def __init__(self, parent=None, *, on_open=None, on_new=None, on_recent=None, on_recent_file=None):
        super().__init__(parent)
        self._on_open = on_open
        self._on_new = on_new
        self._on_recent = on_recent
        self._on_recent_file = on_recent_file
        self._cards: list[QFrame] = []
        self._card_title_labels: list[QLabel] = []
        self._card_desc_labels: list[QLabel] = []
        self._secondary_labels: list[QLabel] = []
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
        for lbl in self._secondary_labels:
            lbl.setStyleSheet(
                f"font-size:11px; color:{desc_color}; background:transparent; border:none;"
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
            ("folder_open.svg", "#60A5FA", "Đọc PDF mượt mà", "Hỗ trợ file lớn, xem toàn trang"),
            ("edit_object.svg", "#FF6B3D", "Chỉnh sửa trực tiếp", "Chèn text, ảnh, vẽ, tô sáng"),
            ("usb.svg", "#F59E0B", "Ký số USB Token", "Viettel CA, VNPT CA, FPT CA"),
            ("signature_check.svg", "#F59E0B", "Bảo mật cao", "Mã hoá, che nội dung nhạy cảm"),
        ]
        pills_row = QHBoxLayout()
        pills_row.setSpacing(16)
        pills_row.addStretch()
        for icon_file, icon_color, title_txt, desc in features:
            card = QFrame()
            card.setFixedSize(164, 96)
            self._cards.append(card)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)
            card_layout.setContentsMargins(12, 10, 12, 10)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(svg_icon(icon_file, size=24, color=icon_color).pixmap(QSize(24, 24)))
            icon_lbl.setStyleSheet(
                "background:transparent; border:none;"
            )
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(icon_lbl)

            title_lbl = QLabel(title_txt)
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_lbl.setWordWrap(True)
            title_lbl.setFixedHeight(28)
            self._card_title_labels.append(title_lbl)
            card_layout.addWidget(title_lbl)

            desc_lbl = QLabel(desc)
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_lbl.setWordWrap(True)
            desc_lbl.setFixedHeight(28)
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

        btn_new = QPushButton("   Tạo PDF mới   ")
        btn_new.setFixedHeight(44)
        btn_new.setStyleSheet(
            "QPushButton { background:transparent; color:#4FC080; font-size:14px;"
            "  font-weight:700; border-radius:8px; padding:0 24px;"
            "  border:2px solid #4FC080; }"
            "QPushButton:hover { background:rgba(79,192,128,0.1); }"
            "QPushButton:pressed { background:rgba(79,192,128,0.2); }"
        )
        if self._on_new:
            btn_new.clicked.connect(self._on_new)
        btn_row.addWidget(btn_new)

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

        root.addSpacing(18)

        recent_title = QLabel("Tệp gần đây")
        recent_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._secondary_labels.append(recent_title)
        root.addWidget(recent_title)

        recent_row = QHBoxLayout()
        recent_row.setSpacing(8)
        recent_row.addStretch()
        for path in self._recent_files():
            btn = QPushButton(os.path.basename(path))
            btn.setFixedHeight(30)
            btn.setMaximumWidth(180)
            btn.setToolTip(path)
            btn.setStyleSheet(
                "QPushButton { background:transparent; color:#C8D8F8; font-size:11px;"
                " border:1px solid #3A4F6A; border-radius:6px; padding:0 10px; }"
                "QPushButton:hover { border-color:#FF7700; color:#FF7700; }"
            )
            btn.clicked.connect(lambda _checked=False, p=path: self._open_recent_file(p))
            recent_row.addWidget(btn)
        if recent_row.count() == 1:
            empty = QLabel("Chưa có tệp gần đây")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._secondary_labels.append(empty)
            recent_row.addWidget(empty)
        recent_row.addStretch()
        root.addLayout(recent_row)

        root.addSpacing(16)

        meta_row = QHBoxLayout()
        meta_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta_row.setSpacing(12)
        version_lbl = QLabel(f"Phiên bản {APP_VERSION}")
        self._secondary_labels.append(version_lbl)
        meta_row.addWidget(version_lbl)

        whats_new = QPushButton("Có gì mới")
        whats_new.setFixedHeight(28)
        whats_new.setStyleSheet(
            "QPushButton { background:transparent; color:#FF7700; border:none;"
            " font-size:11px; font-weight:700; padding:0 8px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        whats_new.clicked.connect(self._open_whats_new)
        meta_row.addWidget(whats_new)
        root.addLayout(meta_row)

        # Hint
        self._hint_lbl = QLabel("hoặc kéo & thả tệp PDF vào cửa sổ này")
        self._hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._hint_lbl)

        # Apply initial styles
        self._apply_theme_styles()


    def apply_language_texts(self, _t):
        """Cập nhật text theo ngôn ngữ. _t là hàm translate: (key, fallback) -> str."""
        if hasattr(self, "_tag_lbl"):
            self._tag_lbl.setText(_t("welcome.read_everywhere", "ĐỌC MỌI LÚC  ·  HIỂU MỌI NƠI"))

        card_data = [
            (_t("welcome.card1.title", "Đọc PDF mượt mà"),      _t("welcome.card1.desc", "Hỗ trợ file lớn, xem toàn trang")),
            (_t("welcome.card2.title", "Chỉnh sửa trực tiếp"),  _t("welcome.card2.desc", "Chèn text, ảnh, vẽ, tô sáng")),
            (_t("welcome.card3.title", "Ký số USB Token"),       _t("welcome.card3.desc", "Viettel CA, VNPT CA, FPT CA")),
            (_t("welcome.card4.title", "Bảo mật cao"),           _t("welcome.card4.desc", "Mã hoá, che nội dung nhạy cảm")),
        ]
        for i, (title, desc) in enumerate(card_data):
            if i < len(self._card_title_labels):
                self._card_title_labels[i].setText(title)
            if i < len(self._card_desc_labels):
                self._card_desc_labels[i].setText(desc)

        # Buttons: tìm QPushButton trong widget
        from packages.qt_compat.QtWidgets import QPushButton
        btns = self.findChildren(QPushButton)
        # Lọc 3 button action chính (có fixedHeight = 44)
        action_btns = [b for b in btns if b.sizeHint().height() == 44 or b.minimumHeight() == 44]
        btn_texts = [
            _t("welcome.btn_open",   "Mở tệp PDF"),
            _t("welcome.btn_new",    "Tạo PDF mới"),
            _t("welcome.btn_recent", "Mở gần đây"),
        ]
        for i, btn in enumerate(action_btns[:3]):
            btn.setText(f"   {btn_texts[i]}   ")

        # Secondary labels (version, recent title)
        for lbl in self._secondary_labels:
            txt = lbl.text()
            if txt.startswith("Tệp gần đây") or txt.startswith("Recent files"):
                lbl.setText(_t("welcome.lbl_recent", "Tệp gần đây"))
            elif txt.startswith("Phiên bản") or txt.startswith("Version"):
                import app.version as _v
                lbl.setText(f"{_t('welcome.version', 'Phiên bản')} {_v.APP_VERSION}")

        if hasattr(self, "_hint_lbl"):
            self._hint_lbl.setText(_t("welcome.drag_drop", "hoặc kéo & thả tệp PDF vào cửa sổ này"))

    def _recent_files(self) -> list[str]:
        recent = load_recent()
        if not isinstance(recent, list):
            return []
        return [p for p in recent[:5] if isinstance(p, str) and os.path.isfile(p)]

    def _open_recent_file(self, path: str):
        if self._on_recent_file:
            self._on_recent_file(path)
        elif self._on_open:
            self._on_open()

    def _open_whats_new(self):
        doc_path = os.path.join(_ROOT, "docs", "2026-05-30_BASELINE_STATUS_HANDOFF.md")
        if not os.path.exists(doc_path):
            doc_path = os.path.join(_ROOT, "docs", "PHASE1_WIN_STATUS.md")
        QDesktopServices.openUrl(QUrl.fromLocalFile(doc_path))
