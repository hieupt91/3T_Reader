from __future__ import annotations

import json
import sys

SERVICE_NAME = "3T Reader"
USERNAME = "license"


def _is_windows() -> bool:
    return sys.platform == "win32"


def credential_manager_save(data: dict) -> bool:
    """Lưu dict vào Windows Credential Manager. Trả về True nếu thành công."""
    if not _is_windows():
        return False
    payload = json.dumps(data)
    try:
        import keyring
        keyring.set_password(SERVICE_NAME, USERNAME, payload)
        return True
    except Exception:
        pass
    # Fallback: DPAPI via ctypes
    try:
        import ctypes
        import ctypes.wintypes
        _crypt = ctypes.windll.crypt32  # type: ignore[attr-defined]

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        encoded = payload.encode("utf-8")
        buf = ctypes.create_string_buffer(encoded)
        blob_in = DATA_BLOB(len(encoded), buf)
        blob_out = DATA_BLOB()
        desc = ctypes.c_wchar_p(SERVICE_NAME)

        ok = _crypt.CryptProtectData(
            ctypes.byref(blob_in), desc, None, None, None, 0, ctypes.byref(blob_out)
        )
        if not ok:
            return False

        protected = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)  # type: ignore[attr-defined]

        import base64
        from pathlib import Path
        _dpapi_path().write_bytes(base64.b64encode(protected))
        return True
    except Exception:
        return False


def credential_manager_load() -> dict | None:
    """Đọc dict từ Windows Credential Manager. Trả về None nếu không có hoặc lỗi."""
    if not _is_windows():
        return None
    try:
        import keyring
        raw = keyring.get_password(SERVICE_NAME, USERNAME)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    # Fallback: DPAPI via ctypes
    try:
        import base64
        import ctypes
        import ctypes.wintypes
        path = _dpapi_path()
        if not path.exists():
            return None
        _crypt = ctypes.windll.crypt32  # type: ignore[attr-defined]

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        protected = base64.b64decode(path.read_bytes())
        buf = ctypes.create_string_buffer(protected)
        blob_in = DATA_BLOB(len(protected), buf)
        blob_out = DATA_BLOB()

        ok = _crypt.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        )
        if not ok:
            return None

        raw = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)  # type: ignore[attr-defined]
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def credential_manager_delete() -> None:
    """Xóa credential khỏi Windows Credential Manager."""
    if not _is_windows():
        return
    try:
        import keyring
        keyring.delete_password(SERVICE_NAME, USERNAME)
    except Exception:
        pass
    # Also clean up DPAPI fallback file if it exists
    try:
        _dpapi_path().unlink(missing_ok=True)
    except Exception:
        pass


def _dpapi_path():
    """Đường dẫn lưu DPAPI blob khi keyring không khả dụng."""
    from pathlib import Path
    import os
    base = Path(os.environ.get("APPDATA", Path.home())) / "3T Reader"
    base.mkdir(parents=True, exist_ok=True)
    return base / ".license_cache.dpapi"
