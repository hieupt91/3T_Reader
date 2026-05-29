from __future__ import annotations

import sys
from types import SimpleNamespace


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_update_client_parses_vps_update_check_contract(monkeypatch):
    from packages.update_client import checker

    calls = []

    def fake_get(url, timeout=None, headers=None):
        calls.append((url, timeout, headers))
        return _FakeResponse(
            {
                "platform": "mac",
                "current_version": "0.0.0",
                "latest_version": "1.0.0",
                "download_url": "https://reader.3tcomputer.com/downloads/3TReader-1.0.0-mac.dmg",
                "sha256": "abc123",
                "mandatory": True,
                "release_notes": "Ready",
            }
        )

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(get=fake_get))

    info = checker.check_for_update("https://reader.3tcomputer.com", "0.0.0")

    assert info.available is True
    assert info.latest_version == "1.0.0"
    assert info.download_url.endswith(".dmg")
    assert info.sha256 == "abc123"
    assert info.mandatory is True
    assert "/api/v1/update/check" in calls[0][0]
    assert "platform=mac" in calls[0][0]


def test_license_token_public_key_accepts_vps_urlsafe_format():
    from packages.license_client.token_verifier import _ED25519_PUBLIC_B64, _public_key_decode

    standard = _public_key_decode(_ED25519_PUBLIC_B64)
    urlsafe = _public_key_decode("y0jZ_wQHoQ-VvAQjYuhlmf0R63cMLgkTHp1wzXrcM08")

    assert len(standard) == 32
    assert standard == urlsafe
