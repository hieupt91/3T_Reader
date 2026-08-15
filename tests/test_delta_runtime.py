"""B53: apply/recovery behaviour for the Windows delta-update bootstrap."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from packages.updater import delta_runtime


def _make_extracted(root: Path, contents: bytes = b"new code") -> Path:
    extracted = root / "extracted"
    payload = extracted / "payload" / "app"
    payload.mkdir(parents=True)
    (payload / "module.pyc").write_bytes(contents)
    (extracted / "manifest.json").write_text(
        json.dumps({"files": [{"path": "app/module.pyc", "sha256": hashlib.sha256(contents).hexdigest()}]}),
        encoding="utf-8",
    )
    return extracted


def test_apply_replaces_file_and_records_base_version(monkeypatch, tmp_path):
    pending_root = tmp_path / "pending"
    target = tmp_path / "_internal"
    (target / "app").mkdir(parents=True)
    (target / "app" / "module.pyc").write_bytes(b"old code")
    monkeypatch.setattr(delta_runtime, "_update_root", lambda: pending_root)
    recorded = []
    monkeypatch.setattr("packages.updater.base_version.set_installed_base_version", recorded.append)

    state_dir = delta_runtime.prepare_pending_update(
        str(_make_extracted(tmp_path)), str(target), version="1.0.32", base_version="base-2"
    )

    assert delta_runtime.apply_pending_update(state_dir) is True
    assert (target / "app" / "module.pyc").read_bytes() == b"new code"
    assert recorded == ["base-2"]


def test_recovery_restores_old_file_after_interruption(monkeypatch, tmp_path):
    pending_root = tmp_path / "pending"
    target = tmp_path / "_internal"
    (target / "app").mkdir(parents=True)
    module = target / "app" / "module.pyc"
    module.write_bytes(b"old code")
    monkeypatch.setattr(delta_runtime, "_update_root", lambda: pending_root)
    state_dir = Path(delta_runtime.prepare_pending_update(
        str(_make_extracted(tmp_path)), str(target), version="1.0.32", base_version="base-2"
    ))
    state = delta_runtime._read_state(state_dir)
    backup = state_dir / "backup" / "app"
    backup.mkdir(parents=True)
    (backup / "module.pyc").write_bytes(b"old code")
    module.write_bytes(b"new code")
    state.update(status="applying", applied=["app/module.pyc"])
    delta_runtime._write_state(state_dir, state)

    delta_runtime.recover_incomplete_updates()

    assert module.read_bytes() == b"old code"
    assert delta_runtime._read_state(state_dir)["status"] == "rolled_back"


def test_prepare_rejects_tampered_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(delta_runtime, "_update_root", lambda: tmp_path / "pending")
    extracted = _make_extracted(tmp_path)
    manifest_path = extracted / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    target = tmp_path / "_internal"
    target.mkdir()

    try:
        delta_runtime.prepare_pending_update(str(extracted), str(target), version="1.0.32", base_version="base-2")
    except ValueError as exc:
        assert "khong khop" in str(exc).lower()
    else:
        raise AssertionError("tampered payload must be rejected")
