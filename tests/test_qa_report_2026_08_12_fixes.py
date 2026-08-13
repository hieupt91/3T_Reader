from __future__ import annotations

import json
from pathlib import Path

from packages.license_client import vps_client


def test_license_save_writes_json_fallback_even_when_secure_store_succeeds(monkeypatch, tmp_path):
    client = vps_client.VpsLicenseClient("https://example.test", tmp_path / "license_cache.json")
    saved_secure = {}

    monkeypatch.setattr(vps_client, "_USE_KEYCHAIN", False)
    monkeypatch.setattr(vps_client, "_USE_CREDENTIAL_MANAGER", True)
    monkeypatch.setattr(vps_client, "credential_manager_save", lambda data, **_kwargs: saved_secure.update(data) or True)

    payload = {"token": "signed-token", "device_id": "device-1", "plan_code": "personal"}
    client._save_cache(payload)

    assert saved_secure["token"] == "signed-token"
    assert json.loads((tmp_path / "license_cache.json").read_text(encoding="utf-8"))["token"] == "signed-token"


def test_license_load_ignores_empty_secure_store_and_migrates_file_fallback(monkeypatch, tmp_path):
    cache_path = tmp_path / "license_cache.json"
    cache_path.write_text(
        json.dumps({"token": "signed-token", "device_id": "device-1", "plan_code": "enterprise"}),
        encoding="utf-8",
    )
    client = vps_client.VpsLicenseClient("https://example.test", cache_path)
    migrated = {}

    monkeypatch.setattr(vps_client, "_USE_KEYCHAIN", False)
    monkeypatch.setattr(vps_client, "_USE_CREDENTIAL_MANAGER", True)
    monkeypatch.setattr(vps_client, "credential_manager_load", lambda **_kwargs: {})
    monkeypatch.setattr(vps_client, "credential_manager_save", lambda data, **_kwargs: migrated.update(data) or True)

    loaded = client._load_cache()

    assert loaded["token"] == "signed-token"
    assert migrated["token"] == "signed-token"


def test_export_subprocess_does_not_report_cancel_when_stderr_exists():
    source = Path("app/actions/export.py").read_text(encoding="utf-8")

    assert 'state = {"stdout": [], "stderr": [], "reported": False, "cancelled": False, "closing": False}' in source
    assert 'state.get("cancelled") and not (stderr_text or stdout_text)' in source
    assert "progress.canceled.disconnect(_cancel_proc)" in source


def test_open_document_checks_duplicate_paths_before_creating_viewer():
    source = Path("app/window.py").read_text(encoding="utf-8")
    open_doc_body = source.split("def open_document(", 1)[1].split("tab    = QWidget()", 1)[0]

    assert "_find_open_document_tab" in open_doc_body
    assert "os.path.normcase(os.path.abspath" in source
    assert "self.tab_widget.setCurrentIndex(existing_index)" in open_doc_body


def test_large_pdf_compress_is_guarded_before_pikepdf_save():
    source = Path("app/actions/document_ops.py").read_text(encoding="utf-8")
    body = source.split("def compress_pdf(window):", 1)[1].split("try:\n        import pikepdf", 1)[0]

    assert "512 * 1024 * 1024" in body
    assert "PDF quá lớn để nén trực tiếp" in body
