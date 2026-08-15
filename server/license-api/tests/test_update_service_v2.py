"""B53: test build_manifest_v2() (route /api/v2/update/check) không đụng gì
tới build_manifest() (v1) hiện có, mặc định delta_enabled=False phải cho
hành vi giống hệt full-install cũ. Xem docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md."""
from __future__ import annotations

import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.admin_config import AdminConfig
from app.services.token_service import TokenService
from app.services.update_service import UpdateService


@pytest.fixture()
def signed_env(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    raw = private_key.private_bytes_raw()
    monkeypatch.setenv("THREET_LICENSE_ED25519_PRIVATE", base64.b64encode(raw).decode("ascii"))
    return private_key


def _verify(private_key: Ed25519PrivateKey, signature_b64: str, payload: dict) -> bool:
    from cryptography.exceptions import InvalidSignature

    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig_bytes = base64.b64decode(signature_b64 + "==")
    try:
        private_key.public_key().verify(sig_bytes, body)
        return True
    except InvalidSignature:
        return False


def test_delta_disabled_by_default_gives_full_update_type(tmp_path, signed_env):
    cfg_path = tmp_path / "admin-config.json"
    admin_config = AdminConfig(str(cfg_path))
    admin_config.set_update_config({
        "win_version": "1.0.32", "win_url": "https://x/y.exe", "win_sha256": "abc",
        "win_code_url": "https://x/patch.zip", "win_code_sha256": "def",
    })
    service = UpdateService(TokenService("dev-secret"), admin_config=admin_config)

    manifest = service.build_manifest_v2("win", "1.0.31", "base-1.0")

    assert manifest["update_type"] == "full"
    assert manifest["code_package_url"] == ""
    assert manifest["code_package_sha256"] == ""
    assert manifest["code_signature"] == ""


def test_delta_enabled_with_matching_base_version_gives_delta(tmp_path, signed_env):
    cfg_path = tmp_path / "admin-config.json"
    admin_config = AdminConfig(str(cfg_path))
    admin_config.set_update_config({
        "win_version": "1.0.32", "win_url": "https://x/y.exe", "win_sha256": "abc",
        "win_base_version": "base-1.0",
        "win_code_url": "https://x/patch.zip", "win_code_sha256": "def456",
        "delta_enabled": True,
    })
    service = UpdateService(TokenService("dev-secret"), admin_config=admin_config)

    manifest = service.build_manifest_v2("win", "1.0.31", "base-1.0")

    assert manifest["update_type"] == "delta"
    assert manifest["code_package_url"] == "https://x/patch.zip"
    assert manifest["code_package_sha256"] == "def456"
    assert manifest["code_signature"] != ""
    assert _verify(signed_env, manifest["code_signature"], {
        "base_version": "base-1.0",
        "code_package_sha256": "def456",
        "code_package_url": "https://x/patch.zip",
    })
    # full-install signature vẫn phải verify được y hệt v1 (fallback path)
    assert _verify(signed_env, manifest["signature"], {
        "download_url": "https://x/y.exe", "sha256": "abc", "version": "1.0.32",
    })


def test_delta_enabled_but_base_version_mismatch_falls_back_to_full(tmp_path, signed_env):
    cfg_path = tmp_path / "admin-config.json"
    admin_config = AdminConfig(str(cfg_path))
    admin_config.set_update_config({
        "win_version": "1.0.32", "win_url": "https://x/y.exe", "win_sha256": "abc",
        "win_base_version": "base-2.0",  # server đổi base, client vẫn base-1.0
        "win_code_url": "https://x/patch.zip", "win_code_sha256": "def456",
        "delta_enabled": True,
    })
    service = UpdateService(TokenService("dev-secret"), admin_config=admin_config)

    manifest = service.build_manifest_v2("win", "1.0.31", "base-1.0")

    assert manifest["update_type"] == "full"
    assert manifest["code_package_url"] == ""
    assert manifest["code_signature"] == ""


def test_already_up_to_date_gives_none(tmp_path, signed_env):
    cfg_path = tmp_path / "admin-config.json"
    admin_config = AdminConfig(str(cfg_path))
    admin_config.set_update_config({"win_version": "1.0.31", "win_url": "https://x/y.exe", "win_sha256": "abc"})
    service = UpdateService(TokenService("dev-secret"), admin_config=admin_config)

    manifest = service.build_manifest_v2("win", "1.0.31", "base-1.0")

    assert manifest["update_type"] == "none"


def test_v1_build_manifest_unaffected_by_v2_fields(tmp_path, signed_env):
    """Regression guard: field B53 mới trong admin_config không được rò rỉ
    vào response v1 hay đổi hành vi build_manifest() cũ."""
    cfg_path = tmp_path / "admin-config.json"
    admin_config = AdminConfig(str(cfg_path))
    admin_config.set_update_config({
        "win_version": "1.0.32", "win_url": "https://x/y.exe", "win_sha256": "abc",
        "win_code_url": "https://x/patch.zip", "win_code_sha256": "def456",
        "delta_enabled": True,
    })
    service = UpdateService(TokenService("dev-secret"), admin_config=admin_config)

    manifest = service.build_manifest("win", "1.0.31")

    assert set(manifest.keys()) == {
        "platform", "current_version", "latest_version", "download_url",
        "sha256", "portable_url", "portable_sha256", "mandatory",
        "release_notes", "signature",
    }
    assert manifest["download_url"] == "https://x/y.exe"


def test_admin_config_persists_and_returns_new_fields(tmp_path):
    cfg_path = tmp_path / "admin-config.json"
    admin_config = AdminConfig(str(cfg_path))
    admin_config.set_update_config({
        "win_base_version": "base-2.0",
        "win_code_url": "https://x/patch.zip",
        "win_code_sha256": "abc123",
        "delta_enabled": True,
    })

    cfg = admin_config.get_update_config()

    assert cfg["win_base_version"] == "base-2.0"
    assert cfg["win_code_url"] == "https://x/patch.zip"
    assert cfg["delta_enabled"] is True


def test_admin_config_ignores_unknown_fields(tmp_path):
    """allowed whitelist trong set_update_config() phải chặn field lạ -
    không tự dưng ghi field không định nghĩa vào config thật."""
    cfg_path = tmp_path / "admin-config.json"
    admin_config = AdminConfig(str(cfg_path))
    admin_config.set_update_config({"totally_unknown_field": "x"})

    cfg = admin_config.get_update_config()

    assert "totally_unknown_field" not in cfg
