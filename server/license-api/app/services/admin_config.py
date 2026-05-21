from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from .order_service import _send_email

_DEFAULT_PASSWORD = os.environ.get("THREET_ADMIN_PASSWORD", "3tAdmin2026")
_ADMIN_EMAIL = os.environ.get("THREET_ADMIN_EMAIL", "3t.hotro@gmail.com")


class AdminConfig:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = RLock()

    def _load(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return {"password": _DEFAULT_PASSWORD}
            try:
                return json.loads(self.path.read_text("utf-8"))
            except Exception:
                return {"password": _DEFAULT_PASSWORD}

    def _save(self, data: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), "utf-8")

    def get_password(self) -> str:
        return self._load().get("password", _DEFAULT_PASSWORD)

    def set_password(self, new_password: str) -> None:
        data = self._load()
        data["password"] = new_password
        self._save(data)

    def send_password_by_email(self) -> bool:
        password = self.get_password()
        html = f"""
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#1e293b">
  <div style="background:linear-gradient(135deg,#3b82f6,#6366f1);padding:24px;border-radius:12px 12px 0 0;text-align:center">
    <h2 style="color:#fff;margin:0;font-size:1.2rem">🔐 Khôi phục mật khẩu Admin</h2>
  </div>
  <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
    <p>Bạn đã yêu cầu khôi phục mật khẩu Admin Panel 3T Reader.</p>
    <div style="background:#1e293b;border-radius:10px;padding:20px;text-align:center;margin:20px 0">
      <p style="color:#94a3b8;font-size:.8rem;margin:0 0 8px">MẬT KHẨU HIỆN TẠI</p>
      <p style="color:#34d399;font-size:1.5rem;font-weight:700;letter-spacing:.15em;margin:0;font-family:monospace">{password}</p>
    </div>
    <p style="font-size:.85rem;color:#64748b">Đăng nhập tại: <a href="https://reader.3tcomputer.com/admin" style="color:#6366f1">reader.3tcomputer.com/admin</a></p>
    <p style="font-size:.82rem;color:#94a3b8;margin-top:12px">Sau khi đăng nhập, hãy đổi sang mật khẩu mới trong phần Cài đặt.</p>
  </div>
</div>
"""
        return _send_email(_ADMIN_EMAIL, "[3T Reader] Khôi phục mật khẩu Admin", html)
