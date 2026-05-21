"""Export actions: PDF → Word, PDF → Excel."""
from __future__ import annotations

import os

from packages.qt_compat.QtCore import QThread, pyqtSignal, QObject
from packages.qt_compat.QtWidgets import QFileDialog, QMessageBox

from app.actions._guard import require_document
from app.dialogs import show_warning


class _ConvertWorker(QObject):
    finished = pyqtSignal(str)   # output_path on success
    failed   = pyqtSignal(str)   # error message
    progress = pyqtSignal(str)   # status text

    def __init__(self, task: str, pdf_path: str, output_path: str):
        super().__init__()
        self._task = task          # "docx" | "xlsx"
        self._pdf  = pdf_path
        self._out  = output_path

    def run(self):
        from packages.document_core.converter import convert_pdf_to_docx, convert_pdf_to_xlsx
        try:
            if self._task == "docx":
                convert_pdf_to_docx(self._pdf, self._out, progress_cb=self.progress.emit)
            else:
                n = convert_pdf_to_xlsx(self._pdf, self._out, progress_cb=self.progress.emit)
                if n == 0:
                    self.failed.emit("Không tìm thấy nội dung để xuất.")
                    return
            self.finished.emit(self._out)
        except ImportError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"Lỗi chuyển đổi: {e}")


def _run_conversion(window, task: str, pdf_path: str, output_path: str):
    thread = QThread(window)
    worker = _ConvertWorker(task, pdf_path, output_path)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.progress.connect(lambda msg: window.status.showMessage(msg, 0))

    def _done(out_path):
        thread.quit()
        window.status.showMessage(f"Đã xuất: {os.path.basename(out_path)}", 5000)
        ext = os.path.splitext(out_path)[1].upper()
        msg = QMessageBox(window)
        msg.setWindowTitle(f"Xuất {ext} thành công")
        msg.setText(f"Đã lưu file:\n{out_path}")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Ok)
        if msg.exec() == QMessageBox.StandardButton.Open:
            import subprocess, sys
            if sys.platform == "darwin":
                subprocess.Popen(["open", out_path])
            elif sys.platform == "win32":
                os.startfile(out_path)

    def _fail(msg):
        thread.quit()
        window.status.showMessage("", 0)
        show_warning(window, "Không thể xuất file", msg)

    worker.finished.connect(_done)
    worker.failed.connect(_fail)
    thread.finished.connect(thread.deleteLater)
    worker.finished.connect(worker.deleteLater)
    worker.failed.connect(worker.deleteLater)

    # keep references alive
    window._export_thread = thread
    window._export_worker = worker

    thread.start()


@require_document(show_message=True)
def export_pdf_to_word(window):
    """Chuyển đổi PDF hiện tại sang Word (.docx)."""
    pdf_path = window.current_path
    if not pdf_path or not os.path.exists(pdf_path):
        show_warning(window, "Không tìm thấy tệp", "Tệp PDF không tồn tại.")
        return

    default_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".docx"
    out_path, _ = QFileDialog.getSaveFileName(
        window, "Lưu file Word", default_name, "Word Document (*.docx)"
    )
    if not out_path:
        return
    if not out_path.lower().endswith(".docx"):
        out_path += ".docx"

    window.status.showMessage("Đang chuẩn bị chuyển đổi…", 0)
    _run_conversion(window, "docx", pdf_path, out_path)


@require_document(show_message=True)
def export_pdf_to_excel(window):
    """Trích xuất bảng từ PDF sang Excel (.xlsx)."""
    pdf_path = window.current_path
    if not pdf_path or not os.path.exists(pdf_path):
        show_warning(window, "Không tìm thấy tệp", "Tệp PDF không tồn tại.")
        return

    default_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".xlsx"
    out_path, _ = QFileDialog.getSaveFileName(
        window, "Lưu file Excel", default_name, "Excel Workbook (*.xlsx)"
    )
    if not out_path:
        return
    if not out_path.lower().endswith(".xlsx"):
        out_path += ".xlsx"

    window.status.showMessage("Đang chuẩn bị trích xuất bảng…", 0)
    _run_conversion(window, "xlsx", pdf_path, out_path)
