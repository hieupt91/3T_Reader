from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from ..models import LicenseRecord


class FileStateStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def load_licenses(self) -> dict[str, LicenseRecord]:
        with self._lock:
            if not self.path.exists():
                return {}
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return {}
            licenses: dict[str, LicenseRecord] = {}
            for license_key, payload in raw.get("licenses", {}).items():
                record = LicenseRecord(
                    license_key=payload["license_key"],
                    customer_name=payload["customer_name"],
                    seat_limit=int(payload["seat_limit"]),
                    plan=payload.get("plan", "") or ("enterprise" if payload["license_key"].startswith("3TR-E-") else ("basic" if payload["license_key"].startswith("3TR-B-") else "personal")),
                    first_activated_at=payload.get("first_activated_at", "") or "",
                    customer_email=payload.get("customer_email", "") or "",
                )
                record.active_devices = dict(payload.get("active_devices", {}))
                record.revoked_devices = set(payload.get("revoked_devices", []))
                licenses[license_key] = record
            return licenses

    def save_licenses(self, licenses: dict[str, LicenseRecord]) -> None:
        with self._lock:
            payload = {
                "licenses": {
                    key: {
                        "license_key": record.license_key,
                        "customer_name": record.customer_name,
                        "seat_limit": record.seat_limit,
                        "plan": getattr(record, "plan", "personal"),
                        "first_activated_at": getattr(record, "first_activated_at", "") or "",
                        "customer_email": getattr(record, "customer_email", "") or "",
                        "active_devices": record.active_devices,
                        "revoked_devices": sorted(record.revoked_devices),
                    }
                    for key, record in licenses.items()
                }
            }
            self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
