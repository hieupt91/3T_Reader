from __future__ import annotations

import json
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from .passwords import hash_password, needs_rehash, verify_password


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
            "password_hash": hash_password(password),
            "permissions": permissions,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "must_change_password": True,
        }
        self._save(data)
        return {"username": username, "permissions": permissions}

    def update_permissions(self, username: str, permissions: list[str]) -> None:
        username = username.strip().lower()
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        valid_perms = {"approve", "reject", "delete"}
        data["staff"][username]["permissions"] = [p for p in permissions if p in valid_perms]
        self._save(data)

    def delete_staff(self, username: str) -> None:
        username = username.strip().lower()
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        del data["staff"][username]
        self._save(data)

    def get_2fa_secret(self, username: str) -> str | None:
        return self.get_staff(username).get("totp_secret")

    def is_2fa_enabled(self, username: str) -> bool:
        return bool(self.get_staff(username).get("totp_enabled", False))

    def set_2fa_secret(self, username: str, secret: str) -> None:
        username = username.strip().lower()
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        data["staff"][username]["totp_secret"] = secret
        data["staff"][username]["totp_enabled"] = False
        self._save(data)

    def enable_2fa(self, username: str) -> None:
        username = username.strip().lower()
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        data["staff"][username]["totp_enabled"] = True
        self._save(data)

    def disable_2fa(self, username: str) -> None:
        username = username.strip().lower()
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        data["staff"][username].pop("totp_secret", None)
        data["staff"][username]["totp_enabled"] = False
        self._save(data)

    def change_own_password(self, username: str, new_password: str) -> None:
        username = username.strip().lower()
        if len(new_password) < 6:
            raise ValueError("Mật khẩu mới phải có ít nhất 6 ký tự")
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        data["staff"][username].pop("password", None)
        data["staff"][username]["password_hash"] = hash_password(new_password)
        data["staff"][username]["must_change_password"] = False
        self._save(data)

    def reset_password(self, username: str) -> str:
        username = username.strip().lower()
        data = self._load()
        if username not in data["staff"]:
            raise KeyError(f"Nhân viên '{username}' không tồn tại")
        alphabet = string.ascii_letters + string.digits
        new_password = "".join(secrets.choice(alphabet) for _ in range(12))
        data["staff"][username].pop("password", None)
        data["staff"][username]["password_hash"] = hash_password(new_password)
        data["staff"][username]["must_change_password"] = True
        self._save(data)
        return new_password

    def must_change_password(self, username: str) -> bool:
        return bool(self.get_staff(username).get("must_change_password", False))

    def authenticate(self, username: str, password: str) -> bool:
        username = username.strip().lower()
        data = self._load()
        info = data["staff"].get(username)
        if not info:
            return False
        stored = info.get("password_hash") or info.get("password", "")
        ok = verify_password(password, stored)
        if ok and needs_rehash(stored):
            info.pop("password", None)
            info["password_hash"] = hash_password(password)
            data["staff"][username] = info
            self._save(data)
        return ok
