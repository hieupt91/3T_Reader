from __future__ import annotations

from packages.qt_compat.QtCore import Qt, pyqtSignal
from packages.qt_compat.QtGui import QIcon
from packages.qt_compat.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.signature_ui import apply_signature_styles


class SignatureCenterDock(QDockWidget):
    fieldActivated = pyqtSignal(str, int, str)
    fieldValidateRequested = pyqtSignal(dict)
    fieldSignRequested = pyqtSignal(dict)
    fieldNavigateRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__("Ký số", parent)
        self.setObjectName("signatureCenterDock")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)

        container = QWidget()
        self._container = container
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Signature Center")
        title.setObjectName("signatureCenterTitle")
        subtitle = QLabel("Danh sách field ký, trạng thái, và thao tác nhanh.")
        subtitle.setObjectName("signatureCenterSubtitle")
        subtitle.setWordWrap(True)

        self._summary_label = QLabel("Chưa mở tài liệu.")
        self._summary_label.setObjectName("signatureCenterSummary")
        self._summary_label.setWordWrap(True)

        filter_row = QHBoxLayout()
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Lọc theo field, người ký, hoặc trạng thái")
        self._filter.textChanged.connect(self._refresh_visible_items)
        self._refresh_btn = QPushButton("Làm mới")
        self._refresh_btn.clicked.connect(self._emit_refresh)
        filter_row.addWidget(self._filter, 1)
        filter_row.addWidget(self._refresh_btn, 0)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show_current_item)
        self.list.itemDoubleClicked.connect(self._activate_item)
        self.list.setUniformItemSizes(False)

        detail_frame = QFrame()
        detail_frame.setObjectName("signatureDetailFrame")
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(10, 10, 10, 10)
        detail_layout.setSpacing(6)

        self._detail_title = QLabel("Chọn một field để xem chi tiết.")
        self._detail_title.setWordWrap(True)
        self._detail_pill = QLabel("Chưa chọn")
        self._detail_pill.setObjectName("signatureDetailPill")
        self._detail_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_pill.setStyleSheet(
            "border-radius:999px;padding:4px 10px;font-weight:700;font-size:11px;"
            "background:#fff7e8;color:#975900;border:1px solid #f0cf8e;"
        )

        pill_row = QHBoxLayout()
        pill_row.addWidget(self._detail_pill, 0, Qt.AlignmentFlag.AlignLeft)
        pill_row.addStretch(1)

        self._detail_lines: dict[str, QLabel] = {}
        for label in (
            "field_name",
            "page_number",
            "signed_state",
            "signer",
            "reason",
            "location",
            "signing_time",
            "certificate",
            "content",
            "validation",
        ):
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)
            lbl = QLabel()
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lbl.setObjectName(f"signatureDetail_{label}")
            row_layout.addWidget(lbl)
            self._detail_lines[label] = lbl
            detail_layout.addWidget(row)

        self._detail_lines["field_name"].setText("Trường ký: -")
        self._detail_lines["page_number"].setText("Trang: -")
        self._detail_lines["signed_state"].setText("Trạng thái: -")
        self._detail_lines["signer"].setText("Người ký: -")
        self._detail_lines["reason"].setText("Lý do: -")
        self._detail_lines["location"].setText("Địa điểm: -")
        self._detail_lines["signing_time"].setText("Thời điểm ký: -")
        self._detail_lines["certificate"].setText("Chứng thư: -")
        self._detail_lines["content"].setText("Nội dung ký: -")
        self._detail_lines["validation"].setText("Xác minh: -")
        self._detail_lines["validation"].setObjectName("signatureValidationLine")

        action_row = QHBoxLayout()
        self._open_btn = QPushButton("Xem chi tiết")
        self._open_btn.clicked.connect(self._open_selected)
        self._go_btn = QPushButton("Đi tới trang")
        self._go_btn.clicked.connect(self._goto_selected)
        self._sign_btn = QPushButton("Ký field")
        self._sign_btn.clicked.connect(self._sign_selected)
        self._verify_btn = QPushButton("Kiểm tra")
        self._verify_btn.clicked.connect(self._verify_selected)
        action_row.addWidget(self._open_btn)
        action_row.addWidget(self._go_btn)
        action_row.addWidget(self._sign_btn)
        action_row.addWidget(self._verify_btn)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._summary_label)
        layout.addLayout(filter_row)
        layout.addWidget(self.list, 1)
        layout.addWidget(detail_frame, 0)
        layout.addLayout(action_row)

        self.setWidget(container)
        apply_signature_styles(self, object_name="signatureCenterDock")

        self._fields: list[dict] = []
        self._pdf_path: str = ""
        self._on_open_field = None
        self._on_sign_field = None
        self._on_validate_field = None
        self._on_navigate = None
        self._selected_field: dict | None = None

    def clear(self):
        self._fields = []
        self._pdf_path = ""
        self._summary_label.setText("Chưa mở tài liệu.")
        self.list.clear()
        self._show_field(None)

    def load_signature_fields(
        self,
        pdf_path: str,
        fields: list[dict],
        *,
        on_open_field=None,
        on_sign_field=None,
        on_validate_field=None,
        on_navigate=None,
    ):
        self._pdf_path = pdf_path or ""
        self._fields = list(fields or [])
        self._on_open_field = on_open_field
        self._on_sign_field = on_sign_field
        self._on_validate_field = on_validate_field
        self._on_navigate = on_navigate

        self.list.clear()
        total = len(self._fields)
        signed = sum(1 for item in self._fields if item.get("field_signed"))
        unsigned = total - signed
        invalid = sum(1 for item in self._fields if not item.get("integrity_ok") and item.get("field_signed"))
        self._summary_label.setText(
            f"Tổng field: {total} | Đã ký: {signed} | Chưa ký: {unsigned} | Có cảnh báo: {invalid}"
        )

        for field in self._fields:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, field)
            item.setText(self._render_item_text(field))
            item.setToolTip(self._render_tooltip(field))
            if field.get("field_signed"):
                if field.get("integrity_ok"):
                    item.setBackground(Qt.GlobalColor.transparent)
                else:
                    item.setBackground(Qt.GlobalColor.transparent)
            self.list.addItem(item)

        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self._show_field(None)

        self._refresh_visible_items()

    def select_field(self, field_name: str):
        if not field_name:
            return
        for row in range(self.list.count()):
            item = self.list.item(row)
            field = item.data(Qt.ItemDataRole.UserRole) or {}
            if str(field.get("field_name") or "") == field_name:
                self.list.setCurrentRow(row)
                break

    def _refresh_visible_items(self):
        query = (self._filter.text() or "").strip().lower()
        if not self.list.count():
            return

        selected = self.list.currentItem()
        selected_name = None
        if selected:
            selected_field = selected.data(Qt.ItemDataRole.UserRole) or {}
            selected_name = str(selected_field.get("field_name") or "")

        first_visible = None
        for row in range(self.list.count()):
            item = self.list.item(row)
            field = item.data(Qt.ItemDataRole.UserRole) or {}
            haystack = " ".join(
                str(field.get(key) or "")
                for key in (
                    "field_name",
                    "display_signer",
                    "signer_reported_name",
                    "reason",
                    "location",
                    "certificate_status",
                    "issuer_name",
                    "overall_status",
                )
            ).lower()
            visible = not query or query in haystack
            item.setHidden(not visible)
            if visible and first_visible is None:
                first_visible = item

        if selected_name:
            for row in range(self.list.count()):
                item = self.list.item(row)
                field = item.data(Qt.ItemDataRole.UserRole) or {}
                if str(field.get("field_name") or "") == selected_name and not item.isHidden():
                    self.list.setCurrentRow(row)
                    self._show_field(field)
                    return

        if first_visible is not None:
            self.list.setCurrentItem(first_visible)

    def _emit_refresh(self):
        parent = self.parent()
        if parent and hasattr(parent, "_reload_signature_center"):
            parent._reload_signature_center()

    def _current_field(self) -> dict | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else self._selected_field

    def _show_current_item(self, current, _previous):
        field = current.data(Qt.ItemDataRole.UserRole) if current else None
        self._show_field(field)

    def _show_field(self, field: dict | None):
        self._selected_field = field
        if not field:
            self._detail_title.setText("Chọn một field để xem chi tiết.")
            self._detail_pill.setText("Chưa chọn")
            self._detail_pill.setStyleSheet(
                "border-radius:999px;padding:4px 10px;font-weight:700;font-size:11px;"
                "background:#fff7e8;color:#975900;border:1px solid #f0cf8e;"
            )
            for key, label in self._detail_lines.items():
                if key == "field_name":
                    label.setText("Trường ký: -")
                elif key == "page_number":
                    label.setText("Trang: -")
                elif key == "signed_state":
                    label.setText("Trạng thái: -")
                elif key == "signer":
                    label.setText("Người ký: -")
                elif key == "reason":
                    label.setText("Lý do: -")
                elif key == "location":
                    label.setText("Địa điểm: -")
                elif key == "signing_time":
                    label.setText("Thời điểm ký: -")
                elif key == "certificate":
                    label.setText("Chứng thư: -")
                elif key == "content":
                    label.setText("Nội dung ký: -")
                elif key == "validation":
                    label.setText("Xác minh: -")
            self._sign_btn.setEnabled(False)
            self._sign_btn.setText("Ký field")
            self._open_btn.setEnabled(False)
            self._verify_btn.setEnabled(False)
            self._go_btn.setEnabled(False)
            return

        self._detail_title.setText(str(field.get("field_name") or "Signature field"))
        signed = bool(field.get("field_signed"))
        integrity_ok = bool(field.get("integrity_ok"))
        if not signed:
            pill = "Chưa ký"
            style = "border-radius:999px;padding:4px 10px;font-weight:700;font-size:11px;background:#fff7e8;color:#975900;border:1px solid #f0cf8e;"
        elif integrity_ok:
            pill = "Hợp lệ"
            style = "border-radius:999px;padding:4px 10px;font-weight:700;font-size:11px;background:#e8fff0;color:#146c34;border:1px solid #a8e0bb;"
        else:
            pill = "Cảnh báo"
            style = "border-radius:999px;padding:4px 10px;font-weight:700;font-size:11px;background:#fff1f2;color:#a11e2b;border:1px solid #f1b6be;"
        self._detail_pill.setText(pill)
        self._detail_pill.setStyleSheet(style)

        self._detail_lines["field_name"].setText(f"Trường ký: {field.get('field_name') or '-'}")
        self._detail_lines["page_number"].setText(f"Trang: {field.get('page_number') or '-'}")
        self._detail_lines["signed_state"].setText(
            f"Trạng thái: {'Đã ký' if signed else 'Chưa ký'}"
        )
        self._detail_lines["signer"].setText(f"Người ký: {field.get('display_signer') or 'Không rõ'}")
        self._detail_lines["reason"].setText(f"Lý do: {field.get('reason') or 'Không có'}")
        self._detail_lines["location"].setText(f"Địa điểm: {field.get('location') or 'Không có'}")
        self._detail_lines["signing_time"].setText(f"Thời điểm ký: {field.get('signing_time') or 'Không rõ'}")
        cert = f"{field.get('issuer_name') or 'Không rõ'} | {field.get('serial_hex') or 'Không rõ'}"
        self._detail_lines["certificate"].setText(f"Chứng thư: {cert}")
        preview = str(field.get("signature_preview_text") or "").strip()
        if preview:
            self._detail_lines["content"].setText(f"Nội dung ký: {preview}")
        else:
            self._detail_lines["content"].setText("Nội dung ký: Không rõ")
        validation = field.get("overall_status") or field.get("message") or "Không rõ"
        self._detail_lines["validation"].setText(f"Xác minh: {validation}")

        self._open_btn.setEnabled(True)
        self._verify_btn.setEnabled(True)
        self._go_btn.setEnabled(True)
        if signed:
            self._sign_btn.setEnabled(False)
            self._sign_btn.setText("Đã ký")
            self._detail_lines["validation"].setText(
                f"Xác minh: Đã có chữ ký trong field này. {validation}"
            )
        else:
            self._sign_btn.setEnabled(True)
            self._sign_btn.setText("Ký field")

    def _activate_item(self, item: QListWidgetItem):
        field = item.data(Qt.ItemDataRole.UserRole) or {}
        if not field:
            return
        self._open_field(field)

    def _open_selected(self):
        field = self._current_field()
        if field:
            self._open_field(field)

    def _goto_selected(self):
        field = self._current_field()
        if not field:
            return
        page = int(field.get("page_number") or field.get("clicked_page") or 0)
        if page and callable(self._on_navigate):
            self._on_navigate(page)

    def _sign_selected(self):
        field = self._current_field()
        if not field:
            return
        if field.get("field_signed"):
            self._show_field(field)
            return
        if callable(self._on_sign_field):
            self._on_sign_field(field)

    def _verify_selected(self):
        field = self._current_field()
        if field and callable(self._on_validate_field):
            self._on_validate_field(field)

    def _open_field(self, field: dict):
        page = int(field.get("page_number") or field.get("clicked_page") or 0)
        field_name = str(field.get("field_name") or field.get("selected_field_name") or "")
        if page and callable(self._on_navigate):
            self._on_navigate(page)
        if callable(self._on_open_field):
            self._on_open_field(field)
        elif field_name and page and self.fieldActivated:
            self.fieldActivated.emit(field_name, page, str(field.get("display_signer") or ""))

    def _render_item_text(self, field: dict) -> str:
        name = str(field.get("field_name") or "Field")
        page = field.get("page_number") or field.get("clicked_page") or "-"
        status = "Đã ký" if field.get("field_signed") else "Chưa ký"
        signer = str(field.get("display_signer") or field.get("signer_reported_name") or "").strip()
        status_suffix = "Hợp lệ" if field.get("integrity_ok") else ("Cảnh báo" if field.get("field_signed") else "")
        lines = [f"{name}", f"Trang {page} • {status}"]
        if signer:
            lines.append(signer)
        if status_suffix:
            lines.append(status_suffix)
        return "\n".join(lines)

    def _render_tooltip(self, field: dict) -> str:
        return "\n".join(
            part for part in [
                f"Field: {field.get('field_name') or '-'}",
                f"Trang: {field.get('page_number') or field.get('clicked_page') or '-'}",
                f"Trạng thái: {'Đã ký' if field.get('field_signed') else 'Chưa ký'}",
                f"Người ký: {field.get('display_signer') or 'Không rõ'}",
                f"Xác minh: {field.get('overall_status') or field.get('message') or 'Không rõ'}",
            ] if part
        )
