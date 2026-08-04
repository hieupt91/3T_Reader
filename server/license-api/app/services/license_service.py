from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..models import LicenseRecord
from .token_service import TokenService
from .state_store import FileStateStore


@dataclass
class LicenseService:
    token_service: TokenService
    state_store: FileStateStore | None = None
    licenses: dict[str, LicenseRecord] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.state_store is None:
            self.state_store = FileStateStore(f"{settings.data_dir}/{settings.state_file}")

        stored = self.state_store.load_licenses()
        if stored:
            self.licenses = stored
        elif not self.licenses:
            self.licenses = {
                "THREET-DEMO-0001": LicenseRecord("THREET-DEMO-0001", "Demo Customer", 2),
                "THREET-DEMO-ENTERPRISE": LicenseRecord("THREET-DEMO-ENTERPRISE", "Enterprise Demo", 10),
            }
            self._save()

    def _expiry(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=settings.license_duration_days)).isoformat()

    def activate(self, license_key: str, device_id: str, platform: str, app_version: str, machine_name: str | None) -> dict:
        record = self.licenses.get(license_key)
        if record is None:
            return {
                "ok": False,
                "message": "Unknown license key.",
            }

        if device_id in record.revoked_devices:
            return {
                "ok": False,
                "message": "This device is revoked.",
            }

        if device_id not in record.active_devices and len(record.active_devices) >= record.seat_limit:
            return {
                "ok": False,
                "message": "Seat limit reached.",
            }

        payload = {
            "license_key": license_key,
            "device_id": device_id,
            "platform": platform,
            "app_version": app_version,
            "machine_name": machine_name or "",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": self._expiry(),
        }
        token = self.token_service.sign(payload)
        record.active_devices[device_id] = payload
        self._save()
        return {
            "ok": True,
            "message": "Activated.",
            "token": token,
            "license_key": license_key,
            "device_id": device_id,
            "expires_at": payload["expires_at"],
            "seat_limit": record.seat_limit,
        }

    def validate(self, token: str, device_id: str) -> dict:
        try:
            payload = self.token_service.verify(token)
        except ValueError:
            return {"ok": False, "message": "Invalid token."}
        if payload.get("device_id") != device_id:
            return {"ok": False, "message": "Device mismatch."}
        if self._is_expired(payload.get("expires_at", "")):
            return {"ok": False, "message": "Token expired.", "expires_at": payload.get("expires_at")}
        return {
            "ok": True,
            "message": "Valid.",
            "license_key": payload.get("license_key"),
            "device_id": device_id,
            "expires_at": payload.get("expires_at"),
        }

    def heartbeat(self, token: str, device_id: str) -> dict:
        validation = self.validate(token, device_id)
        if not validation["ok"]:
            return validation
        validation["message"] = "Heartbeat ok."
        return validation

    def deactivate(self, token: str, device_id: str) -> dict:
        try:
            payload = self.token_service.verify(token)
        except ValueError:
            return {"ok": False, "message": "Invalid token."}
        license_key = payload.get("license_key")
        record = self.licenses.get(license_key)
        if record is None:
            return {"ok": False, "message": "Unknown license key."}
        record.active_devices.pop(device_id, None)
        record.revoked_devices.add(device_id)
        self._save()
        return {"ok": True, "message": "Deactivated."}

    @staticmethod
    def _is_expired(expires_at: str) -> bool:
        if not expires_at:
            return True
        try:
            return datetime.fromisoformat(expires_at) < datetime.now(timezone.utc)
        except ValueError:
            return True

    def _save(self) -> None:
        if self.state_store is not None:
            self.state_store.save_licenses(self.licenses)
