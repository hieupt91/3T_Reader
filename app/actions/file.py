import os
import tempfile
import uuid

import fitz
from PyQt6.QtWidgets import QFileDialog, QMenu, QInputDialog, QLineEdit
from core.recent import load_recent, save_recent, clear_recent
from app.dialogs import show_warning


def _pick_pdf_file(window):
    dialog = QFileDialog(window)
    dialog.setWindowTitle("Chọn tệp PDF")
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    dialog.setNameFilter("Tệp PDF (*.pdf)")
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setLabelText(QFileDialog.DialogLabel.LookIn, "Tìm trong")
    dialog.setLabelText(QFileDialog.DialogLabel.FileName, "Tên tệp")
    dialog.setLabelText(QFileDialog.DialogLabel.FileType, "Loại tệp")
    dialog.setLabelText(QFileDialog.DialogLabel.Accept, "Mở")
    dialog.setLabelText(QFileDialog.DialogLabel.Reject, "Hủy")
    if dialog.exec():
        selected = dialog.selectedFiles()
        return selected[0] if selected else None
    return None


def open_file(window, path=None):
    if not path:
        path = _pick_pdf_file(window)
    if path:
        prepared = _prepare_pdf_source(window, path)
        if not prepared:
            return

        source_path, display_path, temp_path = prepared

        if hasattr(window, "open_document"):
            opened = window.open_document(
                source_path,
                display_path=display_path,
                temp_path=temp_path,
            )
            if not opened:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                return
        else:
            window.current_path = source_path
            window.viewer.load_pdf(source_path, zoom="page-width", pagemode="thumbs")

        save_recent(path)
        window.status.showMessage(f"Đã mở: {os.path.basename(path)}", 3000)


def _prepare_pdf_source(window, path: str):
    try:
        doc = fitz.open(path)
    except Exception as e:
        show_warning(window, "Không mở được tệp", str(e))
        return None

    try:
        if not doc.needs_pass:
            return (path, path, None)

        for _ in range(3):
            password, ok = QInputDialog.getText(
                window,
                "Tệp có mật khẩu",
                "Nhập mật khẩu để mở PDF:",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return None

            if doc.authenticate(password):
                temp_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_decrypted")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}.pdf")
                doc.save(temp_path, encryption=fitz.PDF_ENCRYPT_NONE)
                return (temp_path, path, temp_path)

            show_warning(window, "Mật khẩu không đúng", "Mật khẩu bạn nhập không đúng. Vui lòng thử lại.")

        show_warning(window, "Không thể mở tệp", "Đã vượt quá số lần nhập mật khẩu.")
        return None
    finally:
        doc.close()

def _populate_recent_menu(menu, window):
    """Shared logic: populate a QMenu with recent file entries."""
    recent = load_recent()
    if not isinstance(recent, list):
        recent = []
    clean_recent = [p for p in recent if isinstance(p, str) and p.strip()]

    if not clean_recent:
        empty = menu.addAction("  Chưa có tệp nào")
        empty.setEnabled(False)
    else:
        from app.icon_utils import svg_icon
        for path in clean_recent:
            action = menu.addAction(f"  {os.path.basename(path)}")
            action.setIcon(svg_icon("folder_open.svg", size=16, color="#9b9bc0"))
            action.setToolTip(path)
            action.setStatusTip(path)
            action.triggered.connect(lambda checked=False, p=path: open_file(window, p))
        menu.addSeparator()
        clear_action = menu.addAction("🗑  Xóa danh sách")
        clear_action.triggered.connect(lambda: _clear_and_notify(window))


def show_recent_menu(window):
    menu = QMenu(window)
    _populate_recent_menu(menu, window)
    menu.exec(window.toolbar.mapToGlobal(window.toolbar.rect().bottomLeft()))


def _clear_and_notify(window):
    clear_recent()
    window.status.showMessage("Đã xóa danh sách tệp gần đây", 3000)