from __future__ import annotations

import json
import re
import sys

SERVICE_NAME = "3T Reader"
USERNAME = "license"


def _is_windows() -> bool:
    return sys.platform == "win32"


def credential_manager_save(
    data: dict,
    *,
    service_name: str = SERVICE_NAME,
    username: str = USERNAME,
) -> bool:
    if not _is_windows():
        return False
    payload = json.dumps(data)
    keyring_ok = False
    try:
        import keyring

        keyring.set_password(service_name, username, payload)
        keyring_ok = True
    except Exception:
        pass
    # Luôn ghi thêm bản dự phòng DPAPI, kể cả khi keyring thành công: việc
    # PyInstaller đóng gói metadata backend của keyring không ổn định giữa các
    # bản build, nên chỉ tin vào keyring có thể làm mất license sau khi update.
    try:
        import base64
        import ctypes
        import ctypes.wintypes

        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        encoded = payload.encode("utf-8")
        buf = ctypes.create_string_buffer(encoded)
        blob_in = DATA_BLOB(len(encoded), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
        blob_out = DATA_BLOB()
        desc = ctypes.c_wchar_p(service_name)

        ok = crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            desc,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not ok:
            return keyring_ok

        protected = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        kernel32.LocalFree(blob_out.pbData)
        _dpapi_path(service_name=service_name, username=username).write_bytes(base64.b64encode(protected))
        return True
    except Exception:
        return keyring_ok


def credential_manager_load(
    *,
    service_name: str = SERVICE_NAME,
    username: str = USERNAME,
) -> dict | None:
    if not _is_windows():
        return None
    try:
        import keyring

        raw = keyring.get_password(service_name, username)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    try:
        import base64
        import ctypes
        import ctypes.wintypes

        path = _dpapi_path(service_name=service_name, username=username)
        if not path.exists():
            return None

        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        protected = base64.b64decode(path.read_bytes())
        buf = ctypes.create_string_buffer(protected)
        blob_in = DATA_BLOB(len(protected), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
        blob_out = DATA_BLOB()

        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not ok:
            return None

        raw = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        kernel32.LocalFree(blob_out.pbData)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def credential_manager_delete(
    *,
    service_name: str = SERVICE_NAME,
    username: str = USERNAME,
) -> None:
    if not _is_windows():
        return
    try:
        import keyring

        keyring.delete_password(service_name, username)
    except Exception:
        pass
    try:
        _dpapi_path(service_name=service_name, username=username).unlink(missing_ok=True)
    except Exception:
        pass


def _dpapi_path(*, service_name: str = SERVICE_NAME, username: str = USERNAME):
    from pathlib import Path
    import os

    base = Path(os.environ.get("APPDATA", Path.home())) / "3T Reader"
    base.mkdir(parents=True, exist_ok=True)
    safe_service = re.sub(r"[^A-Za-z0-9_.-]+", "_", service_name).strip("_") or "service"
    safe_user = re.sub(r"[^A-Za-z0-9_.-]+", "_", username).strip("_") or "user"
    return base / f".{safe_service}.{safe_user}.dpapi"
