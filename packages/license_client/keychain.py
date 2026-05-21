from __future__ import annotations

import json
import subprocess
import sys

_SERVICE = "3T Reader License"
_ACCOUNT = "3t-reader"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _security(*args: str) -> str:
    """Gọi macOS security CLI, trả về stdout (stripped)."""
    result = subprocess.run(
        ["security", *args],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def keychain_save(data: dict) -> bool:
    """Lưu dict vào macOS Keychain. Trả về True nếu thành công."""
    if not _is_macos():
        return False
    try:
        payload = json.dumps(data)
        # -U = update nếu đã tồn tại
        _security(
            "add-generic-password",
            "-a", _ACCOUNT,
            "-s", _SERVICE,
            "-w", payload,
            "-U",
        )
        return True
    except Exception:
        return False


def keychain_load() -> dict:
    """Đọc dict từ macOS Keychain. Trả về {} nếu không có hoặc lỗi."""
    if not _is_macos():
        return {}
    try:
        raw = _security(
            "find-generic-password",
            "-a", _ACCOUNT,
            "-s", _SERVICE,
            "-w",
        )
        return json.loads(raw)
    except Exception:
        return {}


def keychain_delete() -> bool:
    """Xóa entry khỏi Keychain. Trả về True nếu thành công."""
    if not _is_macos():
        return False
    try:
        _security(
            "delete-generic-password",
            "-a", _ACCOUNT,
            "-s", _SERVICE,
        )
        return True
    except Exception:
        return False
