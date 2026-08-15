"""Vá lỗ hổng bảo mật thật (15/08/2026): updater Mac trước đây hoàn toàn
không verify SHA-256/chữ ký khi tải bản cập nhật - tải thẳng và chạy. Test
này xác nhận download_update() giờ từ chối mọi bản cập nhật thiếu/lỗi
SHA-256 hoặc chữ ký, và CHẤP NHẬN đúng khi được ký hợp lệ bằng key tin
cậy - cùng logic đã verify trên Windows
(packages/updater/update_client.py, nhánh piper-vps-sync)."""
from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from packages.update_client import checker


def test_embedded_public_keys_are_not_empty():
    assert checker._EMBEDDED_PUBLIC_KEYS_B64


def test_embedded_public_keys_match_token_verifier_source_of_truth():
    from packages.license_client.token_verifier import _TRUSTED_ED25519_PUBLIC_KEYS_B64

    assert checker._EMBEDDED_PUBLIC_KEYS_B64 == _TRUSTED_ED25519_PUBLIC_KEYS_B64


def test_check_for_update_captures_sha256_and_signature(monkeypatch):
    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "version": "1.0.22",
                "download_url": "https://example.test/3TReader-1.0.22-mac.dmg",
                "sha256": "abc123",
                "signature": "sig123",
                "release_notes": "notes",
            }

    monkeypatch.setattr("requests.get", lambda *a, **kw: _FakeResp())

    info = checker.check_for_update("https://example.test", "1.0.21")

    assert info.available is True
    assert info.sha256 == "abc123"
    assert info.signature == "sig123"


def test_download_update_rejects_missing_sha256():
    info = checker.UpdateInfo(
        available=True, current_version="1.0.21", latest_version="1.0.22",
        download_url="https://example.test/update.dmg", sha256="", signature="sig",
    )

    result = checker.download_update(info)

    assert result.success is False
    assert "sha-256" in result.error.lower()


def test_download_update_rejects_missing_signature():
    info = checker.UpdateInfo(
        available=True, current_version="1.0.21", latest_version="1.0.22",
        download_url="https://example.test/update.dmg", sha256="abc", signature="",
    )

    result = checker.download_update(info)

    assert result.success is False
    assert "chữ ký" in result.error.lower()


def test_download_update_accepts_manifest_signed_by_trusted_key(monkeypatch):
    """Test hành vi thật đầu-cuối: ký đúng format bằng keypair Ed25519 test,
    xác nhận download_update() CHẤP NHẬN - không chỉ kiểm tra list không rỗng."""
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_b64 = base64.b64encode(public_bytes).decode("ascii").rstrip("=")
    monkeypatch.setattr(checker, "_EMBEDDED_PUBLIC_KEYS_B64", [public_b64])

    payload_bytes = b"fake dmg bytes"
    sha256 = hashlib.sha256(payload_bytes).hexdigest()

    manifest_bytes = json.dumps(
        {"version": "1.0.22", "download_url": "https://example.test/update.dmg", "sha256": sha256},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    signature_b64 = base64.b64encode(private_key.sign(manifest_bytes)).decode("ascii").rstrip("=")

    class _FakeResp:
        headers = {"content-length": str(len(payload_bytes))}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield payload_bytes

    monkeypatch.setattr("requests.get", lambda *a, **kw: _FakeResp())

    info = checker.UpdateInfo(
        available=True, current_version="1.0.21", latest_version="1.0.22",
        download_url="https://example.test/update.dmg", sha256=sha256, signature=signature_b64,
    )

    result = checker.download_update(info)

    assert result.success is True, result.error
    assert result.path


def test_download_update_rejects_sha256_mismatch(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_b64 = base64.b64encode(public_bytes).decode("ascii").rstrip("=")
    monkeypatch.setattr(checker, "_EMBEDDED_PUBLIC_KEYS_B64", [public_b64])

    class _FakeResp:
        headers = {"content-length": "8"}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"realbyte"

    monkeypatch.setattr("requests.get", lambda *a, **kw: _FakeResp())

    info = checker.UpdateInfo(
        available=True, current_version="1.0.21", latest_version="1.0.22",
        download_url="https://example.test/update.dmg", sha256="0" * 64, signature="anything",
    )

    result = checker.download_update(info)

    assert result.success is False
    assert "sha-256" in result.error.lower()


def test_download_update_rejects_untrusted_signature(monkeypatch):
    """Chữ ký hợp lệ về MẶT TOÁN HỌC nhưng ký bằng key KHÔNG nằm trong danh
    sách tin cậy - mô phỏng kẻ tấn công tự ký giả mạo."""
    attacker_key = Ed25519PrivateKey.generate()
    payload_bytes = b"malicious dmg bytes"
    sha256 = hashlib.sha256(payload_bytes).hexdigest()
    manifest_bytes = json.dumps(
        {"version": "1.0.22", "download_url": "https://example.test/update.dmg", "sha256": sha256},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    forged_signature = base64.b64encode(attacker_key.sign(manifest_bytes)).decode("ascii").rstrip("=")

    class _FakeResp:
        headers = {"content-length": str(len(payload_bytes))}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield payload_bytes

    monkeypatch.setattr("requests.get", lambda *a, **kw: _FakeResp())

    info = checker.UpdateInfo(
        available=True, current_version="1.0.21", latest_version="1.0.22",
        download_url="https://example.test/update.dmg", sha256=sha256, signature=forged_signature,
    )

    result = checker.download_update(info)

    assert result.success is False
    assert "chữ ký" in result.error.lower()
