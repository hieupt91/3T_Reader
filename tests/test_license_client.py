"""Unit tests for packages.license_client — NotConfiguredLicenseClient."""

import pytest

from packages.license_client.client import NotConfiguredLicenseClient


class TestNotConfiguredLicenseClient:
    def test_validate_cached_returns_active(self):
        client = NotConfiguredLicenseClient()
        result = client.validate_cached()
        assert result.active is True

    def test_activate_raises_runtime_error(self):
        client = NotConfiguredLicenseClient()
        with pytest.raises(RuntimeError):
            client.activate("any-key", "test@example.com", "fp-123")

    def test_deactivate_returns_none(self):
        client = NotConfiguredLicenseClient()
        # deactivate() is a no-op, returns None without error
        assert client.deactivate() is None

    def test_heartbeat_returns_active(self):
        client = NotConfiguredLicenseClient()
        result = client.heartbeat()
        assert result.active is True
