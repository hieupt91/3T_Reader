import sys
import platform as _platform
import os
import threading
import traceback
import faulthandler

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

if len(sys.argv) >= 3 and sys.argv[1] == "--usb-sign-worker":
    from packages.signing.usb_worker import main as _usb_sign_worker_main

    sys.exit(_usb_sign_worker_main(sys.argv[2:]))

_crash_log_handle = None


def _install_crash_logging() -> None:
    global _crash_log_handle
    try:
        log_path = os.path.join(os.path.dirname(__file__), "app_log.txt")
        _crash_log_handle = open(log_path, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_crash_log_handle, all_threads=True)
    except Exception:
        return

    def _excepthook(exc_type, exc, tb):
        try:
            traceback.print_exception(exc_type, exc, tb, file=_crash_log_handle)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    if hasattr(threading, "excepthook"):
        def _thread_excepthook(args):
            try:
                traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=_crash_log_handle)
            except Exception:
                pass
            if threading.__excepthook__ is not None:
                threading.__excepthook__(args)

        threading.excepthook = _thread_excepthook

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
from packages.qt_compat.QtGui import QFont
from packages.qt_compat.QtCore import QLocale, QLibraryInfo, QTranslator, Qt
from app.window import PDFReaderApp
from app.config import APP_NAME
from styles.theme import apply_theme


def _startup_pdf_path(argv: list[str]) -> str | None:
    """Return the first PDF path passed by file association / command line."""
    for arg in argv[1:]:
        if not arg or arg.startswith("-"):
            continue
        path = os.path.abspath(os.path.expanduser(arg.strip('"')))
        if path.lower().endswith(".pdf") and os.path.isfile(path):
            return path
    return None

if __name__ == "__main__":
    _install_crash_logging()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)

    qt_translator = QTranslator()
    qtbase_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    qt_translator.load(QLocale("vi_VN"), "qtbase", "_", qtbase_path)
    app.installTranslator(qt_translator)

    # Tự detect theme macOS/Windows — theo hệ thống
    import platform as _plt
    _initial_theme = "dark"
    try:
        if _plt.system() == "Darwin":
            import subprocess
            r = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            _initial_theme = "dark" if r.stdout.strip() == "Dark" else "light"
        elif _plt.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            _initial_theme = "light" if val == 1 else "dark"
    except Exception:
        pass
    apply_theme(_initial_theme)
    _ui_font = {"Darwin": "SF Pro Text", "Windows": "Segoe UI"}.get(_platform.system(), "")
    app.setFont(QFont(_ui_font, 10))
    app.setApplicationName(APP_NAME)

    from app.icon_utils import app_logo_icon
    app.setWindowIcon(app_logo_icon(256))

    window = PDFReaderApp()
    startup_pdf = _startup_pdf_path(sys.argv)
    window.show()

    from packages.qt_compat.QtCore import QTimer
    from app.license_dialog import check_license_on_startup

    def _finish_startup():
        if not check_license_on_startup(window):
            window.close()
            app.quit()
            return
        if startup_pdf:
            from app.actions.file import open_file

            QTimer.singleShot(0, lambda p=startup_pdf: open_file(window, p))

    QTimer.singleShot(0, _finish_startup)
    sys.exit(app.exec())
