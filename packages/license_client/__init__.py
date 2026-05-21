from __future__ import annotations

from .client import LicenseClient, NotConfiguredLicenseClient
from .models import ActivationResult, LicenseStatus

_client: LicenseClient | None = None


def get_license_client() -> LicenseClient:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def _build_client() -> LicenseClient:
    try:
        from app.config import VPS_LICENSE_BASE_URL  # type: ignore[import]
    except Exception:
        return NotConfiguredLicenseClient()

    if not VPS_LICENSE_BASE_URL:
        return NotConfiguredLicenseClient()

    try:
        import os, sys
        from pathlib import Path
        from .vps_client import VpsLicenseClient

        # Determine cache path without importing paths.py (avoids circular import)
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = str(Path.home() / "Library" / "Application Support")
        else:
            base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))

        cache_path = Path(base) / "3T Reader" / "license_cache.json"
        return VpsLicenseClient(VPS_LICENSE_BASE_URL, cache_path)
    except Exception:
        return NotConfiguredLicenseClient()


__all__ = [
    "ActivationResult",
    "LicenseClient",
    "LicenseStatus",
    "NotConfiguredLicenseClient",
    "get_license_client",
]
