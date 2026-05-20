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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AboutDialog")
        self.setWindowTitle("Giới thiệu 3T Reader")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.setMinimumHeight(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("AboutHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 24, 24, 24)
        header_layout.setSpacing(20)

        logo = QLabel()
        logo.setPixmap(svg_pixmap("logo_full.svg", size=220))
        logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(logo, 0)

        title_col = QVBoxLayout()
        title = QLabel("Giới thiệu 3T Reader")
        title.setObjectName("AboutTitle")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        version = QLabel(f"Version {APP_VERSION}")
        version.setObjectName("AboutVersion")
        version.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        desc = QLabel(
            "Desktop PDF workflow cho mở file, xem, chỉnh nội dung, ký số và build Windows."
        )
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
            "• Mở PDF, recent files, tab và thumbnail sidebar",
            "• Chèn text / ảnh, sửa object, undo / redo",
            "• PDF.js render trong local HTTP server",
            "• Windows packaging, USB token và ký số",
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

