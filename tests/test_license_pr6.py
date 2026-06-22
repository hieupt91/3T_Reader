from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from packages.license_client import fingerprint

from packages.license_client import trial, vps_client


def test_trial_uses_last_seen_to_block_clock_rollback(monkeypatch):
    monkeypatch.setattr(
        trial,
        "_storage_load",
        lambda: {
            "first_launch": "2026-05-10T00:00:00+00:00",
            "last_seen_at": "2026-05-20T00:00:00+00:00",
        },
    )
    saved = {}
    monkeypatch.setattr(trial, "_storage_save", lambda data: saved.update(data))
    monkeypatch.setattr(trial, "_utcnow", lambda: datetime(2026, 5, 15, tzinfo=timezone.utc))

    info = trial.get_or_init_trial()

    assert info["days_used"] == 10
    assert info["days_remaining"] == 20
    assert saved["last_seen_at"] == "2026-05-20T00:00:00+00:00"


def test_offline_validation_ignores_tampered_cache_grace_days(monkeypatch, tmp_path):
    client = vps_client.VpsLicenseClient("https://example.test", tmp_path / "license.json")

    monkeypatch.setattr(
        "packages.license_client.token_verifier.is_ed25519_token",
        lambda _token: True,
    )
    monkeypatch.setattr(
        "packages.license_client.token_verifier.verify_token_offline",
        lambda _token: {"expires_at": "2026-05-10T00:00:00+00:00"},
    )
    monkeypatch.setattr(vps_client, "_utcnow", lambda: datetime(2026, 5, 20, tzinfo=timezone.utc))

    status = client._verify_offline(
        {
            "token": "signed-token",
            "grace_days": 99999,
            "expires_at": "2026-05-10T00:00:00+00:00",
        }
    )

    assert status is not None
    assert status.active is False


def test_windows_fingerprint_ignores_hostname_when_machine_guid_exists(monkeypatch):
    monkeypatch.setattr(fingerprint.platform, "system", lambda: "Windows")
    monkeypatch.setattr(fingerprint.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(fingerprint, "_windows_machine_guid", lambda: "machine-guid-1")
    monkeypatch.setattr(fingerprint.socket, "gethostname", lambda: "HOST-A")
    monkeypatch.setenv("COMPUTERNAME", "HOST-A")

    first = fingerprint.get_device_fingerprint()

    monkeypatch.setattr(fingerprint.socket, "gethostname", lambda: "HOST-B")
    monkeypatch.setenv("COMPUTERNAME", "HOST-B")

    second = fingerprint.get_device_fingerprint()

    assert first == second


def test_vps_license_service_reuses_same_machine_seat_and_user_deactivate_does_not_revoke():
    src = Path("vps_license_service.py").read_text(encoding="utf-8")

    assert "def _find_reusable_device_id(" in src
    assert "record.active_devices.pop(reusable_device_id)" in src
    assert 'not in {"user_requested", "app_reinstall", "app_uninstall"}' in src
    assert 'record.revoked_devices.discard(device_id)' in src


def test_main_api_passes_deactivate_reason_to_license_service():
    src = Path("main_api.py").read_text(encoding="utf-8")

    assert "license_service.deactivate(req.token, req.device_id, req.reason)" in src
