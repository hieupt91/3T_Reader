from packages.qt_compat.QtWidgets import QDockWidget, QListWidget, QListWidgetItem, QLabel, QWidget, QVBoxLayout
from packages.qt_compat.QtCore import Qt


class AnnotationSidebar(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Chú thích", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setFixedWidth(260)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._empty_label = QLabel("Không có chú thích.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color:#64748B;font-size:12px;padding:20px;")

        self.list = QListWidget()
        self.list.setStyleSheet("""
            QListWidget {
                background:#F8FAFC;
                border:none;
                padding:8px;
                color:#0F172A;
                font-size:12px;
            }
            QListWidget::item {
                border:1px solid #E2E8F0;
                border-radius:6px;
                padding:7px 8px;
                margin:3px 0;
                background:#FFFFFF;
            }
            QListWidget::item:selected {
                border-color:#2563EB;
                background:#DBEAFE;
            }
            QListWidget::item:hover {
                background:#EEF2FF;
            }
        """)

        layout.addWidget(self._empty_label)
        layout.addWidget(self.list)
        self.setWidget(container)

        self._on_navigate = None
        self.list.itemClicked.connect(self._handle_click)
        self.clear()

    def clear(self):
        self.list.clear()
        self.list.setVisible(False)
        self._empty_label.setVisible(True)

    def load_annotations(self, pdf_path: str, on_navigate):
        self._on_navigate = on_navigate
        self.list.clear()
        rows = self._read_annotations(pdf_path)
        if not rows:
            self.clear()
            return
        self._empty_label.setVisible(False)
        self.list.setVisible(True)
        for row in rows:
            item = QListWidgetItem(row["label"])
            item.setToolTip(row["tooltip"])
            item.setData(Qt.ItemDataRole.UserRole, row["page"])
            self.list.addItem(item)

    def _handle_click(self, item: QListWidgetItem):
        page = item.data(Qt.ItemDataRole.UserRole)
        if page and self._on_navigate:
            self._on_navigate(int(page))

    def _read_annotations(self, pdf_path: str) -> list[dict]:
        try:
            import pikepdf
            rows: list[dict] = []
            with pikepdf.open(pdf_path) as pdf:
                for page_index, page in enumerate(pdf.pages, start=1):
                    annots = page.get("/Annots", [])
                    for annot in annots or []:
                        try:
                            obj = annot.get_object() if hasattr(annot, "get_object") else annot
                            subtype = str(obj.get("/Subtype", "/Annot")).lstrip("/")
                            contents = str(obj.get("/Contents", "") or "").strip()
                            if len(contents) > 80:
                                contents = contents[:77] + "..."
                            snippet = contents or self._label_for_subtype(subtype)
                            label = f"Trang {page_index} - {self._label_for_subtype(subtype)}"
                            if snippet:
                                label += f"\n{snippet}"
                            rows.append({
                                "page": page_index,
                                "label": label,
                                "tooltip": f"Trang {page_index} - {subtype}",
                            })
                        except Exception:
                            continue
            return rows
        except Exception:
            return []

    @staticmethod
    def _label_for_subtype(subtype: str) -> str:
        labels = {
            "Highlight": "Tô sáng",
            "Underline": "Gạch dưới",
            "StrikeOut": "Gạch ngang",
            "Text": "Ghi chú",
            "FreeText": "Văn bản",
            "Ink": "Vẽ tay",
            "Widget": "Trường ký",
        }
        return labels.get(subtype, subtype or "Chú thích")
