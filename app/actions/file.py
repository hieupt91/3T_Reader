import os
import tempfile
import uuid

from packages.qt_compat.QtWidgets import QFileDialog, QMenu, QInputDialog, QLineEdit
from packages.qt_compat.QtCore import QStandardPaths, QUrl
from packages.platform.recent import load_recent, save_recent, clear_recent
from app.dialogs import show_warning
from packages.pdf_engine import get_pdf_engine


def _existing_dir(path: str | None) -> str:
    if not path:
        return ""
    if os.path.isfile(path):
        path = os.path.dirname(path)
    return path if os.path.isdir(path) else ""


def _default_open_dir(window) -> str:
    current_dir = _existing_dir(getattr(window, "current_path", None))
    if current_dir:
        return current_dir

    for recent_path in load_recent():
        recent_dir = _existing_dir(recent_path if isinstance(recent_path, str) else "")
        if recent_dir:
            return recent_dir

    for location in (
        QStandardPaths.StandardLocation.DocumentsLocation,
        QStandardPaths.StandardLocation.DesktopLocation,
        QStandardPaths.StandardLocation.DownloadLocation,
        QStandardPaths.StandardLocation.HomeLocation,
    ):
        for path in QStandardPaths.standardLocations(location):
            if os.path.isdir(path):
                return path
    return ""


def _sidebar_urls(window) -> list[QUrl]:
    paths: list[str] = []

    def add(path: str | None) -> None:
        folder = _existing_dir(path)
        if folder and folder not in paths:
            paths.append(folder)

    add(getattr(window, "current_path", None))
    for recent_path in load_recent():
        if isinstance(recent_path, str):
            add(recent_path)

    for location in (
        QStandardPaths.StandardLocation.DesktopLocation,
        QStandardPaths.StandardLocation.DocumentsLocation,
        QStandardPaths.StandardLocation.DownloadLocation,
        QStandardPaths.StandardLocation.HomeLocation,
    ):
        for path in QStandardPaths.standardLocations(location):
            add(path)

    return [QUrl.fromLocalFile(path) for path in paths]


def _pick_document_files(window):
    import sys
    dialog = QFileDialog(window)
    dialog.setWindowTitle("Chọn tệp tài liệu")
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    dialog.setNameFilters([
        "Tài liệu (*.pdf *.png *.jpg *.jpeg *.bmp *.doc *.docx *.xls *.xlsx *.xml)", 
        "Tệp PDF (*.pdf)", 
        "Hình ảnh (*.png *.jpg *.jpeg *.bmp)",
        "Tất cả tệp (*)"
    ])
    default_dir = _default_open_dir(window)
    if default_dir:
        dialog.setDirectory(default_dir)
    sidebar_urls = _sidebar_urls(window)
    if sidebar_urls:
        dialog.setSidebarUrls(sidebar_urls)

    if sys.platform in {"darwin", "win32"}:
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, False)
    else:
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setLabelText(QFileDialog.DialogLabel.LookIn, "Tìm trong")
        dialog.setLabelText(QFileDialog.DialogLabel.FileName, "Tên tệp")
        dialog.setLabelText(QFileDialog.DialogLabel.FileType, "Loại tệp")
        dialog.setLabelText(QFileDialog.DialogLabel.Accept, "Mở")
        dialog.setLabelText(QFileDialog.DialogLabel.Reject, "Hủy")

    if dialog.exec():
        return dialog.selectedFiles()
    return []


def open_file(window, path=None):
    if not path:
        paths = _pick_document_files(window)
        if not paths:
            return
        if len(paths) > 1:
            for p in paths:
                open_file(window, p)
            return
        path = paths[0]
    if path:
        if not os.path.exists(path):
            show_warning(
                window,
                "Không tìm thấy tài liệu",
                f"Không tìm thấy tài liệu tại đường dẫn:\n{path}",
            )
            return

        from app.actions.document_converter import process_file_and_open
        pdf_path = process_file_and_open(window, path)
        if not pdf_path:
            return
            
        prepared = _prepare_pdf_source(window, pdf_path)
        if not prepared:
            return

        source_path, _display_path, temp_path = prepared
        if temp_path:
            tracked = getattr(window, "_session_temp_paths", None)
            if tracked is None:
                tracked = set()
                window._session_temp_paths = tracked
            tracked.add(temp_path)

        if hasattr(window, "open_document"):
            opened = window.open_document(
                source_path,
                display_path=path,
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
            window.viewer.load_pdf(source_path, zoom="100", pagemode="thumbs")

        save_recent(path)
        window.status.showMessage(f"Đã mở: {os.path.basename(path)}", 3000)


def _prepare_pdf_source(window, path: str):
    try:
        doc = get_pdf_engine().open(path)
    except Exception as e:
        show_warning(
            window,
            "Không mở được tệp",
            "Không đọc được nội dung file PDF này — file có thể bị hỏng, tải chưa "
            "xong, hoặc không đúng định dạng PDF. Hãy thử tải lại file hoặc dùng "
            "một file khác.\n\n"
            f"Chi tiết kỹ thuật: {e}",
        )
        return None

    try:
        if not doc.needs_password:
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
                temp_dir = os.path.join(tempfile.gettempdir(), "3t_reader_decrypted")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}.pdf")
                doc.save_without_encryption(temp_path)
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
