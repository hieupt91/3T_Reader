from __future__ import annotations

import json
import platform
import socket
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .credential_manager import (
    credential_manager_delete,
    credential_manager_load,
    credential_manager_save,
)
from .fingerprint import get_device_fingerprint
from .keychain import keychain_delete, keychain_load, keychain_save
from .models import ActivationResult, LicenseStatus

_CONNECT_TIMEOUT = 6
_READ_TIMEOUT = 10
_USE_KEYCHAIN = platform.system() == "Darwin"
_USE_CREDENTIAL_MANAGER = platform.system() == "Windows"
_DEFAULT_GRACE_DAYS = 7
_MAX_GRACE_DAYS = 30

_session = None
_session_lock = threading.Lock()


def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                import requests

                s = requests.Session()
                s.headers.update({"User-Agent": "3T-Reader/1.0"})
                _session = s
    return _session


def _post(base_url: str, path: str, payload: dict) -> dict:
    from requests.exceptions import ConnectionError, Timeout

    url = f"{base_url.rstrip('/')}{path}"
    try:
        resp = _get_session().post(
            url,
            json=payload,
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
        )
    except Timeout:
        raise RuntimeError("Ket noi qua cham hoac may chu khong phan hoi. Vui long thu lai.")
    except ConnectionError:
        raise RuntimeError("Khong the ket noi may chu. Kiem tra ket noi internet.")
    except OSError:
        raise RuntimeError("Loi mang. Kiem tra ket noi internet va thu lai.")
    if not resp.ok:
        try:
            body = resp.json()
            detail = body.get("detail")
            if isinstance(detail, list):
                msg = "; ".join([d.get("msg", str(d)) if isinstance(d, dict) else str(d) for d in detail])
            else:
                msg = detail or body.get("message") or f"Loi {resp.status_code}"
        except Exception:
            msg = f"Loi {resp.status_code}"
        raise RuntimeError(str(msg))
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


def _normalize_grace_days(value, default: int = _DEFAULT_GRACE_DAYS) -> int:
    try:
        days = int(value)
    except Exception:
        days = default
    return max(0, min(_MAX_GRACE_DAYS, days))


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class VpsLicenseClient:
    def __init__(self, base_url: str, cache_path: str | Path) -> None:
        self._base = base_url.rstrip("/")
        self._cache = Path(cache_path)
        self._device_id = get_device_fingerprint()
        self._background_validate_lock = threading.Lock()
        self._background_validate_in_flight = False

    def _load_cache(self) -> dict:
        if _USE_KEYCHAIN:
            data = keychain_load()
            if data:
                return data
        elif _USE_CREDENTIAL_MANAGER:
            data = credential_manager_load()
            if data:
                return data
        try:
            return json.loads(self._cache.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_cache(self, data: dict) -> None:
        if _USE_KEYCHAIN:
            if keychain_save(data):
                return
        elif _USE_CREDENTIAL_MANAGER:
            if credential_manager_save(data):
                return
        self._cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._cache.with_suffix(self._cache.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self._cache)

    def _clear_cache(self) -> None:
        if _USE_KEYCHAIN:
            keychain_delete()
        elif _USE_CREDENTIAL_MANAGER:
            credential_manager_delete()
        self._cache.unlink(missing_ok=True)

    def _verify_offline(self, cache: dict) -> LicenseStatus | None:
        token = cache.get("token", "")
        try:
            from .token_verifier import is_ed25519_token, verify_token_offline

            if not is_ed25519_token(token):
                return None
            payload = verify_token_offline(token)
            expires_at = _parse_dt(payload.get("expires_at"))
            grace_days = _normalize_grace_days(payload.get("grace_days"))
            grace_until = (expires_at + timedelta(days=grace_days)) if expires_at else None

            if grace_until and _utcnow() > grace_until:
                return LicenseStatus(
                    active=False,
                    message="License het han - lien he 3T Company de gia han.",
                )
            return LicenseStatus(
                active=True,
                plan_code=cache.get("plan_code", payload.get("license_key", "")),
                expires_at=expires_at,
                offline_grace_until=grace_until,
                message="",
            )
        except Exception:
            return None

    def activate(self, license_key: str, email: str, device_fingerprint: str) -> ActivationResult:
        del email
        device_id = device_fingerprint or self._device_id
        payload = {
            "license_key": license_key,
            "device_id": device_id,
            "platform": platform.system().lower(),
            "app_version": _app_version(),
            "machine_name": socket.gethostname(),
        }
        resp = _post(self._base, "/api/v1/license/activate", payload)
        if resp.get("status") != "ok" and "token" not in resp:
            raise RuntimeError(resp.get("message", "Kích hoạt thất bại."))

        token = resp["token"]
        expires_at = _parse_dt(resp.get("expires_at"))
        grace_days = _normalize_grace_days(resp.get("grace_days"))
        grace_until = (expires_at + timedelta(days=grace_days)) if expires_at else None
        plan_code = resp.get("plan")
        if not plan_code:
            if license_key.startswith("3TR-E"):
                plan_code = "enterprise"
            elif license_key.startswith("3TR-P"):
                plan_code = "personal"
            elif license_key.startswith("3TR-B"):
                plan_code = "basic"
            else:
                plan_code = "free"

        self._save_cache(
            {
                "token": token,
                "device_id": device_id,
                "license_key": license_key,
                "plan_code": plan_code,
                "expires_at": resp.get("expires_at", ""),
                "grace_days": grace_days,
            }
        )

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
            return LicenseStatus(active=False, message="Chua kich hoat license.")

        offline = self._verify_offline(cache)
        if offline is not None:
            if offline.active:
                self._validate_server_background(token, cache)
            return offline

        # Đối với token cũ (không phải Ed25519), KHÔNG block main thread.
        # Trả về trạng thái từ cache ngay lập tức và gọi server ở background.
        status = self._offline_status(cache)
        if status.active:
            self._validate_server_background(token, cache)
        return status

    def _validate_server(self, token: str, cache: dict) -> LicenseStatus:
        resp = _post(
            self._base,
            "/api/v1/license/validate",
            {"token": token, "device_id": cache.get("device_id", self._device_id)},
        )
        if not resp.get("valid"):
            return LicenseStatus(active=False, message=resp.get("message", "License khong hop le."))

        expires_at = _parse_dt(resp.get("expires_at"))
        grace_days = _normalize_grace_days(resp.get("grace_days"))
        refreshed_cache = dict(cache)
        refreshed_cache.update(
            {
                "plan_code": resp.get("plan") or cache.get("plan_code", "free"),
                "expires_at": resp.get("expires_at", cache.get("expires_at", "")),
                "grace_days": grace_days,
            }
        )
        self._save_cache(refreshed_cache)
        return LicenseStatus(
            active=True,
            plan_code=refreshed_cache.get("plan_code", ""),
            expires_at=expires_at,
            offline_grace_until=(expires_at + timedelta(days=grace_days)) if expires_at else None,
            message=resp.get("message", ""),
        )

    def _validate_server_background(self, token: str, cache: dict) -> None:
        with self._background_validate_lock:
            if self._background_validate_in_flight:
                return
            self._background_validate_in_flight = True

        def _run():
            try:
                self._validate_server(token, cache)
            except Exception:
                pass
            finally:
                with self._background_validate_lock:
                    self._background_validate_in_flight = False

        threading.Thread(target=_run, daemon=True).start()

    def heartbeat(self) -> LicenseStatus:
        cache = self._load_cache()
        token = cache.get("token")
        if not token:
            return LicenseStatus(active=False, message="Chua kich hoat.")

        try:
            resp = _post(
                self._base,
                "/api/v1/license/heartbeat",
                {"token": token, "device_id": cache.get("device_id", self._device_id)},
            )
            return LicenseStatus(
                active=bool(resp.get("ok", False)),
                plan_code=resp.get("plan", cache.get("plan_code", "free")),
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
                pass
        self._clear_cache()

    def _offline_status(self, cache: dict) -> LicenseStatus:
        expires_at = _parse_dt(cache.get("expires_at", ""))
        grace_days = _DEFAULT_GRACE_DAYS
        grace_until = (expires_at + timedelta(days=grace_days)) if expires_at else None

        if grace_until and _utcnow() > grace_until:
            return LicenseStatus(
                active=False,
                message="License het grace period - kiem tra ket noi voi may chu.",
            )
        return LicenseStatus(
            active=True,
            plan_code=cache.get("plan_code", ""),
            expires_at=expires_at,
            offline_grace_until=grace_until,
            message="Offline - se xac thuc lai khi co ket noi.",
        )
