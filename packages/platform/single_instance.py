import os
import json
import socket
import socketserver
import sys
import tempfile
import threading
import zlib
from pathlib import Path

from app.config import MUTEX_NAME

_WINDOWS_MUTEX = None
_LOCK_FILE = None
_IPC_SERVER = None
_IPC_THREAD = None


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


def _ipc_port() -> int:
    """Return a deterministic localhost port for second-instance messages."""
    return 49152 + (zlib.crc32(MUTEX_NAME.encode("utf-8")) % 12000)


def send_paths_to_running_instance(paths: list[str], *, timeout: float = 1.0) -> bool:
    """Send PDF paths from a secondary process to the already-running app."""
    clean_paths = [
        os.path.abspath(os.path.expanduser(str(path).strip('"')))
        for path in paths
        if path
    ]
    if not clean_paths:
        return False

    payload = json.dumps({"open": clean_paths}, ensure_ascii=False).encode("utf-8")
    try:
        with socket.create_connection(("127.0.0.1", _ipc_port()), timeout=timeout) as sock:
            sock.sendall(payload + b"\n")
        return True
    except OSError:
        return False


def start_single_instance_server(open_paths_callback) -> None:
    """Start a small localhost server used by file association launches."""
    global _IPC_SERVER, _IPC_THREAD
    if _IPC_SERVER is not None:
        return

    class _Handler(socketserver.BaseRequestHandler):
        def handle(self):
            data = b""
            while len(data) < 1024 * 1024:
                chunk = self.request.recv(65536)
                if not chunk:
                    break
                data += chunk
                if b"\n" in chunk:
                    break
            try:
                message = json.loads(data.decode("utf-8").strip())
            except Exception:
                return
            paths = message.get("open") if isinstance(message, dict) else None
            if not isinstance(paths, list):
                return
            clean_paths = [
                os.path.abspath(os.path.expanduser(str(path).strip('"')))
                for path in paths
                if isinstance(path, str) and path.lower().endswith(".pdf") and os.path.isfile(path)
            ]
            if clean_paths:
                open_paths_callback(clean_paths)

    class _Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        _IPC_SERVER = _Server(("127.0.0.1", _ipc_port()), _Handler)
        _IPC_THREAD = threading.Thread(
            target=_IPC_SERVER.serve_forever,
            name="single-instance-ipc",
            daemon=True,
        )
        _IPC_THREAD.start()
    except OSError:
        _IPC_SERVER = None
        _IPC_THREAD = None
