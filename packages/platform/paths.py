import os
import sys
from pathlib import Path

from app.config import APP_DATA_DIR_NAME


def _ensure(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_app_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return _ensure(Path(base) / APP_DATA_DIR_NAME)
    if sys.platform == "darwin":
        return _ensure(Path.home() / "Library" / "Application Support" / APP_DATA_DIR_NAME)
    return _ensure(Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DATA_DIR_NAME)


def get_cache_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return _ensure(Path(base) / APP_DATA_DIR_NAME / "Cache")
    if sys.platform == "darwin":
        return _ensure(Path.home() / "Library" / "Caches" / APP_DATA_DIR_NAME)
    return _ensure(Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP_DATA_DIR_NAME)


def get_log_dir() -> str:
    if sys.platform == "darwin":
        return _ensure(Path.home() / "Library" / "Logs" / APP_DATA_DIR_NAME)
    return _ensure(Path(get_app_data_dir()) / "logs")
