from __future__ import annotations

import hashlib
import os
import platform
import socket
import uuid


def _stable_mac() -> str | None:
    node = uuid.getnode()
    if node & 0x010000000000:
        return None
    return f"{node:012x}"


def _windows_machine_guid() -> str | None:
    if platform.system() != "Windows":
        return None
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        value = str(value).strip()
        return value or None
    except Exception:
        return None


def get_device_fingerprint() -> str:
    parts = [
        _windows_machine_guid(),
        _stable_mac(),
        os.environ.get("COMPUTERNAME") or socket.gethostname(),
        platform.system(),
        platform.machine(),
    ]
    normalized = [part for part in parts if part]
    return hashlib.sha256("|".join(normalized).encode("utf-8")).hexdigest()[:32]
