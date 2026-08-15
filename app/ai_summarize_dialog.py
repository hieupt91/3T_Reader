"""Dialog tóm tắt tài liệu PDF."""
from __future__ import annotations

import os

from packages.qt_compat.QtCore import Qt, QTimer
from packages.qt_compat.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QFileDialog, QComboBox, QCheckBox,
    QSizePolicy,
)
from app.ai_task_runner import dialog_task_running, start_dialog_task
from styles.theme import is_dark


def _build_style(dark: bool) -> str:
    if dark:
        return """
QDialog { background: #16162A; }
QLabel#title  { color: #E8EEFF; font-size: 15px; font-weight: 700; }
QLabel#status { color: #8080B0; font-size: 11px; }
QLabel#lbl_type { color: #C0C8F0; font-size: 13px; }
QComboBox {
    background: #1E1E38;
    color: #D0D8F8;
    border: 1px solid #3A3A60;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
    min-width: 220px;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #1E1E38;
    color: #D0D8F8;
    selection-background-color: #3A3A6A;
    border: 1px solid #3A3A60;
}
QCheckBox { color: #C0C8F0; font-size: 13px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QTextEdit {
    background: #1A1A2E;
    color: #D0D8F8;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    font-size: 13px;
    padding: 10px;
    line-height: 1.5;
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
QPushButton:hover  { background: #2A2A50; border-color: #6060C0; }
QPushButton:disabled { color: #444466; border-color: #2A2A44; }
QPushButton#btn_summarize {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2ecc71,stop:1 #27ae60);
    color: white; border: none;
}
QPushButton#btn_summarize:hover { background: #3dd882; }
QFrame#divider { background: #2A2A4A; }
"""
    return """
QDialog { background: #F8FAFF; }
QLabel#title  { color: #0F172A; font-size: 15px; font-weight: 700; }
QLabel#status { color: #475569; font-size: 11px; }
QLabel#lbl_type { color: #334155; font-size: 13px; }
QComboBox {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
    min-width: 220px;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #FFFFFF;
    color: #0F172A;
    selection-background-color: #DBEAFE;
    border: 1px solid #CBD5E1;
}
QCheckBox { color: #334155; font-size: 13px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QTextEdit {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    font-size: 13px;
    padding: 10px;
    line-height: 1.5;
}
QPushButton {
    background: #E2E8F0;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover  { background: #CBD5E1; border-color: #94A3B8; }
QPushButton:disabled { color: #94A3B8; border-color: #CBD5E1; }
QPushButton#btn_summarize {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2563EB,stop:1 #16A34A);
    color: white; border: none;
}
QPushButton#btn_summarize:hover { background: #3B82F6; }
QFrame#divider { background: #CBD5E1; }
"""

_DOC_TYPES = [
    ("Hợp đồng",              "contract"),
    ("Đề xuất/Báo giá",       "proposal"),
    ("Biên bản họp",          "minutes"),
    ("Báo cáo",               "report"),
    ("Tài liệu thông thường", "general"),
]

class AISummarizeDialog(QDialog):
    """Dialog tóm tắt tài liệu PDF."""

    def __init__(self, parent, pdf_path: str):
        super().__init__(parent)
        self.setWindowTitle("Tóm tắt tài liệu")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.resize(660, 540)
        self.setStyleSheet(_build_style(is_dark()))

        self._pdf_path   = pdf_path
        self._result_text = ""
        self._task_thread = None
        self._task_worker = None

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("Tóm tắt tài liệu")
        title.setObjectName("title")
        root.addWidget(title)

        # Doc type selector
        type_row = QHBoxLayout()
        type_row.setSpacing(12)

        lbl_type = QLabel("Loại tài liệu:")
        lbl_type.setObjectName("lbl_type")
        type_row.addWidget(lbl_type)

        self._combo_type = QComboBox()
        for label, _ in _DOC_TYPES:
            self._combo_type.addItem(label)
        self._combo_type.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self._combo_type)
        type_row.addStretch()
        root.addLayout(type_row)

        # Contract extraction checkbox (chỉ hiện khi chọn Hợp đồng)
        self._chk_extract = QCheckBox("Trích xuất dữ liệu hợp đồng")
        self._chk_extract.setVisible(True)  # index 0 is contract
        root.addWidget(self._chk_extract)

        # Status
        self._lbl_status = QLabel("Sẵn sàng tóm tắt.")
        self._lbl_status.setObjectName("status")
        root.addWidget(self._lbl_status)

        # Result area
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setPlaceholderText("Kết quả tóm tắt sẽ xuất hiện ở đây…")
        self._text_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._text_edit)

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        root.addWidget(div)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_close = QPushButton("Đóng")
        self._btn_close.clicked.connect(self.reject)

        self._btn_summarize = QPushButton("Tóm tắt")
        self._btn_summarize.setObjectName("btn_summarize")
        self._btn_summarize.clicked.connect(self._on_summarize)

        self._btn_save = QPushButton("Lưu kết quả (.txt)")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)

        btn_row.addWidget(self._btn_close)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_summarize)
        root.addLayout(btn_row)

    def _on_type_changed(self, index: int):
        _, doc_type = _DOC_TYPES[index]
        self._chk_extract.setVisible(doc_type == "contract")

    def _on_summarize(self):
        from packages.ai.provider import is_ai_available
        if not is_ai_available():
            self._text_edit.setPlainText(
                "Chưa cấu hình API key AI. Vào Settings để cài đặt."
            )
            self._lbl_status.setText("Chưa có API key.")
            return

        index = self._combo_type.currentIndex()
        _, doc_type = _DOC_TYPES[index]
        extract = self._chk_extract.isChecked() and doc_type == "contract"

        self._btn_summarize.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._lbl_status.setText("Đang tóm tắt…")
        self._text_edit.setPlainText("Đang phân tích tài liệu…")

        started = start_dialog_task(
            self,
            lambda: self._summarize_document(doc_type, extract),
            on_success=self._on_finished,
            on_error=self._on_error,
        )
        if not started:
            self._btn_summarize.setEnabled(True)
            self._text_edit.setPlainText("Đang có một tác vụ AI khác đang chạy.")
            self._lbl_status.setText("Đang có tác vụ AI khác đang chạy.")

    def _ocr_scan_text(self, max_pages: int = 20, char_budget: int = 6000) -> str:
        """TC38: OCR ngầm file scan để lấy văn bản cho bước tóm tắt.

        Chạy trong worker thread của start_dialog_task nên không block UI.
        Dừng sớm khi đã đủ ký tự cho prompt tóm tắt (6000 chars).
        """
        from packages.ocr.engine import ocr_pdf_page

        try:
            import pypdfium2 as pdfium
            from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK
            with PDFIUM_LOCK:
                doc = pdfium.PdfDocument(self._pdf_path)
                try:
                    total = len(doc)
                finally:
                    doc.close()
        except Exception:
            return ""

        parts: list[str] = []
        collected = 0
        for page_num in range(1, min(total, max_pages) + 1):
            try:
                res = ocr_pdf_page(self._pdf_path, page_num)
            except Exception:
                continue
            text = (getattr(res, "text", "") or "").strip()
            if text:
                parts.append(f"[Trang {page_num}]\n{text}")
                collected += len(text)
                if collected >= char_budget:
                    break
        return "\n\n".join(parts)

    def _summarize_document(self, doc_type: str, extract_contract: bool):
        from packages.ai.summarize import (
            summarize_pdf, summarize_text, extract_contract_data, SummaryResult,
        )

        # --- TC38: file scan (không có text layer) → tự động OCR ngầm ---
        ocr_text = ""
        try:
            import pdfplumber
            sample_text = ""
            with pdfplumber.open(self._pdf_path) as pdf_doc:
                pages_to_check = min(len(pdf_doc.pages), 3)
                for i in range(pages_to_check):
                    sample_text += (pdf_doc.pages[i].extract_text() or "")
            if len(sample_text.strip()) < 50:
                from packages.ocr.engine import is_available as ocr_available
                if not ocr_available():
                    return SummaryResult(
                        summary="",
                        error=(
                            "Tài liệu này có vẻ là bản scan (hình ảnh), "
                            "không có văn bản trích xuất được.\n"
                            "Máy chưa cài Tesseract OCR nên không thể tự động "
                            "nhận dạng văn bản. Vui lòng cài OCR rồi thử lại "
                            "(Menu → Công cụ → OCR tài liệu)."
                        ),
                    )
                ocr_text = self._ocr_scan_text()
                if len(ocr_text.strip()) < 50:
                    return SummaryResult(
                        summary="",
                        error=(
                            "Đã tự động chạy OCR nhưng không nhận dạng được "
                            "văn bản trong tài liệu scan này."
                        ),
                    )
        except Exception:
            pass  # Let summarize_pdf handle other PDF read errors

        if ocr_text:
            text = ocr_text
            if len(text) > 6000:
                text = text[:6000] + "\n[... nội dung bị cắt bớt ...]"
            result = summarize_text(text, doc_type)
        else:
            result = summarize_pdf(self._pdf_path, doc_type)
        if not result.success:
            return result

        if extract_contract and doc_type == "contract":
            if ocr_text:
                text = ocr_text
            else:
                import pdfplumber

                with pdfplumber.open(self._pdf_path) as pdf_doc:
                    parts = []
                    for page in pdf_doc.pages:
                        text = (page.extract_text() or "").strip()
                        if text:
                            parts.append(text)
                text = "\n\n".join(parts)
            if len(text) > 6000:
                text = text[:6000]
            contract_result = extract_contract_data(text)
            if contract_result.success:
                from packages.ai.summarize import SummaryResult

                combined = (
                    "=== TÓM TẮT ===\n"
                    + result.summary
                    + "\n\n=== DỮ LIỆU HỢP ĐỒNG ===\n"
                    + contract_result.summary
                )
                result = SummaryResult(summary=combined, doc_type=result.doc_type)
        return result

    def _on_finished(self, result):
        self._btn_summarize.setEnabled(True)
        if result.success:
            self._result_text = result.summary
            self._text_edit.setPlainText(self._result_text)
            self._lbl_status.setStyleSheet("color:#4fc080;font-size:11px")
            self._lbl_status.setText("Tóm tắt hoàn thành.")
            self._btn_save.setEnabled(True)
        else:
            self._text_edit.setPlainText(f"Lỗi: {result.error}")
            self._lbl_status.setStyleSheet("color:#E05050;font-size:11px")
            self._lbl_status.setText(f"Lỗi: {result.error}")

    def _on_error(self, msg: str, _tb: str):
        self._btn_summarize.setEnabled(True)
        self._text_edit.setPlainText(f"Lỗi: {msg}")
        self._lbl_status.setStyleSheet("color:#E05050;font-size:11px")
        self._lbl_status.setText(f"Lỗi: {msg}")

    def _on_save(self):
        base = os.path.splitext(os.path.basename(self._pdf_path))[0]
        default_name = f"{base}_tomtat.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu kết quả tóm tắt",
            os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "Text files (*.txt)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._result_text)
            orig = self._btn_save.text()
            self._btn_save.setText("Đã lưu!")
            QTimer.singleShot(1500, lambda: self._btn_save.setText(orig))

    def closeEvent(self, event):
        if dialog_task_running(self):
            self._lbl_status.setStyleSheet("color:#E05050;font-size:11px")
            self._lbl_status.setText("Đang chờ AI hoàn tất. Hãy đóng lại sau khi tác vụ xong.")
            event.ignore()
            return
        super().closeEvent(event)
