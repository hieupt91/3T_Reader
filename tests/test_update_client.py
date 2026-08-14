from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import app.updater as legacy_updater
from packages.updater import update_client


def test_check_for_update_uses_live_update_check_endpoint(monkeypatch):
    calls = []

    def fake_get(url, params=None):
        calls.append((url, params))
        return {
            "platform": "win",
            "current_version": "1.0.2",
            "version": "1.0.7",
            "latest_version": "1.0.7",
            "download_url": "https://reader.3tcomputer.com/downloads/3TReader-1.0.7-win.exe",
            "sha256": "ABC123",
            "release_notes": "Release notes",
        }

    monkeypatch.setattr(update_client, "_get", fake_get)

    info = update_client.check_for_update(
        "https://reader.3tcomputer.com",
        "1.0.2",
        platform="win",
    )

    assert calls == [
        (
            "https://reader.3tcomputer.com/api/v1/update/check",
            {"platform": "win", "current_version": "1.0.2"},
        )
    ]
    assert info.available is True
    assert info.latest_version == "1.0.7"
    assert info.download_url.endswith("3TReader-1.0.7-win.exe")
    assert info.sha256 == "ABC123"
    assert info.release_notes == "Release notes"


def test_check_for_update_accepts_latest_version_field(monkeypatch):
    monkeypatch.setattr(
        update_client,
        "_get",
        lambda _url, params=None: {
            "latest_version": "1.0.7",
            "url": "https://example.test/update.exe",
        },
    )

    info = update_client.check_for_update("https://example.test", "1.0.7", platform="win")

    assert info.available is False
    assert info.latest_version == "1.0.7"
    assert info.download_url == "https://example.test/update.exe"


def test_legacy_updater_uses_live_query_contract(monkeypatch):
    opened_urls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"version": "1.0.7"}).encode("utf-8")

    def fake_urlopen(req, timeout=0):
        opened_urls.append(req.full_url)
        return FakeResponse()

    monkeypatch.setattr(legacy_updater, "UPDATE_MANIFEST_URL", "https://reader.3tcomputer.com/api/v1/update/check")
    monkeypatch.setattr(legacy_updater.urllib.request, "urlopen", fake_urlopen)

    assert legacy_updater._get_latest_release() == {"version": "1.0.7"}

    parsed = urlparse(opened_urls[0])
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://reader.3tcomputer.com/api/v1/update/check"
    query = parse_qs(parsed.query)
    assert query["current_version"] == [legacy_updater.APP_VERSION]
    assert query["platform"][0] in {"win", "mac"}
    assert "product" not in query
    assert "channel" not in query
    assert "version" not in query


def test_embedded_public_keys_are_not_empty():
    """Regression: khi list này từng rỗng (import xuyên package âm thầm vỡ
    trên bản build đóng gói, xem comment đầu update_client.py), MỌI bản cập
    nhật hợp lệ đều bị từ chối cho MỌI user - xác nhận thật 14/08/2026 (lỗi
    "Chữ ký manifest không hợp lệ"). Test này 1 mình đủ để bắt regression đó
    ngay ở CI thay vì chờ user thật báo lỗi."""
    assert update_client._EMBEDDED_PUBLIC_KEYS_B64


def test_embedded_public_keys_match_token_verifier_source_of_truth():
    """update_client.py nhúng thẳng (không import) danh sách key để tránh vỡ
    âm thầm ở bản build đóng gói - nhưng vẫn phải khớp CHÍNH XÁC với
    packages/license_client/token_verifier.py (nguồn key gốc dùng cho license
    token). Lệch nhau ở đây nghĩa là ai đó xoay key 1 chỗ mà quên chỗ kia."""
    from packages.license_client.token_verifier import _TRUSTED_ED25519_PUBLIC_KEYS_B64

    assert update_client._EMBEDDED_PUBLIC_KEYS_B64 == _TRUSTED_ED25519_PUBLIC_KEYS_B64


def test_download_update_accepts_manifest_signed_by_trusted_key(monkeypatch):
    """Test hành vi thật đầu-cuối: ký đúng format manifest bằng 1 keypair
    Ed25519 test, đưa public key vào danh sách tin cậy, xác nhận
    download_update() CHẤP NHẬN - chứng minh _verify_signature() hoạt động
    đúng với dữ liệu thật, không chỉ kiểm tra list không rỗng."""
    import base64
    import hashlib
    import json

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_b64 = base64.b64encode(public_bytes).decode("ascii").rstrip("=")

    monkeypatch.setattr(update_client, "_EMBEDDED_PUBLIC_KEYS_B64", [public_b64])

    payload_bytes = b"fake installer bytes"
    sha256 = hashlib.sha256(payload_bytes).hexdigest()

    manifest_bytes = json.dumps(
        {
            "version": "1.0.99",
            "download_url": "https://example.test/update.bin",
            "sha256": sha256,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature_b64 = base64.b64encode(private_key.sign(manifest_bytes)).decode("ascii").rstrip("=")

    class _FakeResp:
        headers = {"content-length": str(len(payload_bytes))}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield payload_bytes

    monkeypatch.setattr("requests.get", lambda *a, **kw: _FakeResp())

    info = update_client.UpdateInfo(
        available=True,
        current_version="1.0.98",
        latest_version="1.0.99",
        download_url="https://example.test/update.bin",
        sha256=sha256,
        signature=signature_b64,
    )

    result = update_client.download_update(info)

    assert result.success is True, result.error
    assert result.path


def test_download_update_rejects_unsigned_manifest():
    info = update_client.UpdateInfo(
        available=True,
        current_version="1.0.7",
        latest_version="1.0.8",
        download_url="https://example.test/3TReader.exe",
        sha256="abc123",
        signature="",
    )

    result = update_client.download_update(info)

    assert result.success is False
    assert "thieu chu ky" in result.error.lower()


def test_legacy_update_client_checker_delegates_to_signed_updater(monkeypatch):
    from packages.update_client import checker as legacy_checker

    calls = []

    def fake_check(base_url, current_version, *, platform):
        calls.append((base_url, current_version, platform))
        return update_client.UpdateInfo(
            available=True,
            current_version=current_version,
            latest_version="1.0.8",
            download_url="https://example.test/update.exe",
            sha256="abc",
            signature="sig",
        )

    monkeypatch.setattr(legacy_checker, "_check_for_update", fake_check)

    info = legacy_checker.check_for_update("https://example.test", "1.0.7")

    assert info.latest_version == "1.0.8"
    assert calls[0][0] == "https://example.test"
    assert calls[0][1] == "1.0.7"
    assert calls[0][2] in {"win", "mac", "linux"}
    assert legacy_checker.download_update is update_client.download_update
    assert legacy_checker.UpdateInfo is update_client.UpdateInfo
