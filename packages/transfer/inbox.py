from __future__ import annotations

"""Staging + atomic rename cho file nhận qua P2P — theo kế hoạch gốc mục
5.2/9.4: mọi file nhận vào "Inbox ScanDoc" riêng, không ghi đè PDF đang mở
hay file nguồn người dùng, chỉ hiển thị sau khi hash khớp.
"""

import os
import sys
from pathlib import Path


def inbox_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    path = base / "3T Reader" / "Inbox ScanDoc"
    path.mkdir(parents=True, exist_ok=True)
    return path


def staged_path_for(file_name: str) -> Path:
    return inbox_dir() / f"{file_name}.part"


def final_path_for(file_name: str) -> Path:
    target = inbox_dir() / file_name
    if not target.exists():
        return target
    # Tránh ghi đè file cùng tên đã nhận trước đó — thêm hậu tố (1), (2)...
    stem, suffix = target.stem, target.suffix
    i = 1
    while True:
        candidate = inbox_dir() / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


class StagedReceive:
    """Ghi dữ liệu đã verify hash vào `.part`, chỉ đổi tên atomic sang file
    thật sau khi hash khớp — nếu sai/huỷ giữa chừng thì xoá `.part`, không
    bao giờ để lộ file dở dang trong danh sách tài liệu."""

    def __init__(self, file_name: str) -> None:
        from .protocol import sanitize_file_name

        self._file_name = sanitize_file_name(file_name)
        self._staged_path = staged_path_for(self._file_name)

    def write(self, data: bytes) -> None:
        with open(self._staged_path, "wb") as f:
            f.write(data)

    def commit(self) -> Path:
        """Đổi tên atomic sang file thật. Gọi sau khi đã verify hash."""
        final_path = final_path_for(self._file_name)
        os.replace(self._staged_path, final_path)
        return final_path

    def discard(self) -> None:
        self._staged_path.unlink(missing_ok=True)
