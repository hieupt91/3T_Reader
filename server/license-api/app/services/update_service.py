from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os

from ..config import settings
from .token_service import TokenService


@dataclass
class UpdateService:
    token_service: TokenService
    admin_config: object = None  # AdminConfig, injected to avoid circular import

    def _sign_update_manifest(self, *, version: str, download_url: str, sha256: str) -> str:
        """Sign the canonical client update payload expected by PR6 clients."""
        key = getattr(self.token_service, "_ed25519_key", None)
        if key is None:
            return ""
        payload = {
            "download_url": download_url,
            "sha256": sha256,
            "version": version,
        }
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.b64encode(key.sign(body)).decode("ascii").rstrip("=")

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
            portable_url = cfg.get("portable_url", "")
            portable_sha256 = cfg.get("portable_sha256", "")
        else:
            latest_version = cfg.get("mac_version") or settings.default_update_version
            download_url = cfg.get("mac_url") or os.environ.get("THREET_UPDATE_URL_MAC", settings.default_update_url)
            sha256 = cfg.get("mac_sha256", "")
            portable_url = ""
            portable_sha256 = ""

        release_notes = cfg.get("release_notes", "")
        mandatory = bool(cfg.get("mandatory", False))

        manifest = {
            "platform": platform,
            "current_version": current_version,
            "latest_version": latest_version,
            "download_url": download_url,
            "sha256": sha256,
            "portable_url": portable_url,
            "portable_sha256": portable_sha256,
            "mandatory": mandatory,
            "release_notes": release_notes,
        }
        manifest["signature"] = self._sign_update_manifest(
            version=latest_version,
            download_url=download_url,
            sha256=sha256,
        )
        return manifest
