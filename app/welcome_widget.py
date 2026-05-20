from __future__ import annotations

from packages.qt_compat.QtCore import Qt, Signal
from packages.qt_compat.QtGui import QFont
from packages.qt_compat.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.icon_utils import svg_pixmap


class WelcomeWidget(QWidget):
    openRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WelcomeWidget")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("WelcomeHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(18)

        logo = QLabel()
        logo.setPixmap(svg_pixmap("logo_mark.svg", size=140))
        logo.setFixedSize(154, 154)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(8)
        headline = QLabel("3T Reader")
        headline.setObjectName("WelcomeHeadline")
        headline.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        tagline = QLabel("PDF signing, review, and document tools")
        tagline.setObjectName("WelcomeTagline")
        tagline.setWordWrap(True)
        tagline.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        intro = QLabel(
            "Mở PDF, ký số, chèn text/ảnh, và thao tác tài liệu trong một luồng duy nhất."
        )
        intro.setWordWrap(True)
        intro.setObjectName("WelcomeIntro")
        text_col.addWidget(headline)
        text_col.addWidget(tagline)
        text_col.addWidget(intro)
        text_col.addStretch(1)

        open_btn = QPushButton("Mở tệp PDF")
        open_btn.setObjectName("WelcomeOpenButton")
        open_btn.clicked.connect(self.openRequested.emit)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        text_col.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignLeft)
        hero_layout.addLayout(text_col, 1)

        root.addWidget(hero)

        features = QGridLayout()
        features.setHorizontalSpacing(14)
        features.setVerticalSpacing(14)

        items = [
            ("Mở nhanh", "Recent files, tab, thumbnail sidebar."),
            ("Xem rõ", "PDF.js render, search, zoom, fit, fullscreen."),
            ("Sửa nội dung", "Text, ảnh, xoay, kéo, resize, undo/redo."),
            ("Ký số", "USB token, PKCS#11, flow Windows."),
        ]
        for idx, (title, body) in enumerate(items):
            card = self._make_card(title, body)
            features.addWidget(card, idx // 2, idx % 2)

        root.addLayout(features)
        root.addStretch(1)

        self.apply_theme("dark")

    def _make_card(self, title: str, body: str) -> QFrame:
        card = QFrame()
        card.setObjectName("WelcomeCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("WelcomeCardTitle")
        title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        body_label = QLabel(body)
        body_label.setObjectName("WelcomeCardBody")
        body_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(body_label)
        return card

    def apply_theme(self, mode: str):
        dark = mode != "light"
        if dark:
            self.setStyleSheet(
                """
                QWidget#WelcomeWidget { background: #0f0f13; }
                QFrame#WelcomeHero {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #10192a, stop:1 #162640);
                    border: 1px solid #20324f;
                    border-radius: 24px;
                }
                QLabel#WelcomeHeadline { color: #f7f8ff; }
                QLabel#WelcomeTagline { color: #ffd58a; font-size: 15px; font-weight: 600; }
                QLabel#WelcomeIntro { color: #c1c8df; font-size: 14px; }
                QPushButton#WelcomeOpenButton {
                    background: #ff8a00;
                    color: #ffffff;
                    border: none;
                    border-radius: 14px;
                    padding: 12px 22px;
                    font-size: 14px;
                    font-weight: 700;
                }
                QPushButton#WelcomeOpenButton:hover { background: #ff9f2d; }
                QFrame#WelcomeCard {
                    background: #141822;
                    border: 1px solid #253148;
                    border-radius: 18px;
                }
                QLabel#WelcomeCardTitle { color: #f0f5ff; }
                QLabel#WelcomeCardBody { color: #aeb7d1; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QWidget#WelcomeWidget { background: #f4f7fb; }
                QFrame#WelcomeHero {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #ffffff, stop:1 #edf4ff);
                    border: 1px solid #d1dced;
                    border-radius: 24px;
                }
                QLabel#WelcomeHeadline { color: #10203a; }
                QLabel#WelcomeTagline { color: #f05a28; font-size: 15px; font-weight: 600; }
                QLabel#WelcomeIntro { color: #334155; font-size: 14px; }
                QPushButton#WelcomeOpenButton {
                    background: #f05a28;
                    color: #ffffff;
                    border: none;
                    border-radius: 14px;
                    padding: 12px 22px;
                    font-size: 14px;
                    font-weight: 700;
                }
                QPushButton#WelcomeOpenButton:hover { background: #ff6c45; }
                QFrame#WelcomeCard {
                    background: #ffffff;
                    border: 1px solid #d6deea;
                    border-radius: 18px;
                }
                QLabel#WelcomeCardTitle { color: #10203a; }
                QLabel#WelcomeCardBody { color: #475569; }
                """
            )

