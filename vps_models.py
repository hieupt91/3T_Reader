from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LicenseRecord:
    license_key: str
    customer_name: str
    seat_limit: int
    plan: str = 'personal'
    active_devices: dict[str, dict] = field(default_factory=dict)
    revoked_devices: set[str] = field(default_factory=set)
    # ISO timestamp of the very first activation. License expiry is anchored
    # here so uninstall + re-activate does not restart the license period.
    first_activated_at: str | None = None
