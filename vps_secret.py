"""Central place to read VPS credentials from the environment.

Passwords must never be hardcoded in deploy scripts (SEC-01/02/03).
Set the environment variable before running any deploy/patch script:

    PowerShell:  $env:THREET_VPS_PASSWORD = "..."
    cmd.exe:     set THREET_VPS_PASSWORD=...
"""
from __future__ import annotations

import os


def vps_password() -> str:
    password = os.environ.get("THREET_VPS_PASSWORD", "")
    if not password:
        raise SystemExit(
            "THREET_VPS_PASSWORD chưa được thiết lập.\n"
            "Đặt biến môi trường trước khi chạy script deploy, ví dụ (PowerShell):\n"
            '  $env:THREET_VPS_PASSWORD = "<mật khẩu VPS>"'
        )
    return password
