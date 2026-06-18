from __future__ import annotations

from packages.qt_compat.QtCore import Qt
from packages.qt_compat.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.language_manager import available_languages, language_pack_path


class LanguagePackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tải gói ngôn ngữ")
        self.setModal(True)
        self.resize(460, 360)

        self._checks: dict[str, QCheckBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Chọn một hoặc nhiều gói ngôn ngữ để tải từ server.")
        title.setWordWrap(True)
        title.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tìm kiếm ngôn ngữ (ví dụ: Nhật, Hàn, English)...")
        self.search_input.textChanged.connect(self._filter_languages)
        root.addWidget(self.search_input)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(8)

        for item in available_languages():
            code = item["code"]
            label = item["label"]
            exists = language_pack_path(code).exists()
            check = QCheckBox(f"{label}  -  {'Đã cài' if exists else 'Chưa cài'}")
            check.setChecked(not exists)
            self._checks[code] = check
            content_layout.addWidget(check)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        actions_row = QHBoxLayout()
        self.btn_all = QPushButton("Chọn tất cả")
        self.btn_none = QPushButton("Bỏ chọn")
        actions_row.addWidget(self.btn_all)
        actions_row.addWidget(self.btn_none)
        actions_row.addStretch(1)

        self.btn_all.clicked.connect(self._select_all)
        self.btn_none.clicked.connect(self._clear_all)
        root.addLayout(actions_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Tải xuống")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Hủy")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _filter_languages(self, text: str):
        text = text.lower()
        for code, check in self._checks.items():
            if text in check.text().lower() or text in code.lower():
                check.show()
            else:
                check.hide()

    def _select_all(self):
        for check in self._checks.values():
            check.setChecked(True)

    def _clear_all(self):
        for check in self._checks.values():
            check.setChecked(False)

    def selected_codes(self) -> list[str]:
        return [code for code, check in self._checks.items() if check.isChecked()]
