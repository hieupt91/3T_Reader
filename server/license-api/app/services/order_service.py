from __future__ import annotations

import json
import os
import secrets
import smtplib
import string
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from threading import RLock

def _parse_dt(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


_DEFAULT_PRICES = {"basic": 300_000, "personal": 500_000, "enterprise": 800_000}
_PLAN_NAMES = {"basic": "Gói Cơ Bản", "personal": "Gói Cá Nhân", "enterprise": "Gói Doanh Nghiệp"}

def _get_plan_meta(admin_cfg=None):
    prices = dict(_DEFAULT_PRICES)
    if admin_cfg is not None:
        try:
            prices.update(admin_cfg.get_prices())
        except Exception:
            pass
    return {k: {"name": _PLAN_NAMES[k], "amount": prices.get(k, _DEFAULT_PRICES[k]), "seat_limit": 1}
            for k in _PLAN_NAMES}

# Backward-compat alias (no admin_cfg = use defaults)
PLAN_META = _get_plan_meta()
PLAN_META_OVERRIDE = True

_ADMIN_EMAIL = os.environ.get("THREET_ADMIN_EMAIL", "3t.hotro@gmail.com")
_SMTP_USER   = os.environ.get("THREET_SMTP_USER", "3t.hotro@gmail.com")
_SMTP_PASS   = os.environ.get("THREET_SMTP_PASS", "")


def _gen_order_id() -> str:
    date = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"ORD-{date}-{suffix}"


def _gen_license_key(plan: str) -> str:
    prefix = {"basic": "3TR-B", "personal": "3TR-P", "enterprise": "3TR-E"}.get(plan, "3TR")
    parts = [prefix] + [
        "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        for _ in range(3)
    ]
    return "-".join(parts)


def _send_email(to: str, subject: str, html: str) -> bool:
    if not _SMTP_PASS:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"3T Reader <{_SMTP_USER}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as srv:
            srv.login(_SMTP_USER, _SMTP_PASS)
            srv.send_message(msg)
        return True
    except Exception:
        return False


def _email_customer(order: dict, license_key: str) -> bool:
    plan_name = PLAN_META.get(order["plan"], {}).get("name", order["plan"])
    quantity = int(order.get("quantity", 1))
    unit_price = PLAN_META.get(order["plan"], {}).get("amount", 0)
    total = order.get("amount_total", unit_price * quantity)
    device_text = f"{quantity} máy tính" if quantity > 1 else "1 máy tính"
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#1e293b">
  <div style="background:linear-gradient(135deg,#3b82f6,#6366f1);padding:28px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:1.4rem">🎉 Bản quyền 3T Reader</h1>
  </div>
  <div style="background:#f8fafc;padding:28px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0">
    <p>Xin chào <strong>{order['customer_name']}</strong>,</p>
    <p style="margin:12px 0">Cảm ơn bạn đã mua <strong>{plan_name}</strong>. Dưới đây là key bản quyền của bạn:</p>
    <div style="background:#1e293b;border-radius:10px;padding:20px;text-align:center;margin:20px 0">
      <p style="color:#94a3b8;font-size:.8rem;margin:0 0 8px">LICENSE KEY</p>
      <p style="color:#34d399;font-size:1.4rem;font-weight:700;letter-spacing:.1em;margin:0;font-family:monospace">{license_key}</p>
    </div>
    <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:16px 0;font-size:.88rem">
      <p style="margin:4px 0">📋 <strong>Gói:</strong> {plan_name}</p>
      <p style="margin:4px 0">🖥️ <strong>Số máy sử dụng:</strong> <span style="color:#6366f1;font-weight:700">{device_text}</span> / 1 năm</p>
      <p style="margin:4px 0">💰 <strong>Tổng thanh toán:</strong> {total:,}đ</p>
      <p style="margin:4px 0">📧 <strong>Mã đơn:</strong> {order['id']}</p>
    </div>
    <div style="background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;margin:16px 0;font-size:.85rem;color:#92400e">
      ⚠️ Key này được kích hoạt tối đa <strong>{device_text}</strong>. Mỗi lần kích hoạt trên 1 máy sẽ tính 1 lượt.
    </div>
    <p style="font-size:.85rem;color:#64748b">Hướng dẫn kích hoạt: Mở 3T Reader → menu <em>License</em> → nhập key ở trên → bấm <strong>Kích hoạt</strong>.</p>
    <p style="font-size:.85rem;color:#64748b;margin-top:12px">Cần hỗ trợ? Liên hệ: <a href="mailto:{_ADMIN_EMAIL}" style="color:#6366f1">{_ADMIN_EMAIL}</a></p>
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
    <p style="font-size:.78rem;color:#94a3b8;text-align:center">3T Reader – Phần mềm đọc PDF thông minh cho người Việt</p>
  </div>
</div>
"""
    return _send_email(order["customer_email"], "🔑 Key bản quyền 3T Reader của bạn", html)


def _email_admin(order: dict) -> bool:
    plan_name = PLAN_META.get(order["plan"], {}).get("name", order["plan"])
    unit_price = PLAN_META.get(order["plan"], {}).get("amount", 0)
    quantity = int(order.get("quantity", 1))
    total = order.get("amount_total", unit_price * quantity)
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:500px;margin:auto">
  <h2 style="color:#1e293b">📬 Đơn hàng mới – 3T Reader</h2>
  <table style="width:100%;border-collapse:collapse;font-size:.9rem">
    <tr><td style="padding:8px;color:#64748b;width:130px">Mã đơn</td><td style="padding:8px;font-weight:600">{order['id']}</td></tr>
    <tr style="background:#f8fafc"><td style="padding:8px;color:#64748b">Khách hàng</td><td style="padding:8px">{order['customer_name']}</td></tr>
    <tr><td style="padding:8px;color:#64748b">Email</td><td style="padding:8px">{order['customer_email']}</td></tr>
    <tr style="background:#f8fafc"><td style="padding:8px;color:#64748b">Gói</td><td style="padding:8px"><strong>{plan_name}</strong></td></tr>
    <tr><td style="padding:8px;color:#64748b">Số lượng máy</td><td style="padding:8px"><strong>{quantity} máy</strong></td></tr>
    <tr style="background:#f8fafc"><td style="padding:8px;color:#64748b">Tổng tiền</td><td style="padding:8px;color:#16a34a;font-weight:700">{total:,}đ</td></tr>
  </table>
  <p style="margin-top:16px">
    <a href="https://reader.3tcomputer.com/admin" style="background:#6366f1;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600">→ Vào Admin để duyệt</a>
  </p>
</div>
"""
    return _send_email(_ADMIN_EMAIL, f"[3T Reader] Đơn hàng mới: {order['id']}", html)


class OrderStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = RLock()

    def _load(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return {"orders": {}}
            try:
                return json.loads(self.path.read_text("utf-8"))
            except Exception:
                return {"orders": {}}

    def _save(self, data: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

    def list_orders(self) -> list[dict]:
        data = self._load()
        orders = list(data["orders"].values())
        orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)
        return orders

    def create_order(self, customer_name: str, customer_email: str, plan: str, quantity: int = 1) -> dict:
        if plan not in PLAN_META:
            raise ValueError(f"Plan không hợp lệ: {plan}")
        quantity = max(1, min(quantity, 100))
        meta = PLAN_META[plan]
        order = {
            "id": _gen_order_id(),
            "plan": plan,
            "quantity": quantity,
            "amount_total": meta["amount"] * quantity,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "status": "pending",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "approved_at": None,
            "license_key": None,
        }
        data = self._load()
        data["orders"][order["id"]] = order
        self._save(data)
        _email_admin(order)
        return order

    def approve_order(self, order_id: str, license_service) -> dict:
        data = self._load()
        order = data["orders"].get(order_id)
        if not order:
            raise KeyError("Đơn hàng không tồn tại")
        if order["status"] != "pending":
            raise ValueError("Đơn hàng này đã được xử lý")

        plan = order["plan"]
        quantity = int(order.get("quantity", 1))
        license_key = _gen_license_key(plan)

        # Add key to license store — seat_limit = số máy khách đặt
        from ..models import LicenseRecord
        record = LicenseRecord(
            license_key=license_key,
            customer_name=order["customer_name"],
            seat_limit=quantity,
        )
        license_service.licenses[license_key] = record
        license_service._save()

        order["status"] = "approved"
        order["license_key"] = license_key
        order["approved_at"] = datetime.now(tz=timezone.utc).isoformat()
        data["orders"][order_id] = order
        self._save(data)

        _email_customer(order, license_key)
        return order

    def reject_order(self, order_id: str) -> dict:
        data = self._load()
        order = data["orders"].get(order_id)
        if not order:
            raise KeyError("Đơn hàng không tồn tại")
        order["status"] = "rejected"
        data["orders"][order_id] = order
        self._save(data)
        return order

    def delete_order(self, order_id: str) -> None:
        data = self._load()
        if order_id not in data["orders"]:
            raise KeyError("Đơn hàng không tồn tại")
        del data["orders"][order_id]
        self._save(data)

    def cleanup_old_rejected(self, days: int = 30) -> int:
        """Xóa đơn bị từ chối quá `days` ngày."""
        data = self._load()
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        to_delete = [
            oid for oid, o in data["orders"].items()
            if o.get("status") == "rejected"
            and _parse_dt(o.get("created_at", "")) < cutoff
        ]
        for oid in to_delete:
            del data["orders"][oid]
        if to_delete:
            self._save(data)
        return len(to_delete)
