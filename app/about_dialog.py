from __future__ import annotations

from packages.qt_compat.QtCore import Qt
from packages.qt_compat.QtGui import QFont
from packages.qt_compat.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from app.icon_utils import svg_pixmap
from app.version import APP_VERSION


class AboutDialog(QDialog):
    def __init__(self, parent=None, theme_mode: str = "dark"):
        super().__init__(parent)
        self.setObjectName("AboutDialog")
        self.setWindowTitle("Gioi thieu 3T Reader")
        self.setModal(True)
        self.setMinimumWidth(720)
        self.setMinimumHeight(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("AboutHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 24, 24, 24)
        header_layout.setSpacing(20)

        logo = QLabel()
        logo.setPixmap(svg_pixmap("logo_full.svg", size=(420, 160)))
        logo.setFixedSize(360, 160)
        logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(logo, 0)

        title_col = QVBoxLayout()
        title = QLabel("3T READER")
        title.setObjectName("AboutTitle")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        version = QLabel(f"Version {APP_VERSION}")
        version.setObjectName("AboutVersion")
        version.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        desc = QLabel("DOC MOI LUC - HIEU MOI NOI")
        desc.setWordWrap(True)
        desc.setObjectName("AboutDescription")
        title_col.addWidget(title)
        title_col.addWidget(version)
        title_col.addWidget(desc)
        title_col.addStretch(1)
        header_layout.addLayout(title_col, 1)

        root.addWidget(header)

        body = QFrame()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 18, 24, 18)
        body_layout.setSpacing(10)
        for text in (
            "• Mo PDF, recent files, tab va thumbnail sidebar",
            "• Chen text / anh, sua object, undo / redo",
            "• PDF.js render qua local HTTP server",
            "• Windows packaging, USB token va ky so",
        ):
            label = QLabel(text)
            label.setObjectName("AboutBullet")
            body_layout.addWidget(label)
        body_layout.addStretch(1)
        root.addWidget(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

        self.apply_theme(theme_mode)

    def apply_theme(self, mode: str):
        dark = mode != "light"
        if dark:
            self.setStyleSheet(
                """
                QDialog#AboutDialog {
                    background: #0f0f13;
                }
                QFrame#AboutHeader {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #081c34, stop:1 #10325a);
                    border-bottom: 1px solid #203b60;
                }
                QLabel#AboutTitle { color: #ffffff; }
                QLabel#AboutVersion { color: #ffd58a; }
                QLabel#AboutDescription { color: #d0d8ea; font-size: 13px; }
                QFrame#AboutHeader QLabel { color: #ffffff; }
                QFrame#AboutHeader QLabel#AboutVersion { color: #ffd58a; }
                QFrame#AboutHeader QLabel#AboutDescription { color: #d0d8ea; }
                QLabel#AboutBullet {
                    color: #d7deee;
                    font-size: 13px;
                    padding: 4px 0;
                }
                QDialogButtonBox QPushButton {
                    min-width: 100px;
                    padding: 8px 16px;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QDialog#AboutDialog {
                    background: #f4f7fb;
                }
                QFrame#AboutHeader {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #ffffff, stop:1 #edf4ff);
                    border-bottom: 1px solid #d1dced;
                }
                QLabel#AboutTitle { color: #10203a; }
                QLabel#AboutVersion { color: #f05a28; }
                QLabel#AboutDescription { color: #334155; font-size: 13px; }
                QFrame#AboutHeader QLabel { color: #10203a; }
                QFrame#AboutHeader QLabel#AboutVersion { color: #f05a28; }
                QFrame#AboutHeader QLabel#AboutDescription { color: #334155; }
                QLabel#AboutBullet {
                    color: #475569;
                    font-size: 13px;
                    padding: 4px 0;
                }
                QDialogButtonBox QPushButton {
                    min-width: 100px;
                    padding: 8px 16px;
                }
                """
            )
