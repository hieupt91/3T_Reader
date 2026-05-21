from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock


class StaffService:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = RLock()

    def _load(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return {"staff": {}}
            try:
                return json.loads(self.path.read_text("utf-8"))
            except Exception:
                return {"staff": {}}

    def _save(self, data: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

    def list_staff(self) -> list[dict]:
        data = self._load()
        return [
            {
                "username": u,
                "permissions": info.get("permissions", []),
                "created_at": info.get("created_at", ""),
            }
            for u, info in data["staff"].items()
        ]

    def get_staff(self, username: str) -> dict:
        data = self._load()
        return data["staff"].get(username.strip().lower(), {})

    def create_staff(self, username: str, password: str, permissions: list[str]) -> dict:
        username = username.strip().lower()
        if not username or not password:
            raise ValueError("Tên đăng nhập và mật khẩu không được để trống")
        if len(password) < 6:
            raise ValueError("Mật khẩu phải có ít nhất 6 ký tự")
        valid_perms = {"approve", "reject", "delete"}
        permissions = [p for p in permissions if p in valid_perms]
        data = self._load()
        if username in data["staff"]:
            raise ValueError(f"Tên đăng nhập '{username}' đã tồn tại")
        data["staff"][username] = {
            "password": password,
            "permissions": permissions,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._save(data)
        return {"username": username, "permissions": permissions}

    def update_permissions(self, username: str, permissions: list[str]) -> None:
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        valid_perms = {"approve", "reject", "delete"}
        data["staff"][username]["permissions"] = [p for p in permissions if p in valid_perms]
        self._save(data)

    def delete_staff(self, username: str) -> None:
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        del data["staff"][username]
        self._save(data)

    def authenticate(self, username: str, password: str) -> bool:
        data = self._load()
        info = data["staff"].get(username.strip().lower())
        if not info:
            return False
        return info.get("password") == password
