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

    def _sign_code_package(self, *, base_version: str, code_url: str, code_sha256: str) -> str:
        """B53: chữ ký RIÊNG cho code package - payload khác hẳn
        _sign_update_manifest() (full installer) để không có chuyện 1 chữ ký
        hợp lệ cho payload này lại được chấp nhận nhầm cho payload khác. Xem
        docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md mục 1.3."""
        key = getattr(self.token_service, "_ed25519_key", None)
        if key is None:
            return ""
        payload = {
            "base_version": base_version,
            "code_package_sha256": code_sha256,
            "code_package_url": code_url,
        }
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.b64encode(key.sign(body)).decode("ascii").rstrip("=")

    def build_manifest_v2(self, platform: str, current_version: str, current_base_version: str) -> dict:
        """B53: manifest cho route delta-update (/api/v2/update/check) -
        HOÀN TOÀN tách biệt build_manifest() (v1) ở trên, không sửa hay dùng
        chung state nào với nó. Mặc định an toàn: delta_enabled=False trên
        admin_config -> update_type luôn "full"/"none", hành vi y hệt v1 cho
        tới khi chủ động bật. Xem docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md."""
        cfg = {}
        if self.admin_config is not None:
            try:
                cfg = self.admin_config.get_update_config()
            except Exception:
                cfg = {}

        is_win = platform.lower() in ("win", "windows")
        prefix = "win" if is_win else "mac"

        latest_version = cfg.get(f"{prefix}_version") or settings.default_update_version
        full_url = cfg.get(f"{prefix}_url") or os.environ.get(f"THREET_UPDATE_URL_{prefix.upper()}", settings.default_update_url)
        full_sha256 = cfg.get(f"{prefix}_sha256", "")
        server_base_version = cfg.get(f"{prefix}_base_version", "base-1.0")
        code_url = cfg.get(f"{prefix}_code_url", "")
        code_sha256 = cfg.get(f"{prefix}_code_sha256", "")
        delta_enabled = bool(cfg.get("delta_enabled", False))

        has_update = latest_version != current_version
        can_delta = (
            delta_enabled
            and bool(code_url)
            and bool(code_sha256)
            and current_base_version == server_base_version
            and has_update
        )
        if can_delta:
            update_type = "delta"
        elif has_update:
            update_type = "full"
        else:
            update_type = "none"

        manifest = {
            "platform": platform,
            "current_version": current_version,
            "current_base_version": current_base_version,
            "latest_version": latest_version,
            "update_type": update_type,
            "download_url": full_url,
            "sha256": full_sha256,
            "base_version": server_base_version,
            "code_package_url": code_url if update_type == "delta" else "",
            "code_package_sha256": code_sha256 if update_type == "delta" else "",
            "mandatory": bool(cfg.get("mandatory", False)),
            "release_notes": cfg.get("release_notes", ""),
        }
        manifest["signature"] = self._sign_update_manifest(
            version=latest_version,
            download_url=full_url,
            sha256=full_sha256,
        )
        manifest["code_signature"] = (
            self._sign_code_package(
                base_version=server_base_version,
                code_url=manifest["code_package_url"],
                code_sha256=manifest["code_package_sha256"],
            )
            if update_type == "delta"
            else ""
        )
        return manifest
