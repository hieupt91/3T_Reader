from __future__ import annotations

import os
import re
import secrets as _secrets
from datetime import datetime, timezone
from pathlib import Path

_KEY_PATTERN = re.compile(r'^3TR-[BPE]-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .config import settings
from .schemas import (
    ActivateRequest,
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    ReleaseManifestResponse,
    UpdateCheckResponse,
    ValidateRequest,
    ValidateResponse,
)
from .services.admin_config import AdminConfig
from .services.license_service import LicenseService
from .services.order_service import OrderStore
from .services.staff_service import StaffService
from .services.token_service import TokenService
from .services.state_store import FileStateStore
from .services.update_service import UpdateService


token_service = TokenService(settings.signing_secret)
state_store = FileStateStore(f"{settings.data_dir}/{settings.state_file}")
license_service = LicenseService(token_service, state_store=state_store)
order_store = OrderStore(f"{settings.data_dir}/orders.json")
admin_config = AdminConfig(f"{settings.data_dir}/admin-config.json")
staff_service = StaffService(f"{settings.data_dir}/staff.json")
update_service = UpdateService(token_service, admin_config=admin_config)

_STATIC = Path(__file__).parent / "static"
_active_tokens: set[str] = set()
_staff_tokens: dict[str, dict] = {}  # token → {username, permissions}
_bearer = HTTPBearer(auto_error=False)
_LICENSE_PREFIX = {"basic": "3TR-B", "personal": "3TR-P", "enterprise": "3TR-E"}

app = FastAPI(title=settings.app_name, version="0.3.0")

# Serve download files (DMG/EXE)
_DOWNLOADS = os.environ.get("THREET_DOWNLOADS_DIR", "/downloads")
if os.path.isdir(_DOWNLOADS):
    app.mount("/downloads", StaticFiles(directory=_DOWNLOADS), name="downloads")


# ── Sales page & admin ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    from fastapi.responses import Response

    with open(_STATIC / "index.html", "rb") as f:
        html = f.read()
    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@app.get("/admin", response_class=FileResponse)
def admin_page():
    from fastapi.responses import Response
    with open(_STATIC / "admin.html", "rb") as f:
        html = f.read()
    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@app.get("/support", response_class=FileResponse)
def support_page():
    return FileResponse(_STATIC / "support.html", media_type="text/html")


@app.get("/privacy", response_class=FileResponse)
def privacy_page():
    return FileResponse(_STATIC / "privacy.html", media_type="text/html")


@app.get("/terms", response_class=FileResponse)
def terms_page():
    return FileResponse(_STATIC / "terms.html", media_type="text/html")


class LoginRequest(BaseModel):
    password: str


@app.post("/api/admin/login")
def admin_login(req: LoginRequest):
    if not admin_config.verify_password(req.password):
        raise HTTPException(status_code=401, detail="Mật khẩu không đúng")
    tok = _secrets.token_hex(32)
    _active_tokens.add(tok)
    return {"token": tok, "role": "admin"}


class StaffLoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/staff/login")
def staff_login(req: StaffLoginRequest):
    if not staff_service.authenticate(req.username, req.password):
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng")
    info = staff_service.get_staff(req.username)
    tok = _secrets.token_hex(32)
    _staff_tokens[tok] = {
        "username": req.username.strip().lower(),
        "permissions": info.get("permissions", []),
    }
    return {
        "token": tok,
        "role": "staff",
        "username": req.username.strip().lower(),
        "permissions": info.get("permissions", []),
    }


def _require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if creds is None or creds.credentials not in _active_tokens:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên hết hạn")
    return creds.credentials


def _require_staff_or_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if creds is None:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    tok = creds.credentials
    if tok in _active_tokens:
        return {"role": "admin", "permissions": ["approve", "reject", "delete"]}
    if tok in _staff_tokens:
        return _staff_tokens[tok]
    raise HTTPException(status_code=401, detail="Phiên đăng nhập hết hạn")


def _infer_plan(record) -> str:
    raw_plan = str(getattr(record, "plan", "") or "").strip().lower()
    if raw_plan in {"basic", "personal", "enterprise"}:
        return raw_plan
    key = str(getattr(record, "license_key", "") or "").upper()
    if key.startswith("3TR-B-"):
        return "basic"
    if key.startswith("3TR-E-"):
        return "enterprise"
    return "personal"


def _plan_label(plan: str) -> str:
    return {
        "basic": "Cơ bản",
        "personal": "Cá nhân",
        "enterprise": "Doanh nghiệp",
    }.get(plan, plan)


def _guess_customer_type(plan: str) -> str:
    if plan == "enterprise":
        return "enterprise"
    return "personal"


def _license_status(record) -> str:
    if record.active_devices:
        if len(record.active_devices) >= record.seat_limit:
            return "full"
        return "active"
    if record.revoked_devices:
        return "revoked"
    return "unused"


def _format_device(record, device_id: str, payload: dict) -> dict:
    expires_at = payload.get("expires_at", "")
    issued_at = payload.get("issued_at", "")
    expired = license_service._is_expired(expires_at)
    return {
        "device_id": device_id,
        "machine_name": payload.get("machine_name", ""),
        "platform": payload.get("platform", ""),
        "app_version": payload.get("app_version", ""),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "status": "expired" if expired else "active",
        "license_key": record.license_key,
    }


def _license_to_admin_item(record) -> dict:
    plan = _infer_plan(record)
    devices = [
        _format_device(record, device_id, payload)
        for device_id, payload in sorted(record.active_devices.items())
    ]
    used_seats = len(record.active_devices)
    revoked_count = len(record.revoked_devices)
    return {
        "license_key": record.license_key,
        "customer_name": record.customer_name,
        "plan": plan,
        "plan_label": _plan_label(plan),
        "customer_type": _guess_customer_type(plan),
        "seat_limit": record.seat_limit,
        "used_seats": used_seats,
        "available_seats": max(0, record.seat_limit - used_seats),
        "revoked_devices": revoked_count,
        "status": _license_status(record),
        "devices": devices,
        "last_expires_at": max((d["expires_at"] for d in devices), default=""),
    }


def _build_license_summary(items: list[dict]) -> dict:
    summary = {
        "total": len(items),
        "unused": 0,
        "active": 0,
        "full": 0,
        "revoked": 0,
        "enterprise": 0,
        "personal": 0,
        "total_seats": 0,
        "used_seats": 0,
    }
    for item in items:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
        summary[item["customer_type"]] = summary.get(item["customer_type"], 0) + 1
        summary["total_seats"] += int(item["seat_limit"])
        summary["used_seats"] += int(item["used_seats"])
    return summary


def _make_license_key(plan: str) -> str:
    prefix = _LICENSE_PREFIX.get(plan, "3TR-P")
    parts = [prefix] + [
        "".join(_secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(4))
        for _ in range(3)
    ]
    return "-".join(parts)


def _release_file_type(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".dmg"):
        return "mac"
    if lower.endswith(".zip"):
        return "win-portable"
    return "win"


def _downloads_dir() -> Path:
    return Path(os.environ.get("THREET_DOWNLOADS_DIR", "/downloads"))


def _published_release_names() -> set[str]:
    cfg = admin_config.get_update_config()
    return {
        Path(cfg.get("win_url", "")).name,
        Path(cfg.get("mac_url", "")).name,
        Path(cfg.get("portable_url", "")).name,
    } - {""}


def _asset_roots() -> dict[str, Path]:
    root = _downloads_dir()
    return {
        "releases": root,
        "voices": root / "piper",
        "languages": root / "dicts",
        "modules": root / "modules",
    }


def _safe_asset_path(category: str, relative_path: str) -> Path:
    roots = _asset_roots()
    if category not in roots:
        raise HTTPException(status_code=400, detail="Danh mục tài nguyên không hợp lệ")
    rel = (relative_path or "").replace("\\", "/").strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise HTTPException(status_code=400, detail="Đường dẫn tài nguyên không hợp lệ")
    target = (roots[category] / rel).resolve()
    base = roots[category].resolve()
    if base not in target.parents and target != base:
        raise HTTPException(status_code=400, detail="Đường dẫn vượt phạm vi cho phép")
    return target


_DEFAULT_PLAN_PRICES = {"basic": 300_000, "personal": 500_000, "enterprise": 800_000}
_DEFAULT_PLAN_LABELS = {
    "basic": "Gói Cơ bản",
    "personal": "Gói Cá nhân",
    "enterprise": "Gói Doanh nghiệp",
}
_DEFAULT_PAYMENT_CONFIG = {
    "bank_name": "ACB (A Chau) - CN Quang Binh",
    "bank_code": "ACB",
    "account_number": "555566886",
    "account_name": "CTY TNHH DTCN & XAY LAP 3T",
    "transfer_note_template": "3TREADER {PLAN} {QTY}MAY {EMAIL}",
    "payment_note": "Vui long ghi dung noi dung chuyen khoan de he thong doi soat va cap key tu dong.",
}


def _get_sales_config() -> dict:
    cfg = admin_config.get_update_config()
    prices = dict(_DEFAULT_PLAN_PRICES)
    raw_prices = cfg.get("prices") or {}
    for key in _DEFAULT_PLAN_PRICES:
        try:
            prices[key] = max(0, int(raw_prices.get(key, prices[key])))
        except Exception:
            pass

    payment = dict(_DEFAULT_PAYMENT_CONFIG)
    raw_payment = cfg.get("payment") or {}
    for key, value in raw_payment.items():
        if key in payment and value is not None:
            payment[key] = str(value).strip()

    promos = []
    for item in cfg.get("promo_codes") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip().upper()
        if not code:
            continue
        promo_type = str(item.get("type", "percent")).strip().lower()
        if promo_type not in {"percent", "fixed"}:
            promo_type = "percent"
        try:
            value = max(0, int(item.get("value", 0)))
        except Exception:
            value = 0
        plans = item.get("plans") or []
        normalized_plans = [str(plan).strip().lower() for plan in plans if str(plan).strip().lower() in _DEFAULT_PLAN_PRICES]
        promos.append(
            {
                "code": code,
                "label": str(item.get("label", code)).strip() or code,
                "type": promo_type,
                "value": value,
                "active": bool(item.get("active", True)),
                "plans": normalized_plans,
                "note": str(item.get("note", "")).strip(),
            }
        )

    return {"prices": prices, "payment": payment, "promo_codes": promos}


def _build_transfer_note(template: str, plan: str, quantity: int, email: str, customer_name: str, promo_code: str = "") -> str:
    base = template or _DEFAULT_PAYMENT_CONFIG["transfer_note_template"]
    safe_email = (email or "").strip()
    safe_name = (customer_name or "").strip().replace(" ", "")
    note = base.format(
        PLAN=plan.upper(),
        PLAN_NAME=_DEFAULT_PLAN_LABELS.get(plan, plan),
        QTY=quantity,
        EMAIL=safe_email,
        NAME=safe_name,
        PROMO=promo_code.strip().upper(),
    )
    return " ".join(note.split()).strip()


def _quote_order(plan: str, quantity: int, promo_code: str = "") -> dict:
    sales = _get_sales_config()
    prices = sales["prices"]
    if plan not in prices:
        raise HTTPException(status_code=400, detail="Plan khong hop le")
    qty = max(1, min(int(quantity or 1), 100))
    unit_price = int(prices[plan])
    subtotal = unit_price * qty
    promo_input = (promo_code or "").strip().upper()
    applied_promo = None
    discount_amount = 0

    if promo_input:
        promo = next((item for item in sales["promo_codes"] if item["code"] == promo_input and item["active"]), None)
        if promo is None:
            raise HTTPException(status_code=400, detail="Ma khuyen mai khong hop le hoac da het han")
        allowed_plans = promo.get("plans") or []
        if allowed_plans and plan not in allowed_plans:
            raise HTTPException(status_code=400, detail="Ma khuyen mai khong ap dung cho goi nay")
        if promo["type"] == "percent":
            discount_amount = int(subtotal * promo["value"] / 100)
        else:
            discount_amount = int(promo["value"])
        discount_amount = max(0, min(discount_amount, subtotal))
        applied_promo = promo

    total = max(0, subtotal - discount_amount)
    return {
        "plan": plan,
        "plan_name": _DEFAULT_PLAN_LABELS.get(plan, plan),
        "quantity": qty,
        "unit_price": unit_price,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total": total,
        "promo_code": promo_input,
        "promo": applied_promo,
        "payment": sales["payment"],
    }


def _generate_order_id() -> str:
    return f"ORD-{datetime.now(tz=timezone.utc).strftime('%Y%m%d')}-{_secrets.token_hex(3).upper()}"


def _notify_admin_new_order(order: dict) -> None:
    try:
        from .services import order_service as order_service_module

        if hasattr(order_service_module, "_email_admin"):
            order_service_module._email_admin(order)
    except Exception:
        pass


def _create_order_record(customer_name: str, customer_email: str, plan: str, quantity: int, promo_code: str = "") -> dict:
    quote = _quote_order(plan, quantity, promo_code)
    order = {
        "id": _generate_order_id(),
        "plan": plan,
        "quantity": quote["quantity"],
        "unit_price": quote["unit_price"],
        "subtotal": quote["subtotal"],
        "discount_amount": quote["discount_amount"],
        "amount_total": quote["total"],
        "promo_code": quote["promo_code"],
        "promo_label": (quote["promo"] or {}).get("label", ""),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "status": "pending",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "approved_at": None,
        "license_key": None,
    }
    data = order_store._load()
    data.setdefault("orders", {})
    data["orders"][order["id"]] = order
    order_store._save(data)
    _notify_admin_new_order(order)
    return order


@app.post("/api/admin/forgot-password")
def forgot_password():
    ok = admin_config.send_password_by_email()
    if not ok:
        raise HTTPException(status_code=503, detail="Không thể gửi email. Kiểm tra cấu hình SMTP.")
    return {"ok": True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/admin/change-password")
def change_password(req: ChangePasswordRequest, _=Depends(_require_admin)):
    if not admin_config.verify_password(req.current_password):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 6 ký tự")
    admin_config.set_password(req.new_password)
    _active_tokens.clear()
    return {"ok": True}


@app.get("/api/admin/orders")
def list_orders(user=Depends(_require_staff_or_admin)):
    return {"orders": order_store.list_orders()}


@app.post("/api/admin/orders/{order_id}/approve")
def approve_order(order_id: str, user=Depends(_require_staff_or_admin)):
    if user["role"] != "admin" and "approve" not in user.get("permissions", []):
        raise HTTPException(status_code=403, detail="Không có quyền cấp key")
    try:
        order = order_store.approve_order(order_id, license_service)
        return {"ok": True, "license_key": order["license_key"]}
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/orders/{order_id}/reject")
def reject_order(order_id: str, user=Depends(_require_staff_or_admin)):
    if user["role"] != "admin" and "reject" not in user.get("permissions", []):
        raise HTTPException(status_code=403, detail="Không có quyền từ chối đơn")
    try:
        order_store.reject_order(order_id)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/admin/orders/{order_id}")
def delete_order(order_id: str, user=Depends(_require_staff_or_admin)):
    if user["role"] != "admin" and "delete" not in user.get("permissions", []):
        raise HTTPException(status_code=403, detail="Không có quyền xóa đơn")
    try:
        order_store.delete_order(order_id)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/admin/orders/cleanup")
def cleanup_orders(user=Depends(_require_staff_or_admin)):
    if user["role"] != "admin" and "delete" not in user.get("permissions", []):
        raise HTTPException(status_code=403, detail="Không có quyền dọn dẹp")
    deleted = order_store.cleanup_old_rejected(days=30)
    return {"ok": True, "deleted": deleted}


# ── Staff management (admin only) ──────────────────────────────────

@app.get("/api/admin/staff")
def list_staff(_=Depends(_require_admin)):
    return {"staff": staff_service.list_staff()}


class StaffCreateRequest(BaseModel):
    username: str
    password: str
    permissions: list[str] = ["approve", "reject"]


@app.post("/api/admin/staff")
def create_staff(req: StaffCreateRequest, _=Depends(_require_admin)):
    try:
        result = staff_service.create_staff(req.username, req.password, req.permissions)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class StaffUpdateRequest(BaseModel):
    permissions: list[str]


@app.put("/api/admin/staff/{username}")
def update_staff(username: str, req: StaffUpdateRequest, _=Depends(_require_admin)):
    try:
        staff_service.update_permissions(username, req.permissions)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/admin/staff/{username}")
def delete_staff(username: str, _=Depends(_require_admin)):
    try:
        staff_service.delete_staff(username)
        to_remove = [t for t, info in _staff_tokens.items() if info["username"] == username]
        for t in to_remove:
            del _staff_tokens[t]
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


class OrderSubmitRequest(BaseModel):
    customer_name: str
    customer_email: str
    plan: str
    quantity: int = 1
    promo_code: str | None = None


@app.post("/api/v1/order/submit")
def submit_order(req: OrderSubmitRequest):
    if not req.customer_name.strip() or not req.customer_email.strip():
        raise HTTPException(status_code=422, detail="Vui lòng điền đầy đủ thông tin")
    order = _create_order_record(
        req.customer_name.strip(),
        req.customer_email.strip(),
        req.plan,
        req.quantity,
        req.promo_code or "",
    )
    return {
        "ok": True,
        "order_id": order["id"],
        "amount_total": order["amount_total"],
        "promo_code": order.get("promo_code", ""),
    }


@app.get("/api/public/site-config")
def public_site_config() -> dict:
    cfg = admin_config.get_update_config()
    sales = _get_sales_config()
    return {
        "downloads": {
            "win": {"version": cfg.get("win_version", ""), "url": cfg.get("win_url", "")},
            "portable": {"url": cfg.get("portable_url", "")},
            "mac": {"version": cfg.get("mac_version", ""), "url": cfg.get("mac_url", "")},
        },
        "plans": [
            {"code": code, "name": _DEFAULT_PLAN_LABELS[code], "price": sales["prices"][code]}
            for code in ("basic", "personal", "enterprise")
        ],
        "payment": sales["payment"],
        "promo_codes": [
            {
                "code": item["code"],
                "label": item["label"],
                "type": item["type"],
                "value": item["value"],
                "plans": item["plans"],
                "note": item["note"],
            }
            for item in sales["promo_codes"]
            if item["active"]
        ],
    }


@app.get("/api/public/order-quote")
def public_order_quote(plan: str, quantity: int = 1, promo_code: str = "", email: str = "", customer_name: str = "") -> dict:
    quote = _quote_order(plan, quantity, promo_code)
    payment = quote["payment"]
    note = _build_transfer_note(
        payment.get("transfer_note_template", ""),
        plan,
        quote["quantity"],
        email,
        customer_name,
        promo_code,
    )
    return {
        "plan": quote["plan"],
        "plan_name": quote["plan_name"],
        "quantity": quote["quantity"],
        "unit_price": quote["unit_price"],
        "subtotal": quote["subtotal"],
        "discount_amount": quote["discount_amount"],
        "amount_total": quote["total"],
        "promo_code": quote["promo_code"],
        "promo_label": (quote["promo"] or {}).get("label", ""),
        "payment": payment,
        "transfer_note": note,
    }


# ── Health ────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.get(f"/api/{settings.api_version}/health")
def api_health() -> dict:
    return health()


@app.post("/api/license/activate", response_model=ActivateResponse)
def activate(req: ActivateRequest) -> ActivateResponse:
    if not _KEY_PATTERN.match(req.license_key.strip().upper()):
        raise HTTPException(status_code=400, detail="Mã key không đúng định dạng. Ví dụ: 3TR-P-XXXX-XXXX-XXXX")
    req = req.model_copy(update={"license_key": req.license_key.strip().upper()})
    result = license_service.activate(
        req.license_key,
        req.device_id,
        req.platform,
        req.app_version,
        req.machine_name,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return ActivateResponse(
        status="ok",
        message=result["message"],
        license_key=result["license_key"],
        device_id=result["device_id"],
        token=result["token"],
        expires_at=result["expires_at"],
        grace_days=settings.grace_days,
        seat_limit=result["seat_limit"],
        plan=result.get("plan", "personal"),
    )


@app.post(f"/api/{settings.api_version}/license/activate", response_model=ActivateResponse)
def activate_v1(req: ActivateRequest) -> ActivateResponse:
    return activate(req)


@app.post("/api/license/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest) -> ValidateResponse:
    result = license_service.validate(req.token, req.device_id)
    return ValidateResponse(
        valid=bool(result["ok"]),
        message=result["message"],
        license_key=result.get("license_key"),
        device_id=result.get("device_id"),
        expires_at=result.get("expires_at"),
        grace_days=settings.grace_days if result["ok"] else None,
        plan=result.get("plan", "free"),
    )


@app.post(f"/api/{settings.api_version}/license/validate", response_model=ValidateResponse)
def validate_v1(req: ValidateRequest) -> ValidateResponse:
    return validate(req)


@app.post("/api/license/heartbeat", response_model=HeartbeatResponse)
def heartbeat(req: HeartbeatRequest) -> HeartbeatResponse:
    result = license_service.heartbeat(req.token, req.device_id)
    return HeartbeatResponse(ok=bool(result["ok"]), message=result["message"], plan=result.get("plan", "free"))


@app.post(f"/api/{settings.api_version}/license/heartbeat", response_model=HeartbeatResponse)
def heartbeat_v1(req: HeartbeatRequest) -> HeartbeatResponse:
    return heartbeat(req)


@app.post("/api/license/deactivate", response_model=DeactivateResponse)
def deactivate(req: DeactivateRequest) -> DeactivateResponse:
    result = license_service.deactivate(req.token, req.device_id, req.reason)
    return DeactivateResponse(ok=bool(result["ok"]), message=result["message"])


@app.post(f"/api/{settings.api_version}/license/deactivate", response_model=DeactivateResponse)
def deactivate_v1(req: DeactivateRequest) -> DeactivateResponse:
    return deactivate(req)


@app.get("/api/update/check", response_model=UpdateCheckResponse)
def update_check(platform: str, current_version: str) -> UpdateCheckResponse:
    manifest = update_service.build_manifest(platform, current_version)
    return UpdateCheckResponse(
        platform=manifest["platform"],
        current_version=manifest["current_version"],
        version=manifest["latest_version"],
        latest_version=manifest["latest_version"],
        download_url=manifest["download_url"],
        sha256=manifest["sha256"],
        portable_url=manifest.get("portable_url", ""),
        portable_sha256=manifest.get("portable_sha256", ""),
        mandatory=manifest["mandatory"],
        release_notes=manifest["release_notes"],
        signature=manifest.get("signature", ""),
    )


@app.get(f"/api/{settings.api_version}/update/check", response_model=UpdateCheckResponse)
def update_check_v1(platform: str, current_version: str) -> UpdateCheckResponse:
    return update_check(platform, current_version)


@app.get("/api/releases/{platform}/{version}", response_model=ReleaseManifestResponse)
def release_manifest(platform: str, version: str) -> ReleaseManifestResponse:
    manifest = update_service.build_manifest(platform, version)
    return ReleaseManifestResponse(
        platform=manifest["platform"],
        version=manifest["latest_version"],
        download_url=manifest["download_url"],
        sha256=manifest["sha256"],
        portable_url=manifest.get("portable_url", ""),
        portable_sha256=manifest.get("portable_sha256", ""),
        release_notes=manifest["release_notes"],
        signature=manifest["signature"],
    )


@app.get(f"/api/{settings.api_version}/releases/{{platform}}/{{version}}", response_model=ReleaseManifestResponse)
def release_manifest_v1(platform: str, version: str) -> ReleaseManifestResponse:
    return release_manifest(platform, version)





# ── Upload release file (admin only) ──────────────────────────────

@app.post("/api/admin/upload-release")
async def upload_release(
    file: UploadFile = File(...),
    platform: str = "mac",
    version: str = "1.0.0",
    _=Depends(_require_admin),
):
    import hashlib
    import shutil

    platform_key = (platform or "").strip().lower()
    if platform_key in ("mac", "darwin", "macos"):
        target = "mac"
        ext = ".dmg"
    elif platform_key in ("win-portable", "portable", "windows-portable"):
        target = "win-portable"
        ext = ".zip"
    else:
        target = "win"
        ext = ".exe"
    safe_version = re.sub(r"[^0-9A-Za-z._-]", "", version).strip() or "1.0.0"
    downloads_dir = os.environ.get("THREET_DOWNLOADS_DIR", "/downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    filename = f"3TReader-{safe_version}-{target}{ext}"
    dest = os.path.join(downloads_dir, filename)

    with open(dest, "wb") as f_out:
        shutil.copyfileobj(file.file, f_out)

    size = os.path.getsize(dest)
    sha256 = hashlib.sha256(Path(dest).read_bytes()).hexdigest()

    # Build URL — use host from settings or env
    base_url = os.environ.get("THREET_PUBLIC_BASE_URL", "https://reader.3tcomputer.com")
    download_url = f"{base_url}/downloads/{filename}"

    # Auto-update config
    cfg = admin_config.get_update_config()
    if target == "mac":
        cfg["mac_version"] = safe_version
        cfg["mac_url"] = download_url
        cfg["mac_sha256"] = sha256
    elif target == "win-portable":
        cfg["portable_url"] = download_url
        cfg["portable_sha256"] = sha256
    else:
        cfg["win_version"] = safe_version
        cfg["win_url"] = download_url
        cfg["win_sha256"] = sha256
    admin_config.set_update_config(cfg)
    update_service.admin_config = admin_config

    return {
        "ok": True,
        "filename": filename,
        "size": size,
        "download_url": download_url,
        "version": safe_version,
        "platform": target,
        "sha256": sha256,
    }


# ── Update config (admin only) ────────────────────────────────────

@app.get("/api/admin/update-config")
def get_update_config(_=Depends(_require_admin)) -> dict:
    return admin_config.get_update_config()


class UpdateConfigRequest(BaseModel):
    mac_version: str | None = None
    mac_url: str | None = None
    mac_sha256: str | None = None
    win_version: str | None = None
    win_url: str | None = None
    win_sha256: str | None = None
    portable_url: str | None = None
    portable_sha256: str | None = None
    release_notes: str | None = None
    mandatory: bool | None = None
    signature: str | None = None
    prices: dict[str, int] | None = None


@app.post("/api/admin/update-config")
def set_update_config(req: UpdateConfigRequest, _=Depends(_require_admin)) -> dict:
    current = admin_config.get_update_config()
    current.update(req.model_dump(exclude_none=True))
    admin_config.set_update_config(current)
    # Inject updated config into update_service so next check picks it up
    update_service.admin_config = admin_config
    return {"ok": True}

@app.get("/api/admin/licenses")
def admin_licenses(_=Depends(_require_staff_or_admin)) -> dict:
    items = [_license_to_admin_item(record) for record in license_service.licenses.values()]
    items.sort(key=lambda item: (item["status"] != "active", item["customer_name"].lower(), item["license_key"]))
    summary = _build_license_summary(items)
    return {"items": items, "licenses": items, "summary": summary}


class ManualLicenseCreateRequest(BaseModel):
    customer_name: str
    plan: str = "personal"
    seat_limit: int = 1


@app.post("/api/admin/licenses/manual-create")
def admin_create_license(req: ManualLicenseCreateRequest, _=Depends(_require_admin)) -> dict:
    customer_name = req.customer_name.strip()
    plan = (req.plan or "personal").strip().lower()
    seat_limit = max(1, min(int(req.seat_limit or 1), 500))
    if not customer_name:
        raise HTTPException(status_code=400, detail="Tên khách hàng không được để trống")
    if plan not in {"basic", "personal", "enterprise"}:
        raise HTTPException(status_code=400, detail="Plan không hợp lệ")
    license_key = _make_license_key(plan)
    from .models import LicenseRecord

    record = LicenseRecord(
        license_key=license_key,
        customer_name=customer_name,
        seat_limit=seat_limit,
        plan=plan,
    )
    license_service.licenses[license_key] = record
    license_service._save()
    return {"ok": True, "item": _license_to_admin_item(record)}


@app.post("/api/admin/licenses/{license_key}/revoke-device")
def admin_revoke_device(license_key: str, device_id: str, _=Depends(_require_admin)) -> dict:
    record = license_service.licenses.get(license_key)
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy license key")
    if device_id not in record.active_devices:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị đang kích hoạt")
    record.active_devices.pop(device_id, None)
    record.revoked_devices.add(device_id)
    license_service._save()
    return {"ok": True, "item": _license_to_admin_item(record)}


@app.delete("/api/admin/licenses/{license_key}")
def admin_delete_license(license_key: str, _=Depends(_require_admin)) -> dict:
    record = license_service.licenses.get(license_key)
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy license key")
    if record.active_devices:
        raise HTTPException(status_code=400, detail="Không thể xóa key đang có thiết bị kích hoạt")
    license_service.licenses.pop(license_key, None)
    license_service._save()
    return {"ok": True}


@app.get("/api/admin/pricing")
def admin_get_pricing(_=Depends(_require_admin)) -> dict:
    cfg = admin_config.get_update_config()
    sales = _get_sales_config()
    prices = sales["prices"]
    return {
        "prices": prices,
        "plans": [
            {"code": "basic", "label": "Cơ bản", "price": prices.get("basic", 300000)},
            {"code": "personal", "label": "Cá nhân", "price": prices.get("personal", 500000)},
            {"code": "enterprise", "label": "Doanh nghiệp", "price": prices.get("enterprise", 800000)},
        ],
        "payment": sales["payment"],
        "promo_codes": sales["promo_codes"],
        "mandatory_update": bool(cfg.get("mandatory", False)),
    }


class PricingUpdateRequest(BaseModel):
    basic: int
    personal: int
    enterprise: int
    bank_name: str | None = None
    bank_code: str | None = None
    account_number: str | None = None
    account_name: str | None = None
    transfer_note_template: str | None = None
    payment_note: str | None = None
    promo_codes: list[dict] | None = None


@app.post("/api/admin/pricing")
def admin_set_pricing(req: PricingUpdateRequest, _=Depends(_require_admin)) -> dict:
    current = admin_config.get_update_config()
    current["prices"] = {
        "basic": max(0, int(req.basic)),
        "personal": max(0, int(req.personal)),
        "enterprise": max(0, int(req.enterprise)),
    }
    current["payment"] = {
        "bank_name": (req.bank_name or "").strip() or _DEFAULT_PAYMENT_CONFIG["bank_name"],
        "bank_code": (req.bank_code or "").strip().upper() or _DEFAULT_PAYMENT_CONFIG["bank_code"],
        "account_number": (req.account_number or "").strip() or _DEFAULT_PAYMENT_CONFIG["account_number"],
        "account_name": (req.account_name or "").strip() or _DEFAULT_PAYMENT_CONFIG["account_name"],
        "transfer_note_template": (req.transfer_note_template or "").strip() or _DEFAULT_PAYMENT_CONFIG["transfer_note_template"],
        "payment_note": (req.payment_note or "").strip() or _DEFAULT_PAYMENT_CONFIG["payment_note"],
    }
    promo_items = []
    for item in req.promo_codes or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip().upper()
        if not code:
            continue
        promo_type = str(item.get("type", "percent")).strip().lower()
        if promo_type not in {"percent", "fixed"}:
            promo_type = "percent"
        try:
            value = max(0, int(item.get("value", 0)))
        except Exception:
            value = 0
        raw_plans = item.get("plans", [])
        if isinstance(raw_plans, str):
            raw_plans = [part.strip() for part in raw_plans.split(",")]
        plans = [str(plan).strip().lower() for plan in (raw_plans or []) if str(plan).strip().lower() in _DEFAULT_PLAN_PRICES]
        promo_items.append(
            {
                "code": code,
                "label": str(item.get("label", code)).strip() or code,
                "type": promo_type,
                "value": value,
                "active": bool(item.get("active", True)),
                "plans": plans,
                "note": str(item.get("note", "")).strip(),
            }
        )
    current["promo_codes"] = promo_items
    admin_config.set_update_config(current)
    return {"ok": True, "prices": current["prices"], "payment": current["payment"], "promo_codes": current["promo_codes"]}


@app.get("/api/admin/releases")
def admin_releases(_=Depends(_require_admin)) -> dict:
    downloads_dir = _downloads_dir()
    cfg = admin_config.get_update_config()
    published_hashes = {
        Path(cfg.get("win_url", "")).name: cfg.get("win_sha256", ""),
        Path(cfg.get("mac_url", "")).name: cfg.get("mac_sha256", ""),
        Path(cfg.get("portable_url", "")).name: cfg.get("portable_sha256", ""),
    }
    published_names = _published_release_names()
    items: list[dict] = []
    if downloads_dir.exists():
        for path in sorted(downloads_dir.glob("3TReader-*"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = path.stat()
            sha256 = published_hashes.get(path.name, "")
            is_published = path.name in published_names
            items.append(
                {
                    "filename": path.name,
                    "platform": _release_file_type(path.name),
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "download_url": f"{os.environ.get('THREET_PUBLIC_BASE_URL', 'https://reader.3tcomputer.com')}/downloads/{path.name}",
                    "sha256": sha256,
                    "published": is_published,
                    "can_delete": not is_published,
                }
            )
    return {
        "items": items,
        "current": {
            "win_version": cfg.get("win_version", ""),
            "win_url": cfg.get("win_url", ""),
            "mac_version": cfg.get("mac_version", ""),
            "mac_url": cfg.get("mac_url", ""),
            "portable_url": cfg.get("portable_url", ""),
            "release_notes": cfg.get("release_notes", ""),
            "mandatory": bool(cfg.get("mandatory", False)),
        },
    }


@app.delete("/api/admin/releases/{filename}")
def admin_delete_release(filename: str, _=Depends(_require_admin)) -> dict:
    path = (_downloads_dir() / filename).resolve()
    base = _downloads_dir().resolve()
    if base not in path.parents:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")
    if path.name in _published_release_names():
        raise HTTPException(status_code=400, detail="Không thể xóa file đang được publish")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy file release")
    path.unlink()
    return {"ok": True}


@app.get("/api/admin/assets")
def admin_assets(_=Depends(_require_admin)) -> dict:
    base_url = os.environ.get("THREET_PUBLIC_BASE_URL", "https://reader.3tcomputer.com")
    items: list[dict] = []
    for category, root in _asset_roots().items():
        if not root.exists():
            continue
        for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True):
            rel = path.relative_to(root).as_posix()
            stat = path.stat()
            url_path = path.relative_to(_downloads_dir()).as_posix()
            items.append(
                {
                    "category": category,
                    "relative_path": rel,
                    "filename": path.name,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "download_url": f"{base_url}/downloads/{url_path}",
                }
            )
    return {"items": items}


@app.post("/api/admin/upload-asset")
async def admin_upload_asset(
    file: UploadFile = File(...),
    category: str = "voices",
    subdir: str = "",
    _=Depends(_require_admin),
):
    import shutil

    roots = _asset_roots()
    if category not in roots or category == "releases":
        raise HTTPException(status_code=400, detail="Danh mục upload không hợp lệ")
    clean_subdir = (subdir or "").replace("\\", "/").strip().strip("/")
    if ".." in clean_subdir.split("/"):
        raise HTTPException(status_code=400, detail="Thư mục đích không hợp lệ")
    target_dir = (roots[category] / clean_subdir).resolve()
    base = roots[category].resolve()
    if base not in target_dir.parents and target_dir != base:
        raise HTTPException(status_code=400, detail="Thư mục đích vượt phạm vi cho phép")
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "asset.bin").name
    dest = target_dir / safe_name
    with open(dest, "wb") as f_out:
        shutil.copyfileobj(file.file, f_out)
    return {"ok": True, "filename": safe_name, "category": category, "subdir": clean_subdir}


@app.delete("/api/admin/assets")
def admin_delete_asset(category: str, path: str, _=Depends(_require_admin)) -> dict:
    target = _safe_asset_path(category, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tài nguyên")
    target.unlink()
    return {"ok": True}


@app.get("/api/admin/dashboard")
def admin_dashboard(_=Depends(_require_staff_or_admin)) -> dict:
    orders = order_store.list_orders()
    licenses = [_license_to_admin_item(record) for record in license_service.licenses.values()]
    devices = []
    for item in licenses:
        devices.extend(item["devices"])
    return {
        "orders": {
            "total": len(orders),
            "pending": sum(1 for order in orders if order.get("status") == "pending"),
            "approved": sum(1 for order in orders if order.get("status") == "approved"),
            "rejected": sum(1 for order in orders if order.get("status") == "rejected"),
            "revenue_total": sum(int(order.get("amount_total") or 0) for order in orders if order.get("status") == "approved"),
        },
        "licenses": _build_license_summary(licenses),
        "devices": {
            "total": len(devices),
            "windows": sum(1 for device in devices if device.get("platform") == "windows"),
            "mac": sum(1 for device in devices if device.get("platform") == "darwin"),
            "expired": sum(1 for device in devices if device.get("status") == "expired"),
        },
    }


@app.get("/api/admin/devices")
def admin_devices(_=Depends(_require_staff_or_admin)) -> dict:
    devices = []
    for record in license_service.licenses.values():
        for device_id, payload in record.active_devices.items():
            devices.append(_format_device(record, device_id, payload))
    return {"items": devices}
