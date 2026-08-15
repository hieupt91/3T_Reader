"""Sign Windows build artifacts with signtool.

Usage examples:
  python scripts/sign_windows.py --file dist/3T_Reader/3T_Reader.exe --pfx cert.pfx --password %SIGNING_PASSWORD%
  python scripts/sign_windows.py --file build/installer/Setup_3T_Reader_v1.0.7.exe --cert-subject "3T Company"

Requires Windows SDK signtool.exe and an OV/EV code signing certificate.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


TIMESTAMP_URL = "http://timestamp.digicert.com"


def _signtool() -> str:
    tool = shutil.which("signtool.exe") or shutil.which("signtool")
    if tool:
        return tool
    raise SystemExit("signtool.exe not found. Install Windows SDK or add signtool to PATH.")


def sign_file(path: Path, *, pfx: str = "", password: str = "", cert_subject: str = "") -> None:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    cmd = [
        _signtool(),
        "sign",
        "/fd",
        "sha256",
        "/td",
        "sha256",
        "/tr",
        TIMESTAMP_URL,
    ]
    if pfx:
        cmd.extend(["/f", pfx])
        if password:
            cmd.extend(["/p", password])
    elif cert_subject:
        cmd.extend(["/n", cert_subject])
    else:
        cmd.append("/a")
    cmd.append(str(path))
    subprocess.run(cmd, check=True)


def verify_file(path: Path) -> None:
    subprocess.run([_signtool(), "verify", "/pa", "/v", str(path)], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sign and verify Windows executable/installer artifacts.")
    parser.add_argument("--file", required=True, type=Path, help="Executable or installer to sign")
    parser.add_argument("--pfx", default="", help="PFX certificate path")
    parser.add_argument("--password", default="", help="PFX password")
    parser.add_argument("--cert-subject", default="", help="Certificate subject in Windows cert store")
    parser.add_argument("--no-verify", action="store_true", help="Skip signtool verify after signing")
    args = parser.parse_args(argv)

    sign_file(args.file, pfx=args.pfx, password=args.password, cert_subject=args.cert_subject)
    if not args.no_verify:
        verify_file(args.file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
