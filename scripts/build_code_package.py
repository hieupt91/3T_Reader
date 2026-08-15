"""Create the signed-content input for a B53 Windows delta package.

The resulting ZIP deliberately contains no signature: the VPS signs the ZIP's
SHA-256 together with its URL/base version.  Its local manifest lets the client
verify every file again before it is ever copied into ``_internal``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

DEFAULT_ROOTS = ("app", "packages", "core", "styles", "assets")
IMMUTABLE = {"main.pyc", "packages/updater/delta_runtime.pyc", "packages/updater/delta_runtime.py"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_code_package(internal_dir: Path, output: Path, roots: tuple[str, ...] = DEFAULT_ROOTS) -> str:
    """Write a deterministic ZIP and return its SHA-256 digest."""
    internal_dir = internal_dir.resolve()
    if not internal_dir.is_dir():
        raise ValueError(f"Khong tim thay _internal: {internal_dir}")
    files: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for root_name in roots:
        root = (internal_dir / root_name).resolve()
        if not root.is_relative_to(internal_dir):
            raise ValueError("Duong dan include khong an toan.")
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(internal_dir).as_posix()
            if rel in IMMUTABLE:
                # Normal project roots include packages/updater, where the
                # bootstrap lives.  Omit it silently; an explicit request to
                # package all of _internal is rejected below as a guardrail.
                if root_name in (".", ""):
                    raise ValueError(f"Khong duoc patch bootstrap bat bien: {rel}")
                continue
            if rel not in seen:
                files.append((path, rel))
                seen.add(rel)
    if not files:
        raise ValueError("Khong co file code nao de dong goi.")

    manifest = {"format": 1, "files": [{"path": rel, "sha256": _sha256(path)} for path, rel in files]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
        for path, rel in files:
            zf.write(path, f"payload/{rel}")
    return _sha256(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a B53 code-package ZIP from a PyInstaller _internal directory.")
    parser.add_argument("--internal-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include", nargs="*", default=list(DEFAULT_ROOTS), metavar="DIR")
    args = parser.parse_args(argv)
    try:
        digest = build_code_package(args.internal_dir, args.output, tuple(args.include))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Created: {args.output}\nSHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
