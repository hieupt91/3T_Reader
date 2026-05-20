import sys
import platform as _platform

# ================================================================
# BƯỚC 1: Xử lý subprocess của QtWebEngine TRƯỚC TIÊN
# Khi đóng gói bằng PyInstaller, QtWebEngine chạy lại chính .exe
# với các tham số như --type=renderer, --type=gpu-process, v.v.
# Phải thoát ngay lập tức — KHÔNG khởi tạo bất cứ thứ gì.
# ================================================================
if getattr(sys, 'frozen', False):
    import multiprocessing
    multiprocessing.freeze_support()

    # Đây là subprocess nội bộ của QtWebEngine → thoát ngay, không mở UI
    if any(arg.startswith('--type=') for arg in sys.argv):
        sys.exit(0)

# ================================================================
# BƯỚC 2: Single-instance guard qua platform adapter
# Chỉ cho phép 1 cửa sổ app chạy tại một thời điểm
# ================================================================
from packages.platform import acquire_single_instance

if not acquire_single_instance():
    sys.exit(0)

# ================================================================
# BƯỚC 3: Khởi tạo app bình thường
# ================================================================
from packages.qt_compat.QtWidgets import QApplication
from packages.qt_compat.QtGui import QFont, QIcon
from packages.qt_compat.QtCore import QLocale, QLibraryInfo, QTranslator, Qt

from app.window import PDFReaderApp
from app.config import APP_NAME
from app.icon_utils import svg_pixmap

if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)

    qt_translator = QTranslator()
    qtbase_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    qt_translator.load(QLocale("vi_VN"), "qtbase", "_", qtbase_path)
    app.installTranslator(qt_translator)

    _ui_font = {"Darwin": "SF Pro Text", "Windows": "Segoe UI"}.get(_platform.system(), "")
    app.setFont(QFont(_ui_font, 10))
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(svg_pixmap("logo_mark.svg", size=64)))

    window = PDFReaderApp()
    window.setWindowIcon(QIcon(svg_pixmap("logo_mark.svg", size=64)))
    window.show()
    sys.exit(app.exec())
