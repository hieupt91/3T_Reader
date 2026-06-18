"""Export actions: PDF -> Word, PDF -> Excel.

In dev (.venv) → subprocess for crash isolation (pdf2docx is known unstable).
In frozen EXE → QThread in-process, since the frozen bootloader can't run `-m`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from threading import Event

from packages.qt_compat.QtCore import QObject, QProcess, QThread, Qt, pyqtSignal
from packages.qt_compat.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

from app.actions._guard import require_document
from app.dialogs import show_warning


def _open_after_export(output_path: str):
    if sys.platform == "darwin":
        os.system(f'open "{output_path}"')
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
            raise RuntimeError("Da huy xuat file.")
        self.progress.emit(message)

    def run(self):
        try:
            from packages.document_core.converter import (
                convert_pdf_to_docx,
                convert_pdf_to_xlsx,
            )
            if self._task == "docx":
                convert_pdf_to_docx(self._pdf_path, self._output_path, progress_cb=self._progress)
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
        progress.close()
        setattr(window, "_export_thread", None)
        if not ok and "Da huy" in (err or ""):
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

    state = {"stdout": [], "stderr": [], "reported": False, "cancelled": False}
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
        progress.close()
        if not ok and state.get("cancelled"):
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except OSError:
                pass
            _show_export_result(window, output_path, False, "Da huy xuat file.")
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
        progress.close()
        stderr_text = "".join(state["stderr"]).strip()
        stdout_text = "".join(state["stdout"]).strip()
        _show_export_result(window, output_path, False, stderr_text or stdout_text or "Khong khoi dong duoc bo xu ly xuat.")

    proc.readyReadStandardOutput.connect(_append_stdout)
    proc.readyReadStandardError.connect(_append_stderr)
    proc.finished.connect(_finish)
    proc.errorOccurred.connect(_error)
    def _cancel_proc():
        state["cancelled"] = True
        progress.setLabelText("Dang huy xuat file...")
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

    _run_conversion(window, "docx", pdf_path, out_path)


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
