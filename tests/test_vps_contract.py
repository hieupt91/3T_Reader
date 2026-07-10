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


# ── Bảo mật B1: chặn bypass license offline ──────────────────────────────
# Lỗ hổng cũ: sửa tay file cache JSON (token không-Ed25519) + để offline =>
# app vẫn coi là active vĩnh viễn. Fix: _offline_status không được cấp active
# từ cache; nhánh non-Ed25519 phải xác thực server, offline thì báo inactive.

def _make_client(tmp_path):
    from packages.license_client.vps_client import VpsLicenseClient

    return VpsLicenseClient("https://example.invalid", tmp_path / "license_cache.json")


def test_offline_status_never_grants_active_from_cache(tmp_path):
    client = _make_client(tmp_path)
    # Cache "sửa tay" trông rất hợp lệ, hạn xa tít
    forged = {
        "plan_code": "PRO",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "grace_days": 3650,
    }
    status = client._offline_status(forged)
    assert status.active is False


def test_validate_cached_non_ed25519_offline_is_inactive(tmp_path, monkeypatch):
    import packages.license_client.vps_client as vc

    client = _make_client(tmp_path)
    # Token HMAC cũ (2 phần) => không phải Ed25519 (Ed25519 phải 4 phần, phần[2]=="ed")
    forged_cache = {
        "token": "forgedbody.forgedsig",
        "device_id": "dev-1",
        "plan_code": "PRO",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "grace_days": 3650,
    }
    monkeypatch.setattr(client, "_load_cache", lambda: forged_cache)

    # Giả lập offline: mọi request tới server đều ném lỗi
    def _offline_post(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr(vc, "_post", _offline_post)

    status = client.validate_cached()
    assert status.active is False
