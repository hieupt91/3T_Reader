from __future__ import annotations

import hashlib
import platform
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .manifest import UpdateManifest

_TIMEOUT = 10


def _current_platform() -> str:
    if sys.platform == "darwin":
        return "mac"
    if sys.platform == "win32":
        return "windows"
    return "linux"


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


@dataclass
class UpdateInfo:
    available: bool
    current_version: str = ""
    latest_version: str = ""
    download_url: str = ""
    release_notes: str = ""
    error: Optional[str] = None


@dataclass
class UpdateResult:
    success: bool
    path: Optional[str] = None
    error: Optional[str] = None


def check_for_update(base_url: str, current_version: str, channel: str = "stable") -> UpdateInfo:
    try:
        import requests
        plat = _current_platform()
        url = (
            f"{base_url.rstrip('/')}/api/v1/update/check"
            f"?platform={plat}&current_version={current_version}"
        )
        resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": "3T-Reader/1.0"})
        resp.raise_for_status()
        data = resp.json()

        latest = data.get("version", "")
        if not latest or not _is_newer(latest, current_version):
            return UpdateInfo(available=False, current_version=current_version, latest_version=latest)

        return UpdateInfo(
            available=True,
            current_version=current_version,
            latest_version=latest,
            download_url=data.get("download_url", ""),
            release_notes=data.get("release_notes", ""),
        )
    except Exception as e:
        return UpdateInfo(available=False, current_version=current_version, error=str(e))


def download_update(info: UpdateInfo) -> UpdateResult:
    if not info.available or not info.download_url:
        return UpdateResult(success=False, error="Không có bản cập nhật để tải.")
    try:
        import requests
        resp = requests.get(info.download_url, timeout=120, stream=True, headers={"User-Agent": "3T-Reader/1.0"})
        resp.raise_for_status()

        default_suffix = ".exe" if sys.platform == "win32" else ".dmg"
        suffix = Path(info.download_url).suffix or default_suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="3TReader_update_")
        hasher = hashlib.sha256()
        for chunk in resp.iter_content(chunk_size=65536):
            tmp.write(chunk)
            hasher.update(chunk)
        tmp.close()

        return UpdateResult(success=True, path=tmp.name)
    except Exception as e:
        return UpdateResult(success=False, error=str(e))
