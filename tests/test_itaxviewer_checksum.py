import inspect
import urllib.error

from app.actions import document_converter as dc


def test_sha256_file_computes_correct_digest(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"hello world")
    import hashlib

    assert dc._sha256_file(path) == hashlib.sha256(b"hello world").hexdigest()


def test_fetch_sha256_sidecar_returns_empty_when_server_has_no_sidecar_yet(monkeypatch):
    """iTaxViewer la phan mem ben thu 3 - 3T Company chi co the publish 1 file
    .sha256 ben canh installer tren CDN cua ho, khong ky Ed25519 duoc nhu ban
    update chinh cua app. Server chua co sidecar (404) khong duoc chan tai
    ve/cai dat hop le - phai fallback ve hanh vi cu (khong kiem tra)."""

    def fake_open(*a, **kw):
        raise urllib.error.HTTPError(url="x", code=404, msg="not found", hdrs=None, fp=None)

    monkeypatch.setattr(dc.urllib.request, "build_opener", lambda *a, **kw: type(
        "O", (), {"open": staticmethod(fake_open)}
    )())
    assert dc._fetch_sha256_sidecar("https://example.com/itaxviewer_installer.exe") == ""


def test_fetch_sha256_sidecar_parses_valid_hex_digest(monkeypatch):
    digest = "a" * 64

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return (digest + "\n").encode("utf-8")

    monkeypatch.setattr(dc.urllib.request, "build_opener", lambda *a, **kw: type(
        "O", (), {"open": staticmethod(lambda *a, **kw: FakeResp())}
    )())
    assert dc._fetch_sha256_sidecar("https://example.com/itaxviewer_installer.exe") == digest


def test_fetch_sha256_sidecar_rejects_malformed_response(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b"<html>not a hash</html>"

    monkeypatch.setattr(dc.urllib.request, "build_opener", lambda *a, **kw: type(
        "O", (), {"open": staticmethod(lambda *a, **kw: FakeResp())}
    )())
    assert dc._fetch_sha256_sidecar("https://example.com/itaxviewer_installer.exe") == ""


def test_handle_xml_itax_verifies_checksum_before_running_installer_when_available():
    src = inspect.getsource(dc.handle_xml_itax)
    assert "expected_sha256 = _fetch_sha256_sidecar(url.split(\"?\")[0])" in src
    verify_idx = src.index("expected_sha256 = _fetch_sha256_sidecar")
    install_idx = src.index("_run_itax_installer_silent(window, temp_exe)")
    assert verify_idx < install_idx
    assert "temp_exe.unlink(missing_ok=True)" in src[verify_idx:install_idx]
