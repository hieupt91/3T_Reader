from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LicenseRecord:
    license_key: str
    customer_name: str
    seat_limit: int
    plan: str = ''
    first_activated_at: str = ''
    customer_email: str = ''
    active_devices: dict[str, dict] = field(default_factory=dict)
    revoked_devices: set[str] = field(default_factory=set)
