from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

from .credential_manager import credential_manager_load, credential_manager_save

_TRIAL_DAYS = 30
_SERVICE = "3T Reader Trial"
_ACCOUNT = "3t-reader-trial"
_TRIAL_USERNAME = "trial"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _keychain_load() -> dict:
    if not _is_macos():
        return {}
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", _ACCOUNT, "-s", _SERVICE, "-w"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
    except Exception:
        pass
    return {}


def _keychain_save(data: dict) -> None:
    if not _is_macos():
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
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _trial_file_path() -> str:
    import os

    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    return os.path.join(base, "3TReader", ".trial")


def _merge_trial_data(*items: dict) -> dict:
    merged: dict = {}
    first_values = []
    seen_values = []
    for item in items:
        if not isinstance(item, dict):
            continue
        first_launch = item.get("first_launch")
        if first_launch:
            first_values.append(first_launch)
        last_seen = item.get("last_seen_at")
        if last_seen:
            seen_values.append(last_seen)
    if first_values:
        merged["first_launch"] = min(first_values)
    if seen_values:
        merged["last_seen_at"] = max(seen_values)
    return merged


def _storage_load() -> dict:
    if _is_macos():
        return _merge_trial_data(_keychain_load())
    if _is_windows():
        secure = credential_manager_load(service_name=_SERVICE, username=_TRIAL_USERNAME) or {}
        return _merge_trial_data(secure, _file_load())
    return _merge_trial_data(_file_load())


def _storage_save(data: dict) -> None:
    if _is_macos():
        _keychain_save(data)
        return
    if _is_windows():
        credential_manager_save(data, service_name=_SERVICE, username=_TRIAL_USERNAME)
        _file_save(data)
        return
    _file_save(data)


def _normalized_trial_data(data: dict, now: datetime) -> dict:
    normalized = dict(data or {})
    if "first_launch" not in normalized:
        normalized["first_launch"] = now.isoformat()
    try:
        first = datetime.fromisoformat(normalized["first_launch"])
    except Exception:
        first = now
        normalized["first_launch"] = now.isoformat()
    try:
        last_seen = (
            datetime.fromisoformat(normalized.get("last_seen_at", ""))
            if normalized.get("last_seen_at")
            else first
        )
    except Exception:
        last_seen = first
    effective_now = max(now, last_seen)
    normalized["last_seen_at"] = effective_now.isoformat()
    return normalized


def start_trial() -> dict:
    data = _storage_load()
    if "first_launch" not in data:
        now = _utcnow()
        data["first_launch"] = now.isoformat()
        data["last_seen_at"] = now.isoformat()
        _storage_save(data)
    return get_or_init_trial()


def has_trial_started() -> bool:
    return "first_launch" in _storage_load()


def get_or_init_trial() -> dict:
    now = _utcnow()
    data = _normalized_trial_data(_storage_load(), now)
    _storage_save(data)

    first = datetime.fromisoformat(data["first_launch"])
    effective_now = datetime.fromisoformat(data["last_seen_at"])
    days_used = max(0, (effective_now - first).days)
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
