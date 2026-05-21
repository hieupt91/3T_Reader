from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

_TRIAL_DAYS = 30
_SERVICE = "3T Reader Trial"
_ACCOUNT = "3t-reader-trial"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _keychain_load() -> dict:
    if not _is_macos():
        return _file_load()
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", _ACCOUNT, "-s", _SERVICE, "-w"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
    except Exception:
        pass
    return {}


def _keychain_save(data: dict) -> None:
    if not _is_macos():
        _file_save(data)
        return
    try:
        payload = json.dumps(data)
        subprocess.run(
            ["security", "add-generic-password", "-a", _ACCOUNT, "-s", _SERVICE, "-w", payload, "-U"],
            capture_output=True,
        )
    except Exception:
        pass


def _file_load() -> dict:
    """Fallback lưu file cho Windows/Linux."""
    import os
    path = _trial_file_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _file_save(data: dict) -> None:
    import os
    path = _trial_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _trial_file_path() -> str:
    import os
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "3TReader", ".trial")


def get_or_init_trial() -> dict:
    """
    Trả về thông tin dùng thử:
      {
        "first_launch": "2026-05-21T...",
        "days_used": int,
        "days_remaining": int,   # 0 nếu hết hạn
        "expired": bool,
      }
    Nếu chưa có → ghi ngày hôm nay vào Keychain và trả về ngày 1.
    """
    data = _keychain_load()
    now = datetime.now(tz=timezone.utc)

    if "first_launch" not in data:
        data = {"first_launch": now.isoformat()}
        _keychain_save(data)

    try:
        first = datetime.fromisoformat(data["first_launch"])
    except Exception:
        first = now
        data["first_launch"] = now.isoformat()
        _keychain_save(data)

    days_used = (now - first).days
    days_remaining = max(0, _TRIAL_DAYS - days_used)
    expired = days_used >= _TRIAL_DAYS

    return {
        "first_launch": data["first_launch"],
        "days_used": days_used,
        "days_remaining": days_remaining,
        "expired": expired,
    }


def is_trial_active() -> bool:
    return not get_or_init_trial()["expired"]
