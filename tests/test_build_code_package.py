"""B53 code-package builder output must match the client's expected layout."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path


def _load_builder():
    path = Path(__file__).parents[1] / "scripts" / "build_code_package.py"
    spec = importlib.util.spec_from_file_location("build_code_package", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_builder_writes_manifest_and_payload(tmp_path):
    internal = tmp_path / "_internal"
    (internal / "app").mkdir(parents=True)
    source = internal / "app" / "window.pyc"
    source.write_bytes(b"patched")
    output = tmp_path / "patch.zip"

    digest = _load_builder().build_code_package(internal, output, ("app",))

    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with zipfile.ZipFile(output) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["files"] == [{"path": "app/window.pyc", "sha256": hashlib.sha256(b"patched").hexdigest()}]
        assert zf.read("payload/app/window.pyc") == b"patched"


def test_builder_never_includes_bootstrap(tmp_path):
    internal = tmp_path / "_internal"
    internal.mkdir()
    (internal / "main.pyc").write_bytes(b"bootstrap")

    try:
        _load_builder().build_code_package(internal, tmp_path / "patch.zip", (".",))
    except ValueError as exc:
        assert "bootstrap" in str(exc).lower()
    else:
        raise AssertionError("immutable bootstrap must be rejected")
