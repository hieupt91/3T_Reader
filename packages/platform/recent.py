"""Recent files management — stores last N opened file paths."""

import json
import os

from .paths import get_app_data_dir

RECENT_FILE = os.path.join(get_app_data_dir(), "recent_files.json")
MAX_RECENT = 12


def _recent_path() -> str:
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
