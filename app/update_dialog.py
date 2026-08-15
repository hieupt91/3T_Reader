"""Dialog tải và cài bản cập nhật với progress bar."""
from __future__ import annotations

import sys
import threading

from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit,
)
from packages.qt_compat.QtCore import Qt, Signal, QObject


class _Signals(QObject):
    progress = Signal(int)
    finished = Signal(str)
    error    = Signal(str)


class UpdateDialog(QDialog):
    """Hiện thông tin bản mới, download và mở installer."""

    def __init__(self, parent, info):
        super().__init__(parent)
        self._info   = info
        self._sigs   = _Signals()
        self._path   = ""
        self.setWindowTitle("Cập nhật 3T Reader")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._build_ui()
        self._sigs.progress.connect(self._on_progress)
        self._sigs.finished.connect(self._on_finished)
        self._sigs.error.connect(self._on_error)

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 20, 20, 20)

        lbl = QLabel(
            f"<b style='font-size:15px;color:#5B6CF6;'>"
            f"Phiên bản mới: {self._info.latest_version}</b>"
        )
        lay.addWidget(lbl)

        lay.addWidget(QLabel(
            f"<span style='color:#888;'>Đang dùng: {self._info.current_version}</span>"
        ))

        notes = (self._info.release_notes or "").strip()
        if notes:
            lay.addWidget(QLabel("<b>Thay đổi:</b>"))
            box = QTextEdit()
            box.setReadOnly(True)
            box.setPlainText(notes)
            box.setFixedHeight(100)
            lay.addWidget(box)

        self._status_lbl = QLabel("")
        self._status_lbl.hide()
        lay.addWidget(self._status_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.hide()
        lay.addWidget(self._bar)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_later = QPushButton("Nhắc sau")
        self._btn_later.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_later)

        self._btn_main = QPushButton("Tải về ngay")
        self._btn_main.setDefault(True)
        self._btn_main.setStyleSheet(
            "QPushButton{background:#5B6CF6;color:#fff;border-radius:6px;padding:6px 18px;font-weight:600;}"
            "QPushButton:hover{background:#6B7CF6;}"
            "QPushButton:disabled{background:#888;}"
        )
        self._btn_main.clicked.connect(self._start_download)
        btn_row.addWidget(self._btn_main)

        lay.addLayout(btn_row)

    # ── Download ──────────────────────────────────────────────────────────

    def _start_download(self):
        self._btn_main.setEnabled(False)
        self._btn_later.setEnabled(False)
        self._btn_main.setText("Đang tải...")
        self._status_lbl.setText("Đang tải xuống, vui lòng chờ...")
        self._status_lbl.show()
        self._bar.setValue(0)
        self._bar.show()

        sigs = self._sigs

        def _worker():
            try:
                # Vá lỗ hổng bảo mật thật (15/08/2026, xem
                # packages/update_client/checker.py đầu file): trước đây tải
                # thẳng bằng requests.get() ở đây, KHÔNG verify SHA-256 hay
                # chữ ký gì cả - tin tưởng mù quáng vào download_url. Dùng
                # download_update() đã verify đầy đủ (cùng logic Windows).
                from packages.update_client import download_update

                result = download_update(
                    self._info,
                    progress_cb=lambda pct: sigs.progress.emit(int(pct)),
                )
                if not result.success:
                    raise RuntimeError(result.error or "Không tải được bản cập nhật.")
                sigs.finished.emit(result.path)
            except Exception as exc:
                sigs.error.emit(str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_progress(self, pct: int):
        self._bar.setValue(pct)

    def _on_finished(self, path: str):
        self._path = path
        self._bar.setValue(100)
        self._status_lbl.setText("Tải xong! Nhấn 'Cài đặt ngay' để cập nhật.")
        self._btn_later.setEnabled(True)
        self._btn_main.setEnabled(True)
        self._btn_main.setText("Cài đặt ngay")
        try:
            self._btn_main.clicked.disconnect()
        except Exception:
            pass
        self._btn_main.clicked.connect(self._install)

    def _on_error(self, msg: str):
        self._status_lbl.setText(f"Lỗi: {msg}")
        self._btn_later.setEnabled(True)
        self._btn_main.setEnabled(True)
        self._btn_main.setText("Thử lại")
        try:
            self._btn_main.clicked.disconnect()
        except Exception:
            pass
        self._btn_main.clicked.connect(self._start_download)

    def _install(self):
        import subprocess
        path = self._path
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            subprocess.Popen([path], shell=False)
        else:
            subprocess.Popen(["xdg-open", path])
        self.accept()
        parent = self.parent()
        if parent:
            parent.close()
