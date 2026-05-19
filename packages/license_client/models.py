from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LicenseStatus:
    active: bool
    plan_code: str = ""
    expires_at: datetime | None = None
    offline_grace_until: datetime | None = None
    message: str = ""


@dataclass(frozen=True)
class ActivationResult:
    activation_id: str
    signed_token: str
    status: LicenseStatus
