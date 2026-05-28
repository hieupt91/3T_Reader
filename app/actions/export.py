"""Export actions: PDF -> Word, PDF -> Excel."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from packages.qt_compat.QtCore import QProcess
from packages.qt_compat.QtWidgets import QFileDialog, QMessageBox

from app.actions._guard import require_document
from app.dialogs import show_warning


def _run_conversion(window, task: str, pdf_path: str, output_path: str):
    existing_proc = getattr(window, "_export_proc", None)
    if existing_proc and existing_proc.state() != QProcess.ProcessState.NotRunning:
        show_warning(window, "Dang xuat file", "Vui long cho thao tac xuat file hien tai hoan tat.")
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

    state = {"stdout": [], "stderr": []}

    def _append_stdout():
        chunk = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        if chunk:
            state["stdout"].append(chunk)
            last = chunk.strip().splitlines()[-1] if chunk.strip() else ""
            if last:
                window.status.showMessage(last, 0)

    def _append_stderr():
        chunk = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
        if chunk:
            state["stderr"].append(chunk)

    def _cleanup():
        window._export_proc = None

    def _finish(exit_code: int, exit_status):
        _append_stdout()
        _append_stderr()
        _cleanup()

        stdout_text = "".join(state["stdout"]).strip()
        stderr_text = "".join(state["stderr"]).strip()

        if exit_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            window.status.showMessage(f"Da xuat: {os.path.basename(output_path)}", 5000)
            ext = os.path.splitext(output_path)[1].upper()
            msg = QMessageBox(window)
            msg.setWindowTitle(f"Xuat {ext} thanh cong")
            msg.setText(f"Da luu file:\n{output_path}")
            msg.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok
            )
            msg.setDefaultButton(QMessageBox.StandardButton.Ok)
            if msg.exec() == QMessageBox.StandardButton.Open:
                if sys.platform == "darwin":
                    os.system(f'open "{output_path}"')
                elif sys.platform == "win32":
                    os.startfile(output_path)
            return

        window.status.showMessage("", 0)
        msg = stderr_text or stdout_text or f"Bo xu ly xuat thoat voi ma {exit_code}"
        show_warning(window, "Khong the xuat file", msg)

    def _error(_err):
        _append_stdout()
        _append_stderr()
        if proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()

    proc.readyReadStandardOutput.connect(_append_stdout)
    proc.readyReadStandardError.connect(_append_stderr)
    proc.finished.connect(_finish)
    proc.errorOccurred.connect(_error)

    window._export_proc = proc
    window.status.showMessage("Dang chay bo xu ly xuat...", 0)
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


@require_document(show_message=True)
def export_pdf_to_word(window):
    """Chuyen doi PDF hien tai sang Word (.docx)."""
    pdf_path = window.current_path
    if not pdf_path or not os.path.exists(pdf_path):
        show_warning(window, "Khong tim thay tep", "Tep PDF khong ton tai.")
        return

    default_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".docx"
    out_path, _ = QFileDialog.getSaveFileName(
        window, "Luu file Word", default_name, "Word Document (*.docx)"
    )
    if not out_path:
        return
    if not out_path.lower().endswith(".docx"):
        out_path += ".docx"

    _run_conversion(window, "docx", pdf_path, out_path)


@require_document(show_message=True)
def export_pdf_to_excel(window):
    """Trich xuat PDF sang Excel (.xlsx)."""
    pdf_path = window.current_path
    if not pdf_path or not os.path.exists(pdf_path):
        show_warning(window, "Khong tim thay tep", "Tep PDF khong ton tai.")
        return

    default_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".xlsx"
    out_path, _ = QFileDialog.getSaveFileName(
        window, "Luu file Excel", default_name, "Excel Workbook (*.xlsx)"
    )
    if not out_path:
        return
    if not out_path.lower().endswith(".xlsx"):
        out_path += ".xlsx"

    _run_conversion(window, "xlsx", pdf_path, out_path)
