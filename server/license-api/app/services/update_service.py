from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from .token_service import TokenService


@dataclass
class UpdateService:
    token_service: TokenService

    def build_manifest(self, platform: str, current_version: str) -> dict:
        latest_version = settings.default_update_version
        download_url = settings.default_update_url
        manifest = {
            "platform": platform,
            "current_version": current_version,
            "latest_version": latest_version,
            "download_url": download_url,
            "sha256": "",
            "mandatory": False,
            "release_notes": "",
        }
        manifest["signature"] = self.token_service.sign(manifest)
        return manifest
