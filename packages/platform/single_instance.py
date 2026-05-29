import os
import sys
import tempfile
from pathlib import Path

from app.config import MUTEX_NAME

_WINDOWS_MUTEX = None
_LOCK_FILE = None


def acquire_single_instance() -> bool:
    """Return False when another app instance is already running."""
    if sys.platform == "win32":
        return _acquire_windows_mutex()
    return _acquire_portable_lock()


def _windows_mutex_name() -> str:
    return f"Local\\{MUTEX_NAME}"


def _acquire_windows_mutex() -> bool:
    global _WINDOWS_MUTEX
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        _WINDOWS_MUTEX = kernel32.CreateMutexW(None, False, _windows_mutex_name())
        return kernel32.GetLastError() != 183
    except Exception:
        return True


def _acquire_portable_lock() -> bool:
    """File-lock dùng cho macOS / Linux. Windows dùng mutex riêng."""
    global _LOCK_FILE
    try:
        lock_path = Path(tempfile.gettempdir()) / f"{MUTEX_NAME}.lock"
        _LOCK_FILE = open(lock_path, "w", encoding="utf-8")
        # fcntl chỉ có trên POSIX — Windows đã được xử lý ở _acquire_windows_mutex
        if sys.platform != "win32":
            import fcntl
            try:
                fcntl.flock(_LOCK_FILE.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
        _LOCK_FILE.write(str(os.getpid()))
        _LOCK_FILE.flush()
        return True
    except Exception:
        return True
