# Audit log module - ghi log hành động vào file trong app data dir
# Log format: 2026-01-01 12:00:00 | ACTION | /path/to/file.pdf | details

import os
import threading
from datetime import datetime

from packages.platform import get_app_data_dir

# ── Action name constants ──────────────────────────────────────────────────────
ACT_OPEN      = "OPEN"
ACT_CLOSE     = "CLOSE"
ACT_PRINT     = "PRINT"
ACT_EXPORT    = "EXPORT"
ACT_ANNOTATE  = "ANNOTATE"
ACT_SIGN      = "SIGN"
ACT_OCR       = "OCR"
ACT_AI        = "AI"
ACT_MERGE     = "MERGE"
ACT_SPLIT     = "SPLIT"
ACT_WATERMARK = "WATERMARK"
ACT_PAGE_EDIT = "PAGE_EDIT"

# ── Module-level lock for thread safety ────────────────────────────────────────
_lock = threading.Lock()


def get_audit_log_path() -> str:
    """Return the absolute path to the audit log file."""
    return os.path.join(get_app_data_dir(), "audit.log")


def log_action(action: str, path: str = "", details: str = "") -> None:
    """Append one log line to the audit log.

    Format: ``{timestamp} | {action:20} | {path} | {details}\\n``

    Failures are silently ignored so the calling code never crashes.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} | {action:<20} | {path} | {details}\n"
    try:
        with _lock:
            with open(get_audit_log_path(), "a", encoding="utf-8") as fh:
                fh.write(line)
    except Exception:
        pass  # silent ignore — never crash the app


def read_recent_logs(n: int = 200) -> list[str]:
    """Return the last *n* lines of the audit log as a list of strings.

    Returns an empty list when the file does not exist or cannot be read.
    """
    log_path = get_audit_log_path()
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        return lines[-n:] if len(lines) > n else lines
    except Exception:
        return []
