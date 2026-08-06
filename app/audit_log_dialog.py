"""Dialog xem nhật ký hoạt động (audit log)."""
from __future__ import annotations

import os

from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
)
from packages.qt_compat.QtCore import Qt
from packages.qt_compat.QtGui import QDesktopServices, QFont
from packages.qt_compat.QtCore import QUrl
from packages.audit import read_recent_logs, get_audit_log_path
from styles.theme import is_dark

def _build_style(dark: bool) -> str:
    if dark:
        return """
QDialog { background: #16162A; }
QLabel#title { color: #E8EEFF; font-size: 15px; font-weight: 700; }
QLabel#status { color: #8080B0; font-size: 11px; }
QTextEdit {
    background: #12122A;
    color: #D0D8F8;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    padding: 10px;
}
QPushButton {
    background: #1E1E38;
    color: #B0B8E0;
    border: 1px solid #3A3A60;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover { background: #2A2A50; border-color: #6060C0; }
QPushButton#btn_close {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3A3A6A,stop:1 #2A2A50);
    color: #D0D8F8; border: none;
}
QPushButton#btn_close:hover { background: #4A4A80; }
"""
    return """
QDialog { background: #F8FAFF; }
QLabel#title { color: #0F172A; font-size: 15px; font-weight: 700; }
QLabel#status { color: #64748B; font-size: 11px; }
QTextEdit {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 10px;
}
QPushButton {
    background: #E2E8F0;
    color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover { background: #CBD5E1; border-color: #94A3B8; }
QPushButton#btn_close {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #1D4ED8);
    color: #FFFFFF; border: none;
}
QPushButton#btn_close:hover { background: #3B82F6; }
"""


class AuditLogDialog(QDialog):
    """Modal dialog hiển thị 200 dòng cuối của audit log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nhật ký hoạt động")
        self.setModal(True)
        self.setMinimumSize(800, 500)
        self.resize(900, 560)
        self.setStyleSheet(_build_style(is_dark()))

        self._build_ui()
        self._load_logs()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        # Title
        title = QLabel("Nhật ký hoạt động")
        title.setObjectName("title")
        root.addWidget(title)

        # Status / path hint
        self._lbl_status = QLabel("")
        self._lbl_status.setObjectName("status")
        root.addWidget(self._lbl_status)

        # Log viewer
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        mono_font = QFont("Courier New")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        mono_font.setPointSize(11)
        self._text_edit.setFont(mono_font)
        root.addWidget(self._text_edit)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_refresh = QPushButton("Làm mới")
        btn_refresh.clicked.connect(self._load_logs)

        btn_open_dir = QPushButton("Mở thư mục log")
        btn_open_dir.clicked.connect(self._open_log_dir)

        btn_close = QPushButton("Đóng")
        btn_close.setObjectName("btn_close")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(btn_refresh)
        btn_row.addWidget(btn_open_dir)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _load_logs(self):
        lines = read_recent_logs(200)
        if lines:
            self._text_edit.setPlainText("".join(lines))
            # Scroll to bottom so most recent entries are visible
            cursor = self._text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self._text_edit.setTextCursor(cursor)
            self._lbl_status.setText(
                f"{len(lines)} dòng gần nhất — {get_audit_log_path()}"
            )
        else:
            self._text_edit.setPlainText("(Chưa có nhật ký hoạt động nào.)")
            self._lbl_status.setText(get_audit_log_path())

    def _open_log_dir(self):
        log_dir = os.path.dirname(get_audit_log_path())
        QDesktopServices.openUrl(QUrl.fromLocalFile(log_dir))
