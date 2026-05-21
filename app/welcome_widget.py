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
    QVBoxLayout,
    QWidget,
)

from app.icon_utils import svg_pixmap


class WelcomeWidget(QWidget):
    openRequested = Signal()
    recentRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WelcomeWidget")

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 30)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("WelcomeHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(48, 34, 48, 30)
        hero_layout.setSpacing(18)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        logo = QLabel()
        logo.setObjectName("WelcomeBrandLogo")
        logo.setPixmap(svg_pixmap("logo_full.svg", size=(560, 180)))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setMinimumHeight(180)
        hero_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

        tagline = QLabel("DOC MOI LUC - HIEU MOI NOI")
        tagline.setObjectName("WelcomeTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(tagline)

        intro = QLabel(
            "Nen tang PDF cho Windows: doc muot, sua nhanh, ky so USB token va san sang cho huong thuong mai."
        )
        intro.setWordWrap(True)
        intro.setObjectName("WelcomeIntro")
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        hero_layout.addWidget(intro)

        features = QGridLayout()
        features.setHorizontalSpacing(18)
        features.setVerticalSpacing(18)

        items = [
            ("WelcomeCardOpen", "logo_mark.svg", "Doc PDF muot ma", "Ho tro file lon, tab, thumbnail va tim kiem nhanh."),
            ("WelcomeCardEdit", "edit_object.svg", "Chinh sua truc tiep", "Chen text, anh, doi vi tri, resize, xoay va undo/redo."),
            ("WelcomeCardSign", "usb.svg", "Ky so USB Token", "Flow PKCS#11 cho Windows, huong toi xac thuc token that."),
            ("WelcomeCardSecure", "info.svg", "Bao mat va van hanh", "Temp file, recent, packaging va compliance cho Phase 1 Win."),
        ]
        for idx, item in enumerate(items):
            features.addWidget(self._make_card(*item), 0, idx)
        hero_layout.addLayout(features)

        button_row = QHBoxLayout()
        button_row.setSpacing(14)

        open_btn = QPushButton("Mo tep PDF")
        open_btn.setObjectName("WelcomeOpenButton")
        open_btn.clicked.connect(self.openRequested.emit)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(open_btn)

        recent_btn = QPushButton("Mo gan day")
        recent_btn.setObjectName("WelcomeRecentButton")
        recent_btn.clicked.connect(self.recentRequested.emit)
        recent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(recent_btn)

        hero_layout.addLayout(button_row)

        drag_hint = QLabel("hoac keo va tha tep PDF vao cua so nay")
        drag_hint.setObjectName("WelcomeDragHint")
        drag_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(drag_hint)

        root.addWidget(hero)
        root.addStretch(1)

        self.apply_theme("dark")

    def _make_card(self, object_name: str, icon_file: str, title: str, body: str) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        icon = QLabel()
        icon.setObjectName("WelcomeCardIcon")
        icon.setPixmap(svg_pixmap(icon_file, size=44))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("WelcomeCardTitle")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body_label = QLabel(body)
        body_label.setObjectName("WelcomeCardBody")
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon)
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
                    background: #1f2127;
                    border: 1px solid #2a3040;
                    border-radius: 26px;
                }
                QLabel#WelcomeBrandLogo { background: transparent; }
                QLabel#WelcomeTagline {
                    color: #90b6f2;
                    font-size: 15px;
                    font-weight: 700;
                    letter-spacing: 6px;
                }
                QLabel#WelcomeIntro {
                    color: #c1c8df;
                    font-size: 14px;
                    max-width: 900px;
                }
                QPushButton#WelcomeOpenButton {
                    background: #ff8a00;
                    color: #ffffff;
                    border: none;
                    border-radius: 14px;
                    padding: 14px 28px;
                    font-size: 15px;
                    font-weight: 700;
                    min-width: 190px;
                }
                QPushButton#WelcomeOpenButton:hover { background: #ff9f2d; }
                QPushButton#WelcomeRecentButton {
                    background: transparent;
                    color: #ff8a00;
                    border: 2px solid #ff8a00;
                    border-radius: 14px;
                    padding: 12px 28px;
                    font-size: 15px;
                    font-weight: 700;
                    min-width: 190px;
                }
                QPushButton#WelcomeRecentButton:hover {
                    background: rgba(255, 138, 0, 0.08);
                }
                QLabel#WelcomeDragHint {
                    color: #6d7790;
                    font-size: 13px;
                }
                QFrame[objectName^="WelcomeCard"] {
                    background: #1c1d36;
                    border: 1px solid #27305b;
                    border-radius: 16px;
                    min-width: 220px;
                }
                QLabel#WelcomeCardTitle { color: #f0f5ff; }
                QLabel#WelcomeCardBody { color: #aeb7d1; font-size: 13px; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QWidget#WelcomeWidget { background: #f4f7fb; }
                QFrame#WelcomeHero {
                    background: #ffffff;
                    border: 1px solid #d1dced;
                    border-radius: 26px;
                }
                QLabel#WelcomeBrandLogo { background: transparent; }
                QLabel#WelcomeTagline {
                    color: #1e63d5;
                    font-size: 15px;
                    font-weight: 700;
                    letter-spacing: 6px;
                }
                QLabel#WelcomeIntro { color: #334155; font-size: 14px; max-width: 900px; }
                QPushButton#WelcomeOpenButton {
                    background: #f05a28;
                    color: #ffffff;
                    border: none;
                    border-radius: 14px;
                    padding: 14px 28px;
                    font-size: 15px;
                    font-weight: 700;
                    min-width: 190px;
                }
                QPushButton#WelcomeOpenButton:hover { background: #ff6c45; }
                QPushButton#WelcomeRecentButton {
                    background: transparent;
                    color: #f05a28;
                    border: 2px solid #f05a28;
                    border-radius: 14px;
                    padding: 12px 28px;
                    font-size: 15px;
                    font-weight: 700;
                    min-width: 190px;
                }
                QPushButton#WelcomeRecentButton:hover {
                    background: rgba(240, 90, 40, 0.06);
                }
                QLabel#WelcomeDragHint {
                    color: #64748b;
                    font-size: 13px;
                }
                QFrame[objectName^="WelcomeCard"] {
                    background: #ffffff;
                    border: 1px solid #d6deea;
                    border-radius: 16px;
                    min-width: 220px;
                }
                QLabel#WelcomeCardTitle { color: #10203a; }
                QLabel#WelcomeCardBody { color: #475569; font-size: 13px; }
                """
            )
