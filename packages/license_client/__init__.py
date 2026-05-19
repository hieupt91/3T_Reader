from .client import LicenseClient, NotConfiguredLicenseClient
from .models import ActivationResult, LicenseStatus

_client = NotConfiguredLicenseClient()


def get_license_client() -> LicenseClient:
    return _client


__all__ = [
    "ActivationResult",
    "LicenseClient",
    "LicenseStatus",
    "NotConfiguredLicenseClient",
    "get_license_client",
]
