from __future__ import annotations

import json
import os
import secrets
import string
from pathlib import Path
from threading import RLock

from .order_service import _send_email
from .passwords import hash_password, needs_rehash, verify_password

_DEFAULT_PASSWORD = os.environ.get("THREET_ADMIN_PASSWORD", "3tAdmin2026")
_ADMIN_EMAIL = os.environ.get("THREET_ADMIN_EMAIL", "3t.hotro@gmail.com")


class AdminConfig:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = RLock()

    def _load(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return {"password_hash": hash_password(_DEFAULT_PASSWORD)}
            try:
                return json.loads(self.path.read_text("utf-8"))
            except Exception:
                return {"password_hash": hash_password(_DEFAULT_PASSWORD)}

    def _save(self, data: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

    def verify_password(self, password: str) -> bool:
        data = self._load()
        stored = data.get("password_hash") or data.get("password") or _DEFAULT_PASSWORD
        ok = verify_password(password, stored)
        if ok and needs_rehash(stored):
            data.pop("password", None)
            data["password_hash"] = hash_password(password)
            self._save(data)
        return ok

    def get_password(self) -> str:
        return self._load().get("password", _DEFAULT_PASSWORD)

    def set_password(self, new_password: str, *, forced: bool = False) -> None:
        data = self._load()
        data.pop("password", None)
        data["password_hash"] = hash_password(new_password)
        data["must_change_password"] = forced
        self._save(data)

    def reset_password(self) -> str:
        alphabet = string.ascii_letters + string.digits
        new_password = "".join(secrets.choice(alphabet) for _ in range(12))
        self.set_password(new_password, forced=True)
        return new_password

    def must_change_password(self) -> bool:
        return bool(self._load().get("must_change_password", False))

    def get_2fa_secret(self) -> str | None:
        return self._load().get("totp_secret")

    def is_2fa_enabled(self) -> bool:
        return bool(self._load().get("totp_enabled", False))

    def set_2fa_secret(self, secret: str) -> None:
        data = self._load()
        data["totp_secret"] = secret
        data["totp_enabled"] = False
        self._save(data)

    def enable_2fa(self) -> None:
        data = self._load()
        data["totp_enabled"] = True
        self._save(data)

    def disable_2fa(self) -> None:
        data = self._load()
        data.pop("totp_secret", None)
        data["totp_enabled"] = False
        self._save(data)

    def get_update_config(self) -> dict:
        data = self._load()
        return data.get("update", {
            "mac_version": "",
            "mac_url": "",
            "mac_sha256": "",
            "win_version": "",
            "win_url": "",
            "win_sha256": "",
            "portable_url": "",
            "portable_sha256": "",
            "release_notes": "",
            "mandatory": False,
            # B53 (docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md) - field delta
            # update, chỉ dùng khi "update" key CHƯA tồn tại trong file config
            # (máy mới/lần đầu). Với config đã có sẵn "update" key (VPS thật
            # hiện tại), .get("update", {...}) trả nguyên dict đã lưu, không
            # merge default này vào - mọi nơi đọc field mới đều phải tự
            # .get(key, default) thay vì tin dict luôn đủ field.
            "win_base_version": "base-1.0",
            "win_code_url": "",
            "win_code_sha256": "",
            "mac_base_version": "base-1.0",
            "mac_code_url": "",
            "mac_code_sha256": "",
            "delta_enabled": False,
        })

    def set_update_config(self, cfg: dict) -> None:
        data = self._load()
        current = data.get("update", {})
        allowed = (
            "mac_version",
            "mac_url",
            "mac_sha256",
            "win_version",
            "win_url",
            "win_sha256",
            "portable_url",
            "portable_sha256",
            "release_notes",
            "mandatory",
            "prices",
            "payment",
            "promo_codes",
            "plan_content",
            "seo_title",
            "seo_description",
            "seo_keywords",
            "seo_og_image",
            "social_zalo",
            "social_facebook",
            "social_telegram",
            "win_base_version",
            "win_code_url",
            "win_code_sha256",
            "mac_base_version",
            "mac_code_url",
            "mac_code_sha256",
            "delta_enabled",
        )
        current.update({k: v for k, v in cfg.items() if k in allowed})
        data["update"] = current
        self._save(data)

    def get_prices(self) -> dict:
        cfg = self.get_update_config()
        default = {"basic": 300000, "personal": 500000, "enterprise": 800000}
        return {**default, **cfg.get("prices", {})}

    def send_password_by_email(self) -> bool:
        password = self.reset_password()
        html = f"""
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#1e293b">
  <div style="background:linear-gradient(135deg,#3b82f6,#6366f1);padding:24px;border-radius:12px 12px 0 0;text-align:center">
    <h2 style="color:#fff;margin:0;font-size:1.2rem">Khôi phục mật khẩu Admin</h2>
  </div>
  <div style="background:#f8fafc;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
    <p>Bạn đã yêu cầu đặt lại mật khẩu Admin Panel 3T Reader.</p>
    <div style="background:#1e293b;border-radius:10px;padding:20px;text-align:center;margin:20px 0">
      <p style="color:#94a3b8;font-size:.8rem;margin:0 0 8px">MAT KHAU MOI</p>
      <p style="color:#34d399;font-size:1.5rem;font-weight:700;letter-spacing:.12em;margin:0;font-family:monospace">{password}</p>
    </div>
    <p style="font-size:.85rem;color:#64748b">Dang nhap tai: <a href="https://reader.3tcomputer.com/admin" style="color:#6366f1">reader.3tcomputer.com/admin</a></p>
    <p style="font-size:.82rem;color:#94a3b8;margin-top:12px">Sau khi dang nhap, hay doi sang mat khau rieng trong phan Cai dat.</p>
  </div>
</div>
"""
        return _send_email(_ADMIN_EMAIL, "[3T Reader] Mat khau Admin moi", html)
