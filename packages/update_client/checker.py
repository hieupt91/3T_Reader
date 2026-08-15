from __future__ import annotations

import sys

from packages.updater.update_client import (
    UpdateInfo,
    UpdateResult,
    check_for_update as _check_for_update,
    download_update,
)


def _current_platform() -> str:
    if sys.platform == "darwin":
        return "mac"
    if sys.platform == "win32":
        return "win"
    return "linux"


def check_for_update(base_url: str, current_version: str, channel: str = "stable") -> UpdateInfo:
    """Compatibility wrapper for the legacy packages.update_client import path.

    The implementation lives in packages.updater.update_client so all callers
    share the signed-manifest and SHA-256 verification path.
    """
    return _check_for_update(base_url, current_version, platform=_current_platform())
