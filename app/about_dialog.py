from __future__ import annotations

import os

from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from packages.qt_compat.QtCore import Qt, QSize
from PySide6.QtSvgWidgets import QSvgWidget

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Giới thiệu 3T Reader")
        self.setModal(True)
        self.setFixedWidth(460)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header banner ───────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(120)
        header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #0A1550, stop:0.6 #1A3C9E, stop:1 #2B5CE6);"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(28, 12, 28, 12)

        logo_path = os.path.join(_ASSETS, "logo_full.svg")
        if os.path.exists(logo_path):
            logo_widget = QSvgWidget(logo_path)
            logo_widget.setFixedSize(QSize(310, 82))
            logo_widget.setStyleSheet("background: transparent;")
            h_layout.addWidget(logo_widget)
        else:
            lbl = QLabel("3T READER")
            lbl.setStyleSheet("color:white; font-size:30px; font-weight:900; letter-spacing:3px;")
            h_layout.addWidget(lbl)

        h_layout.addStretch()
        root.addWidget(header)

        # ── Info body ───────────────────────────────────────────────────────
        body = QVBoxLayout()
        body.setContentsMargins(32, 22, 32, 8)
        body.setSpacing(10)

        def _row(label: str, value: str):
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#8899BB; font-size:12px; min-width:100px;")
            val = QLabel(value)
            val.setStyleSheet("font-size:12px; font-weight:600;")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            body.addLayout(row)

        _row("Phiên bản:",  "1.0.0 Beta")
        _row("Nền tảng:",   "macOS · Windows")
        _row("Chức năng:",  "Đọc, chỉnh sửa và ký số tài liệu PDF")
        _row("Công nghệ:",  "Python · PySide6 · pypdfium2 · pikepdf · PDF.js")
        _row("Nhà phát triển:", "3T Technology")

        body.addSpacing(14)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #2A2A40; border:none; max-height:1px;")
        body.addWidget(sep)

        body.addSpacing(10)

        copyright_lbl = QLabel("© 2024–2025 3T Technology. All rights reserved.")
        copyright_lbl.setStyleSheet("color:#556688; font-size:11px;")
        copyright_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(copyright_lbl)

        root.addLayout(body)

        # ── Footer ──────────────────────────────────────────────────────────
        footer = QHBoxLayout()
        footer.setContentsMargins(32, 16, 32, 22)
        footer.addStretch()

        btn_ok = QPushButton("  Đóng  ")
        btn_ok.setDefault(True)
        btn_ok.setFixedWidth(110)
        btn_ok.setFixedHeight(36)
        btn_ok.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 #FF7700, stop:1 #FF4400); color:white; border-radius:6px;"
            "  font-size:13px; font-weight:700; border:none; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 #FF9900, stop:1 #FF5500); }"
        )
        btn_ok.clicked.connect(self.accept)
        footer.addWidget(btn_ok)
        root.addLayout(footer)
