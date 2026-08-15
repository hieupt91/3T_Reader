"""B53: theo dõi "base version" (runtime Qt/Python/Tesseract...) đã cài trên
máy người dùng, để server quyết định có thể vá bằng code package (delta) hay
phải tải full installer. Xem docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md.

Dùng packages.platform.get_app_data_dir() (đã cross-platform sẵn: %APPDATA%
trên Windows, ~/Library/Application Support trên macOS) thay vì tự tính
đường dẫn riêng cho từng OS.
"""
from __future__ import annotations

import os

_DEFAULT_BASE_VERSION = "base-1.0"
_FILE_NAME = "base_version.txt"


def _path() -> str:
    from packages.platform import get_app_data_dir

    return os.path.join(get_app_data_dir(), _FILE_NAME)


def get_installed_base_version() -> str:
    """Chưa có file (mọi bản cài hiện tại, kể cả 1.0.31) -> mặc định
    "base-1.0" - khớp đúng server_base_version mặc định phía backend, để
    bản delta ĐẦU TIÊN vẫn áp dụng được cho user đang chạy bản hiện tại."""
    try:
        with open(_path(), "r", encoding="utf-8") as fh:
            value = fh.read().strip()
            return value or _DEFAULT_BASE_VERSION
    except OSError:
        return _DEFAULT_BASE_VERSION


def set_installed_base_version(value: str) -> None:
    try:
        with open(_path(), "w", encoding="utf-8") as fh:
            fh.write((value or _DEFAULT_BASE_VERSION).strip())
    except OSError:
        pass
