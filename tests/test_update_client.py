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
