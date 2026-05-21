from __future__ import annotations

import json
import platform
import socket
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .fingerprint import get_device_fingerprint
from .models import ActivationResult, LicenseStatus

_TIMEOUT = 8  # seconds


def _post(base_url: str, path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "3T-Reader/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


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
    """License client that calls the 3T Reader VPS backend."""

    def __init__(self, base_url: str, cache_path: str | Path) -> None:
        self._base = base_url.rstrip("/")
        self._cache = Path(cache_path)
        self._device_id = get_device_fingerprint()

    # ── cache helpers ─────────────────────────────────────────────

    def _load_cache(self) -> dict:
        try:
            return json.loads(self._cache.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_cache(self, data: dict) -> None:
        self._cache.parent.mkdir(parents=True, exist_ok=True)
        self._cache.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ── public interface ──────────────────────────────────────────

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
            return self._offline_status(cache)

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
            return self._offline_status(cache)

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

        self._cache.unlink(missing_ok=True)

    # ── offline fallback ──────────────────────────────────────────

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
