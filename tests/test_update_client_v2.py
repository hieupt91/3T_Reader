"""B53: test check_for_update_v2()/stage_code_package() (packages/updater/
update_client.py) - route delta-update riêng, KHÔNG động tới
check_for_update()/download_update() (v1) hiện có. Xem
docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md."""
from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from io import BytesIO

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from packages.updater import update_client


def test_check_for_update_v2_uses_v2_endpoint_and_passes_base_version(monkeypatch):
    calls = []

    def fake_get(url, params=None):
        calls.append((url, params))
        return {
            "latest_version": "1.0.32", "update_type": "delta",
            "base_version": "base-1.0", "download_url": "https://x/full.exe",
            "sha256": "abc", "signature": "sig1",
            "code_package_url": "https://x/patch.zip", "code_package_sha256": "def",
            "code_signature": "sig2",
        }

    monkeypatch.setattr(update_client, "_get", fake_get)

    info = update_client.check_for_update_v2("https://x", "1.0.31", "base-1.0", platform="windows")

    assert calls == [
        ("https://x/api/v2/update/check", {"platform": "windows", "current_version": "1.0.31", "current_base_version": "base-1.0"})
    ]
    assert info.available is True
    assert info.update_type == "delta"
    assert info.code_package_url == "https://x/patch.zip"


def test_check_for_update_v2_none_when_server_says_none(monkeypatch):
    monkeypatch.setattr(
        update_client, "_get",
        lambda url, params=None: {"latest_version": "1.0.31", "update_type": "none"},
    )

    info = update_client.check_for_update_v2("https://x", "1.0.31", "base-1.0")

    assert info.available is False
    assert info.update_type == "none"


def test_check_for_update_v2_network_error_falls_back_to_none(monkeypatch):
    def fake_get(url, params=None):
        raise ConnectionError("network down")

    monkeypatch.setattr(update_client, "_get", fake_get)

    info = update_client.check_for_update_v2("https://x", "1.0.31", "base-1.0")

    assert info.available is False
    assert info.update_type == "none"


def _make_signed_code_package(monkeypatch, *, contents: bytes = b"fake code package"):
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_b64 = base64.b64encode(public_bytes).decode("ascii").rstrip("=")
    monkeypatch.setattr(update_client, "_EMBEDDED_PUBLIC_KEYS_B64", [public_b64])

    sha256 = hashlib.sha256(contents).hexdigest()
    payload_bytes = json.dumps(
        {"base_version": "base-1.0", "code_package_sha256": sha256, "code_package_url": "https://x/patch.zip"},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    code_signature = base64.b64encode(private_key.sign(payload_bytes)).decode("ascii").rstrip("=")
    return sha256, code_signature


def test_stage_code_package_downloads_verifies_and_extracts(monkeypatch, tmp_path):
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("app/window.py", "# fake patched file")
    contents = zip_buf.getvalue()
    sha256, code_signature = _make_signed_code_package(monkeypatch, contents=contents)

    class _FakeResp:
        headers = {"content-length": str(len(contents))}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield contents

    monkeypatch.setattr("requests.get", lambda *a, **kw: _FakeResp())

    info = update_client.UpdateInfoV2(
        available=True, update_type="delta", base_version="base-1.0",
        code_package_url="https://x/patch.zip", code_package_sha256=sha256,
        code_signature=code_signature,
    )

    result = update_client.stage_code_package(info)

    assert result.success is True, result.error
    import os
    assert os.path.exists(os.path.join(result.path, "app", "window.py"))


def test_stage_code_package_rejects_sha256_mismatch(monkeypatch):
    contents = b"real content"
    _, code_signature = _make_signed_code_package(monkeypatch, contents=b"different content")

    class _FakeResp:
        headers = {"content-length": str(len(contents))}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield contents

    monkeypatch.setattr("requests.get", lambda *a, **kw: _FakeResp())

    info = update_client.UpdateInfoV2(
        available=True, update_type="delta", base_version="base-1.0",
        code_package_url="https://x/patch.zip", code_package_sha256="0" * 64,
        code_signature=code_signature,
    )

    result = update_client.stage_code_package(info)

    assert result.success is False
    assert "khong khop" in result.error.lower() or "sha-256" in result.error.lower()


def test_stage_code_package_rejects_bad_signature(monkeypatch):
    contents = b"real content"
    sha256 = hashlib.sha256(contents).hexdigest()

    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_b64 = base64.b64encode(public_bytes).decode("ascii").rstrip("=")
    monkeypatch.setattr(update_client, "_EMBEDDED_PUBLIC_KEYS_B64", [public_b64])

    # Ký payload SAI (khác code_package_url thật) - mô phỏng chữ ký giả/bị thay đổi.
    wrong_payload = json.dumps(
        {"base_version": "base-1.0", "code_package_sha256": sha256, "code_package_url": "https://evil.test/patch.zip"},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    bad_signature = base64.b64encode(private_key.sign(wrong_payload)).decode("ascii").rstrip("=")

    class _FakeResp:
        headers = {"content-length": str(len(contents))}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield contents

    monkeypatch.setattr("requests.get", lambda *a, **kw: _FakeResp())

    info = update_client.UpdateInfoV2(
        available=True, update_type="delta", base_version="base-1.0",
        code_package_url="https://x/patch.zip", code_package_sha256=sha256,
        code_signature=bad_signature,
    )

    result = update_client.stage_code_package(info)

    assert result.success is False
    assert "chu ky" in result.error.lower()


def test_stage_code_package_rejects_missing_fields():
    info = update_client.UpdateInfoV2(available=True, update_type="full")

    result = update_client.stage_code_package(info)

    assert result.success is False
