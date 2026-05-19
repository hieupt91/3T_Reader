from __future__ import annotations

from typing import Protocol

from .models import ActivationResult, LicenseStatus


class LicenseClient(Protocol):
    def activate(self, license_key: str, email: str, device_fingerprint: str) -> ActivationResult:
        ...

    def validate_cached(self) -> LicenseStatus:
        ...

    def heartbeat(self) -> LicenseStatus:
        ...

    def deactivate(self) -> None:
        ...


class NotConfiguredLicenseClient:
    """Phase 0 placeholder until the Linux VPS license API exists."""

    def activate(self, license_key: str, email: str, device_fingerprint: str) -> ActivationResult:
        raise RuntimeError("License VPS is not configured yet.")

    def validate_cached(self) -> LicenseStatus:
        return LicenseStatus(active=True, message="Phase 0 local prototype mode")

    def heartbeat(self) -> LicenseStatus:
        return self.validate_cached()

    def deactivate(self) -> None:
        return None
