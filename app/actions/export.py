"""Export actions: PDF -> Word, PDF -> Excel.

In dev (.venv) → subprocess for crash isolation (pdf2docx is known unstable).
In frozen EXE → QThread in-process, since the frozen bootloader can't run `-m`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from threading import Event

from packages.qt_compat.QtCore import QObject, QProcess, QThread, Qt, pyqtSignal
from packages.qt_compat.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

from app.actions._guard import require_document
from app.dialogs import show_warning


def _open_after_export(output_path: str):
    if sys.platform == "darwin":
        subprocess.run(["open", output_path], check=False)
    elif sys.platform == "win32":
        os.startfile(output_path)


def _show_export_result(window, output_path: str, success: bool, error_msg: str):
    window.status.showMessage("", 0)
    if not success:
        show_warning(window, "Không thể xuất file", error_msg or "Lỗi không xác định.")
        return

    ext = os.path.splitext(output_path)[1].upper()
    window.status.showMessage(f"Đã xuất: {os.path.basename(output_path)}", 5000)
    msg = QMessageBox(window)
    msg.setWindowTitle(f"Xuất {ext} thành công")
    msg.setText(f"Đã lưu file:\n{output_path}")
    msg.setStandardButtons(
        QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
    )
    msg.setDefaultButton(QMessageBox.StandardButton.Ok)
    if msg.exec() == QMessageBox.StandardButton.Open:
        _open_after_export(output_path)


# ─────────────────────────────────────────────────────────────────────────────
# In-process runner (frozen EXE)
# ─────────────────────────────────────────────────────────────────────────────


class _ExportWorker(QObject):
    finished = pyqtSignal(bool, str)   # success, error_message
    progress = pyqtSignal(str)

    def __init__(self, task: str, pdf_path: str, output_path: str):
        super().__init__()
        self._task = task
        self._pdf_path = pdf_path
        self._output_path = output_path
        self._cancelled = Event()

    def cancel(self):
        self._cancelled.set()

    def _progress(self, message: str):
        if self._cancelled.is_set():
            raise RuntimeError("Đã hủy xuất file.")
        self.progress.emit(message)

    def run(self):
        try:
            from packages.document_core.converter import (
                convert_pdf_to_docx,
                convert_pdf_to_docx_layout,
                convert_pdf_to_docx_structured,
                convert_pdf_to_xlsx,
            )
            if self._task == "docx":
                convert_pdf_to_docx(self._pdf_path, self._output_path, progress_cb=self._progress)
            elif self._task == "docx_layout":
                convert_pdf_to_docx_layout(self._pdf_path, self._output_path, progress_cb=self._progress)
            elif self._task == "docx_structured":
                convert_pdf_to_docx_structured(self._pdf_path, self._output_path, progress_cb=self._progress)
            else:
                convert_pdf_to_xlsx(self._pdf_path, self._output_path, progress_cb=self._progress)

            if not os.path.exists(self._output_path) or os.path.getsize(self._output_path) == 0:
                self.finished.emit(False, "Bộ chuyển đổi không tạo được tệp đầu ra.")
                return
            self.finished.emit(True, "")
        except Exception as exc:
            self.finished.emit(False, str(exc))


def _run_in_thread(window, task: str, pdf_path: str, output_path: str):
    existing = getattr(window, "_export_thread", None)
    if existing is not None and (getattr(existing, "isRunning", lambda: False)() or getattr(existing, "is_alive", lambda: False)()):
        show_warning(window, "Đang xuất file", "Vui lòng chờ thao tác xuất hiện tại hoàn tất.")
        return

    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except OSError:
            pass

    import threading
    worker = _ExportWorker(task, pdf_path, output_path)
    progress = QProgressDialog("Đang chuẩn bị xuất file…", "Hủy", 0, 0, window)
    progress.setWindowTitle("Xuất Word/Excel")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)

    def _progress(text: str):
        window.status.showMessage(text, 0)
        progress.setLabelText(text or "Đang xử lý…")

    def _finish(ok: bool, err: str):
        try:
            progress.canceled.disconnect(worker.cancel)
        except Exception:
            pass
        progress.close()
        setattr(window, "_export_thread", None)
        if not ok and ("Da huy" in (err or "") or "Đã hủy" in (err or "")):
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except OSError:
                pass
        _show_export_result(window, output_path, ok, err)

    worker.progress.connect(_progress)
    worker.finished.connect(_finish)
    progress.canceled.connect(worker.cancel)

    thread = threading.Thread(target=worker.run, daemon=True)
    window._export_thread = thread
    window.status.showMessage("Đang chạy bộ xử lý xuất…", 0)
    progress.show()
    thread.start()


# ─────────────────────────────────────────────────────────────────────────────
# Subprocess runner (dev mode — gives crash isolation against pdf2docx faults)
# ─────────────────────────────────────────────────────────────────────────────


def _run_in_subprocess(window, task: str, pdf_path: str, output_path: str):
    existing_proc = getattr(window, "_export_proc", None)
    if existing_proc and existing_proc.state() != QProcess.ProcessState.NotRunning:
        show_warning(window, "Đang xuất file", "Vui lòng chờ thao tác xuất hiện tại hoàn tất.")
        return

    project_root = Path(__file__).resolve().parents[2]
    python_exe = Path(sys.executable)
    preferred = python_exe.with_name("python.exe")
    if preferred.exists():
        python_exe = preferred

    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except OSError:
            pass

    proc = QProcess(window)
    proc.setWorkingDirectory(str(project_root))
    proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

    state = {"stdout": [], "stderr": [], "reported": False, "cancelled": False, "closing": False}
    progress = QProgressDialog("Đang chuẩn bị xuất file…", "Hủy", 0, 0, window)
    progress.setWindowTitle("Xuất Word/Excel")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)

    def _append_stdout():
        chunk = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        if chunk:
            state["stdout"].append(chunk)
            last = chunk.strip().splitlines()[-1] if chunk.strip() else ""
            if last:
                window.status.showMessage(last, 0)
                progress.setLabelText(last)

    def _append_stderr():
        chunk = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
        if chunk:
            state["stderr"].append(chunk)

    def _finish(exit_code: int, _exit_status):
        if state.get("reported"):
            return
        state["reported"] = True
        _append_stdout()
        _append_stderr()
        window._export_proc = None

        stdout_text = "".join(state["stdout"]).strip()
        stderr_text = "".join(state["stderr"]).strip()

        ok = exit_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
        state["closing"] = True
        try:
            progress.canceled.disconnect(_cancel_proc)
        except Exception:
            pass
        progress.close()
        if not ok and state.get("cancelled") and not (stderr_text or stdout_text):
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except OSError:
                pass
            _show_export_result(window, output_path, False, "Đã hủy xuất file.")
            return
        err = "" if ok else (stderr_text or stdout_text or f"Bộ xử lý xuất thoát với mã {exit_code}")
        _show_export_result(window, output_path, ok, err)

    def _error(_err):
        if state.get("reported"):
            return
        state["reported"] = True
        _append_stdout()
        _append_stderr()
        if proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()
        window._export_proc = None
        state["closing"] = True
        try:
            progress.canceled.disconnect(_cancel_proc)
        except Exception:
            pass
        progress.close()
        stderr_text = "".join(state["stderr"]).strip()
        stdout_text = "".join(state["stdout"]).strip()
        _show_export_result(window, output_path, False, stderr_text or stdout_text or "Không khởi động được bộ xử lý xuất.")

    proc.readyReadStandardOutput.connect(_append_stdout)
    proc.readyReadStandardError.connect(_append_stderr)
    proc.finished.connect(_finish)
    proc.errorOccurred.connect(_error)
    def _cancel_proc():
        if state.get("reported") or state.get("closing"):
            return
        state["cancelled"] = True
        progress.setLabelText("Đang hủy xuất file...")
        if proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()

    progress.canceled.connect(_cancel_proc)

    window._export_proc = proc
    window.status.showMessage("Đang chạy bộ xử lý xuất…", 0)
    progress.show()
    if getattr(sys, "frozen", False):
        proc.start(str(python_exe), ["--export-worker", task, pdf_path, output_path])
    else:
        proc.start(
            str(python_exe),
            [
                "-m",
                "packages.document_core.export_runner",
                task,
                pdf_path,
                output_path,
            ],
        )


def _run_conversion(window, task: str, pdf_path: str, output_path: str):
    _run_in_subprocess(window, task, pdf_path, output_path)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────


@require_document(show_message=True)
def export_pdf_to_word(window):
    """Chuyển đổi PDF hiện tại sang Word (.docx)."""
    from packages.qt_compat.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QPushButton, QHBoxLayout, QLabel, QButtonGroup
    
    pdf_path = window.current_path
    if not pdf_path or not os.path.exists(pdf_path):
        show_warning(window, "Không tìm thấy tệp", "Tệp PDF không tồn tại.")
        return

    dlg = QDialog(window)
    dlg.setWindowTitle("Tuỳ chọn xuất Word")
    dlg.resize(400, 250)
    layout = QVBoxLayout(dlg)
    
    lbl = QLabel("Chọn chế độ chuyển đổi:")
    lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
    layout.addWidget(lbl)
    
    btn_fast = QRadioButton("Chuyển đổi nhanh (Giữ Layout tĩnh - pdf2docx)")
    btn_fast.setChecked(True)
    btn_layout_mode = QRadioButton("Giữ nguyên Layout (Lưu dưới dạng ảnh - an toàn nhất)")
    btn_structured = QRadioButton("Trích xuất cấu trúc Text (Phù hợp chỉnh sửa nhiều - pdfplumber)")
    
    group = QButtonGroup(dlg)
    group.addButton(btn_fast)
    group.addButton(btn_layout_mode)
    group.addButton(btn_structured)
    
    layout.addWidget(btn_fast)
    layout.addWidget(btn_layout_mode)
    layout.addWidget(btn_structured)
    
    lbl_desc = QLabel(
        "Lưu ý:\n"
        "- Chuyển đổi nhanh: Phù hợp file ít phức tạp.\n"
        "- Giữ nguyên Layout: Mỗi trang là một ảnh trong Word, 100% không lỗi font.\n"
        "- Cấu trúc Text: Dễ copy và chỉnh sửa text/bảng nhất, không giữ layout."
    )
    lbl_desc.setStyleSheet("color: #666; font-size: 11px;")
    lbl_desc.setWordWrap(True)
    layout.addWidget(lbl_desc)
    
    button_box_layout = QHBoxLayout()
    btn_ok = QPushButton("Xuất file")
    btn_cancel = QPushButton("Hủy")
    button_box_layout.addStretch()
    button_box_layout.addWidget(btn_cancel)
    button_box_layout.addWidget(btn_ok)
    
    layout.addLayout(button_box_layout)
    
    btn_ok.clicked.connect(dlg.accept)
    btn_cancel.clicked.connect(dlg.reject)
    
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
        
    mode = "docx"
    if btn_layout_mode.isChecked():
        mode = "docx_layout"
    elif btn_structured.isChecked():
        mode = "docx_structured"

    default_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".docx"
    out_path, _ = QFileDialog.getSaveFileName(
        window, "Lưu file Word", default_name, "Word Document (*.docx)"
    )
    if not out_path:
        return
    if not out_path.lower().endswith(".docx"):
        out_path += ".docx"

    _run_conversion(window, mode, pdf_path, out_path)


@require_document(show_message=True)
def export_pdf_to_excel(window):
    """Trích xuất PDF sang Excel (.xlsx)."""
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

    _run_conversion(window, "xlsx", pdf_path, out_path)
