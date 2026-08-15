"""B53: crash-safe application of a verified Windows code-package update.

This module deliberately uses only the standard library.  It is loaded before
``app.window`` from :mod:`main`, and it is an immutable part of the base
runtime: a delta package is forbidden from replacing this file or ``main``.
That lets a fresh 3T Reader process recover a half-applied update before any
patched native module (.pyd) is loaded.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

_STATE_FILE = "state.json"
_PAYLOAD_DIR = "payload"
_BACKUP_DIR = "backup"
_IMMUTABLE_PATHS = {
    "main.pyc",
    "packages/updater/delta_runtime.pyc",
    "packages/updater/delta_runtime.py",
}


def _update_root() -> Path:
    from packages.platform import get_app_data_dir

    return Path(get_app_data_dir()) / "pending_delta_updates"


def _normal_relpath(value: str) -> str:
    candidate = Path(value.replace("\\", "/"))
    if not value or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Duong dan goi cap nhat khong an toan.")
    normalized = candidate.as_posix()
    if normalized in _IMMUTABLE_PATHS:
        raise ValueError("Goi cap nhat co chua file bootstrap bat bien.")
    return normalized


def _read_state(state_dir: Path) -> dict:
    with (state_dir / _STATE_FILE).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_state(state_dir: Path, state: dict) -> None:
    temp = state_dir / f"{_STATE_FILE}.tmp"
    with temp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temp, state_dir / _STATE_FILE)


def prepare_pending_update(extracted_dir: str, target_internal_dir: str, *, version: str, base_version: str) -> str:
    """Persist a staged, verified payload and return its state directory.

    ``stage_code_package`` has already verified the archive signature and
    SHA-256.  This function still validates every relative path before any
    subsequent process is allowed to write it into the installation.
    """
    extracted = Path(extracted_dir)
    manifest_path = extracted / "manifest.json"
    payload = extracted / _PAYLOAD_DIR
    if not manifest_path.is_file() or not payload.is_dir():
        raise ValueError("Code package thieu manifest.json hoac thu muc payload.")
    with manifest_path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("Manifest code package khong co danh sach file.")

    files: list[dict[str, str]] = []
    for item in raw_files:
        if not isinstance(item, dict):
            raise ValueError("Manifest code package khong hop le.")
        rel = _normal_relpath(str(item.get("path", "")))
        sha256 = str(item.get("sha256", "")).lower()
        source = payload / rel
        if not source.is_file() or len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError("Manifest code package khong khop payload.")
        if _sha256(source) != sha256:
            raise ValueError("Payload code package khong khop manifest.")
        files.append({"path": rel, "sha256": sha256})

    root = _update_root()
    root.mkdir(parents=True, exist_ok=True)
    state_dir = root / uuid.uuid4().hex
    shutil.copytree(extracted, state_dir)
    state = {
        "status": "pending",
        "version": version,
        "base_version": base_version,
        "target_internal_dir": str(Path(target_internal_dir).resolve()),
        "files": files,
        "applied": [],
    }
    _write_state(state_dir, state)
    return str(state_dir)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _restore(state_dir: Path, state: dict) -> None:
    target_root = Path(state["target_internal_dir"])
    backup_root = state_dir / _BACKUP_DIR
    for rel in reversed(state.get("applied", [])):
        safe_rel = _normal_relpath(rel)
        backup = backup_root / safe_rel
        target = target_root / safe_rel
        if backup.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, target)
        else:
            target.unlink(missing_ok=True)
    state["status"] = "rolled_back"
    _write_state(state_dir, state)


def apply_pending_update(state_dir_name: str, parent_pid: int | None = None) -> bool:
    """Apply one pending update after the GUI process has exited.

    Each replacement is journaled and backed up first.  If this helper dies,
    :func:`recover_incomplete_updates` restores the previous complete code
    layer before the next GUI startup.
    """
    state_dir = Path(state_dir_name)
    state = _read_state(state_dir)
    if parent_pid:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                os.kill(parent_pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            return False

    if state.get("status") not in {"pending", "applying"}:
        return state.get("status") == "complete"
    if state.get("status") == "applying":
        _restore(state_dir, state)
        return False

    target_root = Path(state["target_internal_dir"])
    payload_root = state_dir / _PAYLOAD_DIR
    backup_root = state_dir / _BACKUP_DIR
    if not target_root.is_dir():
        raise ValueError("Khong tim thay thu muc cai dat de ap dung ban va.")

    state["status"] = "applying"
    _write_state(state_dir, state)
    try:
        for item in state["files"]:
            rel = _normal_relpath(item["path"])
            source = payload_root / rel
            target = target_root / rel
            if not source.is_file() or _sha256(source) != item["sha256"]:
                raise ValueError("Payload da thay doi sau khi xac thuc.")
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = backup_root / rel
            if target.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            staged = target.with_name(target.name + ".3t-new")
            shutil.copy2(source, staged)
            os.replace(staged, target)
            state["applied"].append(rel)
            _write_state(state_dir, state)
        state["status"] = "complete"
        _write_state(state_dir, state)
        # Persist only after every file has been replaced successfully.  A
        # rollback must retain the previous base version so the server offers
        # an appropriate package/full installer next time.
        from packages.updater.base_version import set_installed_base_version

        set_installed_base_version(str(state.get("base_version") or ""))
        return True
    except Exception:
        _restore(state_dir, state)
        return False


def recover_incomplete_updates() -> None:
    """Run before app imports; restore rather than guess after interruption."""
    root = _update_root()
    if not root.is_dir():
        return
    for state_dir in root.iterdir():
        if not state_dir.is_dir():
            continue
        try:
            state = _read_state(state_dir)
            if state.get("status") == "applying":
                _restore(state_dir, state)
            elif state.get("status") in {"complete", "rolled_back"}:
                shutil.rmtree(state_dir, ignore_errors=True)
        except Exception:
            # Preserve unknown state for support rather than deleting evidence.
            continue


def spawn_apply_helper(state_dir: str, *, parent_pid: int, executable: str) -> None:
    """Start the private helper, requesting UAC for a protected install.

    A normal per-machine installation lives in ``Program Files``.  A helper
    spawned from the normal user session cannot replace its files and used to
    silently roll the already verified patch back on the next launch.
    """
    args = ["--apply-delta", state_dir, str(parent_pid), executable]
    cwd = str(Path(executable).resolve().parent)
    if sys.platform == "win32":
        import ctypes

        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, subprocess.list2cmdline(args), cwd, 1
        )
        if int(result) <= 32:
            raise RuntimeError("Khong the xin quyen Administrator de ap dung ban cap nhat.")
        return
    subprocess.Popen([executable, *args], close_fds=True, cwd=cwd)


def run_apply_helper_from_argv(argv: list[str]) -> bool | None:
    """Return ``None`` unless argv is the private helper command."""
    if len(argv) != 5 or argv[1] != "--apply-delta":
        return None
    try:
        applied = apply_pending_update(argv[2], int(argv[3]))
        if applied:
            subprocess.Popen([argv[4]], close_fds=True, cwd=str(Path(argv[4]).resolve().parent))
        return applied
    except Exception:
        return False
