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

# Base version bootstrap NÀY thật sự có - chỉ bump khi delta_runtime.py (hay
# file bootstrap bất biến khác) đổi, TỨC LÀ đúng lúc 1 bản cài đặt đầy đủ
# mới được build. Base version chỉ có thể đổi qua cài đặt đầy đủ (delta
# không bao giờ nâng base - delta chỉ áp dụng khi base khớp sẵn), nên hằng
# số này luôn đáng tin hơn base_version.txt đã lưu.
NATIVE_BASE_VERSION = "base-1.2"


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


def reconcile_native_base_version() -> None:
    """Gọi 1 lần lúc khởi động (main.py, trước khi tạo QApplication).

    base_version.txt chỉ được delta_runtime.py ghi SAU một lần áp delta
    thành công - cài đặt đầy đủ (installer) không đụng tới file này. Hệ quả
    thật gặp phải (15/08/2026): máy đã từng áp delta lên base-1.1, sau đó
    được cài lại bằng bản đầy đủ base-1.2 mới hơn - base_version.txt vẫn còn
    "base-1.1" cũ, khiến server nghĩ máy chưa lên base-1.2 và không bao giờ
    cấp delta nữa cho tới khi ai đó tay xoá file này. Vì base version chỉ có
    thể đổi qua cài đặt đầy đủ (chưa bao giờ qua delta), NATIVE_BASE_VERSION
    của đúng bản đang chạy luôn là sự thật - ghi đè bất cứ giá trị cũ nào
    khác đi."""
    if get_installed_base_version() != NATIVE_BASE_VERSION:
        set_installed_base_version(NATIVE_BASE_VERSION)
