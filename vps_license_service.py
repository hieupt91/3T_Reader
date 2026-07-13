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

    def _expiry_from(self, anchor: datetime) -> str:
        return (anchor + timedelta(days=settings.license_duration_days)).isoformat()

    @staticmethod
    def _first_activation_anchor(record: LicenseRecord, now: datetime) -> datetime:
        """Anchor for license expiry: the very first activation, never reset
        by uninstall/re-activate (TC41)."""
        stored = getattr(record, "first_activated_at", None)
        if not stored:
            # Backfill from any device payload issued before this field existed.
            stored = min(
                (
                    str(p.get("issued_at"))
                    for p in record.active_devices.values()
                    if p.get("issued_at")
                ),
                default=None,
            )
        if stored:
            try:
                return datetime.fromisoformat(stored)
            except ValueError:
                pass
        return now

    @staticmethod
    def _normalized_machine_name(machine_name: str | None) -> str:
        return str(machine_name or "").strip().lower()

    def _find_reusable_device_id(
        self,
        record: LicenseRecord,
        *,
        device_id: str,
        platform: str,
        machine_name: str | None,
    ) -> str | None:
        normalized_name = self._normalized_machine_name(machine_name)
        normalized_platform = str(platform or "").strip().lower()
        if not normalized_name:
            return None
        for existing_device_id, payload in record.active_devices.items():
            if existing_device_id == device_id:
                return existing_device_id
            existing_name = self._normalized_machine_name(payload.get("machine_name"))
            existing_platform = str(payload.get("platform") or "").strip().lower()
            if existing_name == normalized_name and existing_platform == normalized_platform:
                return existing_device_id
        return None

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

        reusable_device_id = self._find_reusable_device_id(
            record,
            device_id=device_id,
            platform=platform,
            machine_name=machine_name,
        )

        if reusable_device_id and reusable_device_id != device_id:
            existing_payload = dict(record.active_devices.pop(reusable_device_id))
            existing_payload["device_id"] = device_id
            record.active_devices[device_id] = existing_payload

        if device_id not in record.active_devices and len(record.active_devices) >= record.seat_limit:
            return {
                "ok": False,
                "message": "Seat limit reached.",
            }

        now = datetime.now(timezone.utc)
        anchor = self._first_activation_anchor(record, now)
        expires_at = self._expiry_from(anchor)
        if self._is_expired(expires_at):
            return {
                "ok": False,
                "message": "License expired.",
                "expires_at": expires_at,
            }
        record.first_activated_at = anchor.isoformat()

        payload = {
            "license_key": license_key,
            "device_id": device_id,
            "platform": platform,
            "app_version": app_version,
            "machine_name": machine_name or "",
            "issued_at": now.isoformat(),
            "activated_at": anchor.isoformat(),
            "expires_at": expires_at,
        }
        token = self.token_service.sign(payload)
        record.active_devices[device_id] = payload
        record.revoked_devices.discard(device_id)
        self._save()
        return {
            "ok": True,
            "message": "Activated.",
            "token": token,
            "license_key": license_key,
            "device_id": device_id,
            "expires_at": payload["expires_at"],
            "seat_limit": record.seat_limit,
            "plan": getattr(record, "plan", "personal"),
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
        license_key = payload.get("license_key")
        record = self.licenses.get(license_key) if license_key else None
        return {
            "ok": True,
            "message": "Valid.",
            "license_key": license_key,
            "device_id": device_id,
            "expires_at": payload.get("expires_at"),
            "plan": getattr(record, "plan", "personal") if record else "free",
        }

    def heartbeat(self, token: str, device_id: str) -> dict:
        validation = self.validate(token, device_id)
        if not validation["ok"]:
            return validation
        validation["message"] = "Heartbeat ok."
        return validation

    def deactivate(self, token: str, device_id: str, reason: str | None = None) -> dict:
        try:
            payload = self.token_service.verify(token)
        except ValueError:
            return {"ok": False, "message": "Invalid token."}
        license_key = payload.get("license_key")
        record = self.licenses.get(license_key)
        if record is None:
            return {"ok": False, "message": "Unknown license key."}
        record.active_devices.pop(device_id, None)
        if str(reason or "").strip().lower() not in {"user_requested", "app_reinstall", "app_uninstall"}:
            record.revoked_devices.add(device_id)
        else:
            record.revoked_devices.discard(device_id)
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
