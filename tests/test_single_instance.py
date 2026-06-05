"""Unit tests for packages.platform.single_instance — mutex/lock behavior."""

from packages.platform.single_instance import acquire_single_instance


class TestAcquireSingleInstance:
    def test_returns_bool(self):
        """acquire_single_instance always returns a bool."""
        result = acquire_single_instance()
        assert isinstance(result, bool)
