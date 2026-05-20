import os
import sys
import tempfile
from pathlib import Path

from app.config import MUTEX_NAME

_WINDOWS_MUTEX = None
_LOCK_FILE = None
_ERROR_ALREADY_EXISTS = 183


def _windows_mutex_name() -> str:
    if MUTEX_NAME.startswith(("Local\\", "Global\\")):
        return MUTEX_NAME
    return f"Local\\{MUTEX_NAME}"


def acquire_single_instance() -> bool:
    """Return False when another app instance is already running."""
    if sys.platform == "win32":
        return _acquire_windows_mutex()
    return _acquire_portable_lock()


def _acquire_windows_mutex() -> bool:
    global _WINDOWS_MUTEX
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.GetLastError.restype = ctypes.c_ulong
        _WINDOWS_MUTEX = kernel32.CreateMutexW(None, False, _windows_mutex_name())
        if not _WINDOWS_MUTEX:
            return True
        return kernel32.GetLastError() != _ERROR_ALREADY_EXISTS
    except Exception:
        return True


def _acquire_portable_lock() -> bool:
    global _LOCK_FILE
    try:
        lock_path = Path(tempfile.gettempdir()) / f"{MUTEX_NAME}.lock"
        _LOCK_FILE = open(lock_path, "w", encoding="utf-8")
        if sys.platform == "darwin" or os.name == "posix":
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
