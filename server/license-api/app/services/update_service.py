from __future__ import annotations

from dataclasses import dataclass
import os

from ..config import settings
from .token_service import TokenService


@dataclass
class UpdateService:
    token_service: TokenService
    admin_config: object = None  # AdminConfig, injected to avoid circular import

    def build_manifest(self, platform: str, current_version: str) -> dict:
        # Read from admin_config first (set via admin panel), then env vars, then settings
        cfg = {}
        if self.admin_config is not None:
            try:
                cfg = self.admin_config.get_update_config()
            except Exception:
                cfg = {}

        is_win = platform.lower() in ("win", "windows")

        if is_win:
            latest_version = cfg.get("win_version") or cfg.get("mac_version") or settings.default_update_version
            download_url = cfg.get("win_url") or os.environ.get("THREET_UPDATE_URL_WIN", settings.default_update_url)
            sha256 = cfg.get("win_sha256", "")
        else:
            latest_version = cfg.get("mac_version") or settings.default_update_version
            download_url = cfg.get("mac_url") or os.environ.get("THREET_UPDATE_URL_MAC", settings.default_update_url)
            sha256 = cfg.get("mac_sha256", "")

        release_notes = cfg.get("release_notes", "")
        mandatory = bool(cfg.get("mandatory", False))

        manifest = {
            "platform": platform,
            "current_version": current_version,
            "latest_version": latest_version,
            "download_url": download_url,
            "sha256": sha256,
            "mandatory": mandatory,
            "release_notes": release_notes,
        }
        manifest["signature"] = self.token_service.sign(manifest)
        return manifest
