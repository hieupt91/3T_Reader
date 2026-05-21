from __future__ import annotations

import json
import platform
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .fingerprint import get_device_fingerprint
from .keychain import keychain_delete, keychain_load, keychain_save
from .models import ActivationResult, LicenseStatus

_TIMEOUT = 8  # seconds
_USE_KEYCHAIN = platform.system() == "Darwin"


def _post(base_url: str, path: str, payload: dict) -> dict:
    import requests
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.post(
        url,
        json=payload,
        headers={"User-Agent": "3T-Reader/1.0"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _app_version() -> str:
    try:
        from app.version import APP_VERSION  # type: ignore[import]
        return APP_VERSION
    except Exception:
        return "1.0.0"


class VpsLicenseClient:
    """License client gọi VPS backend. macOS dùng Keychain; các nền tảng khác dùng JSON cache."""

    def __init__(self, base_url: str, cache_path: str | Path) -> None:
        self._base = base_url.rstrip("/")
        self._cache = Path(cache_path)
        self._device_id = get_device_fingerprint()

    # ── storage: Keychain (macOS) hoặc JSON file ─────────────────────

    def _load_cache(self) -> dict:
        if _USE_KEYCHAIN:
            data = keychain_load()
            if data:
                return data
        try:
            return json.loads(self._cache.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_cache(self, data: dict) -> None:
        if _USE_KEYCHAIN:
            if keychain_save(data):
                return  # Keychain OK, không cần JSON
        self._cache.parent.mkdir(parents=True, exist_ok=True)
        self._cache.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _clear_cache(self) -> None:
        if _USE_KEYCHAIN:
            keychain_delete()
        self._cache.unlink(missing_ok=True)

    # ── offline token verification ────────────────────────────────────

    def _verify_offline(self, cache: dict) -> LicenseStatus | None:
        """Verify token Ed25519 offline. Trả về None nếu token không phải Ed25519."""
        token = cache.get("token", "")
        try:
            from .token_verifier import is_ed25519_token, verify_token_offline
            if not is_ed25519_token(token):
                return None
            payload = verify_token_offline(token)
            expires_at = _parse_dt(payload.get("expires_at"))
            grace_days = int(cache.get("grace_days", 7))
            grace_until = (expires_at + timedelta(days=grace_days)) if expires_at else None

            if grace_until and datetime.now(tz=timezone.utc) > grace_until:
                return LicenseStatus(
                    active=False,
                    message="License hết hạn — liên hệ 3T Company để gia hạn.",
                )
            return LicenseStatus(
                active=True,
                plan_code=cache.get("plan_code", payload.get("license_key", "")),
                expires_at=expires_at,
                offline_grace_until=grace_until,
                message="Offline — xác thực bằng chữ ký cục bộ.",
            )
        except Exception:
            return None

    # ── public interface ──────────────────────────────────────────────

    def activate(self, license_key: str, email: str, device_fingerprint: str) -> ActivationResult:
        device_id = device_fingerprint or self._device_id
        payload = {
            "license_key": license_key,
            "device_id": device_id,
            "platform": platform.system().lower(),
            "app_version": _app_version(),
            "machine_name": socket.gethostname(),
        }
        resp = _post(self._base, "/api/v1/license/activate", payload)
        if resp.get("status") != "ok":
            raise RuntimeError(resp.get("message", "Kích hoạt thất bại."))

        token = resp["token"]
        expires_at = _parse_dt(resp.get("expires_at"))
        grace_days = int(resp.get("grace_days") or 7)
        grace_until = (expires_at + timedelta(days=grace_days)) if expires_at else None
        plan_code = resp.get("license_key", license_key)

        self._save_cache({
            "token": token,
            "device_id": device_id,
            "license_key": license_key,
            "plan_code": plan_code,
            "expires_at": resp.get("expires_at", ""),
            "grace_days": grace_days,
        })

        status = LicenseStatus(
            active=True,
            plan_code=plan_code,
            expires_at=expires_at,
            offline_grace_until=grace_until,
            message=resp.get("message", ""),
        )
        return ActivationResult(
            activation_id=resp.get("device_id", device_id),
            signed_token=token,
            status=status,
        )

    def validate_cached(self) -> LicenseStatus:
        cache = self._load_cache()
        token = cache.get("token")
        if not token:
            return LicenseStatus(active=False, message="Chưa kích hoạt license.")

        try:
            resp = _post(
                self._base,
                "/api/v1/license/validate",
                {"token": token, "device_id": cache.get("device_id", self._device_id)},
            )
            if not resp.get("valid"):
                return LicenseStatus(active=False, message=resp.get("message", "License không hợp lệ."))

            expires_at = _parse_dt(resp.get("expires_at"))
            grace_days = int(resp.get("grace_days") or cache.get("grace_days", 7))
            return LicenseStatus(
                active=True,
                plan_code=resp.get("license_key") or cache.get("plan_code", ""),
                expires_at=expires_at,
                offline_grace_until=(expires_at + timedelta(days=grace_days)) if expires_at else None,
                message=resp.get("message", ""),
            )
        except Exception:
            # VPS không reach — thử verify offline bằng Ed25519
            offline = self._verify_offline(cache)
            return offline if offline is not None else self._offline_status(cache)

    def heartbeat(self) -> LicenseStatus:
        cache = self._load_cache()
        token = cache.get("token")
        if not token:
            return LicenseStatus(active=False, message="Chưa kích hoạt.")

        try:
            resp = _post(
                self._base,
                "/api/v1/license/heartbeat",
                {"token": token, "device_id": cache.get("device_id", self._device_id)},
            )
            return LicenseStatus(
                active=bool(resp.get("ok", False)),
                plan_code=cache.get("plan_code", ""),
                message=resp.get("message", ""),
            )
        except Exception:
            offline = self._verify_offline(cache)
            return offline if offline is not None else self._offline_status(cache)

    def deactivate(self) -> None:
        cache = self._load_cache()
        token = cache.get("token")
        if token:
            try:
                _post(
                    self._base,
                    "/api/v1/license/deactivate",
                    {
                        "token": token,
                        "device_id": cache.get("device_id", self._device_id),
                        "reason": "user_requested",
                    },
                )
            except Exception:
                pass  # best-effort

        self._clear_cache()

    # ── offline fallback (không có Ed25519 token) ─────────────────────

    def _offline_status(self, cache: dict) -> LicenseStatus:
        expires_at = _parse_dt(cache.get("expires_at", ""))
        grace_days = int(cache.get("grace_days", 7))
        grace_until = (expires_at + timedelta(days=grace_days)) if expires_at else None

        if grace_until and datetime.now(tz=timezone.utc) > grace_until:
            return LicenseStatus(
                active=False,
                message="License hết grace period — kiểm tra kết nối với máy chủ.",
            )
        return LicenseStatus(
            active=True,
            plan_code=cache.get("plan_code", ""),
            expires_at=expires_at,
            offline_grace_until=grace_until,
            message="Offline — sẽ xác thực lại khi có kết nối.",
        )
