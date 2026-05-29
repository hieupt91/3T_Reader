import json
import os

def get_app_data_dir():
    """Backward-compatible wrapper for the shared platform path adapter."""
    from packages.platform import get_app_data_dir as _get_app_data_dir

    return _get_app_data_dir()

RECENT_FILE = os.path.join(get_app_data_dir(), "recent_files.json")
MAX_RECENT = 5

def _recent_path() -> str:
    """Backward-compatible path helper used by platform smoke tests."""
    return RECENT_FILE

def load_recent() -> list:
    if os.path.exists(RECENT_FILE):
        try:
            with open(RECENT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []

def save_recent(path: str):
    recent = load_recent()
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    with open(RECENT_FILE, "w", encoding="utf-8") as f:
        json.dump(recent[:MAX_RECENT], f, ensure_ascii=False)

def clear_recent():
    with open(RECENT_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)
