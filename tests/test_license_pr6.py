from __future__ import annotations

from datetime import datetime, timezone

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
