"""Backward-compatible re-export — actual implementation in packages.platform.recent."""

from packages.platform.recent import (
    RECENT_FILE,
    MAX_RECENT,
    _recent_path,
    load_recent,
    save_recent,
    clear_recent,
)

__all__ = ["RECENT_FILE", "MAX_RECENT", "_recent_path", "load_recent", "save_recent", "clear_recent"]
