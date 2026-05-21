from __future__ import annotations

import os
import re
import secrets as _secrets
from pathlib import Path

_KEY_PATTERN = re.compile(r'^3TR-[BPE]-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
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
from .services.token_service import TokenService
from .services.state_store import FileStateStore
from .services.update_service import UpdateService


token_service = TokenService(settings.signing_secret)
state_store = FileStateStore(f"{settings.data_dir}/{settings.state_file}")
license_service = LicenseService(token_service, state_store=state_store)
update_service = UpdateService(token_service)
order_store = OrderStore(f"{settings.data_dir}/orders.json")
admin_config = AdminConfig(f"{settings.data_dir}/admin-config.json")

_ADMIN_PASSWORD = os.environ.get("THREET_ADMIN_PASSWORD", "3tAdmin2026")
_STATIC = Path(__file__).parent / "static"
_active_tokens: set[str] = set()
_bearer = HTTPBearer(auto_error=False)

app = FastAPI(title=settings.app_name, version="0.3.0")


# ── Sales page & admin ────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(_STATIC / "index.html", media_type="text/html")


@app.get("/admin", response_class=FileResponse)
def admin_page():
    return FileResponse(_STATIC / "admin.html", media_type="text/html")


class LoginRequest(BaseModel):
    password: str


@app.post("/api/admin/login")
def admin_login(req: LoginRequest):
    if req.password != admin_config.get_password():
        raise HTTPException(status_code=401, detail="Mật khẩu không đúng")
    tok = _secrets.token_hex(32)
    _active_tokens.add(tok)
    return {"token": tok}


def _require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if creds is None or creds.credentials not in _active_tokens:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên hết hạn")
    return creds.credentials


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
    if req.current_password != admin_config.get_password():
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 6 ký tự")
    admin_config.set_password(req.new_password)
    _active_tokens.clear()
    return {"ok": True}


@app.get("/api/admin/orders")
def list_orders(_=Depends(_require_admin)):
    return {"orders": order_store.list_orders()}


@app.post("/api/admin/orders/{order_id}/approve")
def approve_order(order_id: str, _=Depends(_require_admin)):
    try:
        order = order_store.approve_order(order_id, license_service)
        return {"ok": True, "license_key": order["license_key"]}
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/orders/{order_id}/reject")
def reject_order(order_id: str, _=Depends(_require_admin)):
    try:
        order_store.reject_order(order_id)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/admin/orders/{order_id}")
def delete_order(order_id: str, _=Depends(_require_admin)):
    try:
        order_store.delete_order(order_id)
        return {"ok": True}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/admin/orders/cleanup")
def cleanup_orders(_=Depends(_require_admin)):
    deleted = order_store.cleanup_old_rejected(days=30)
    return {"ok": True, "deleted": deleted}


class OrderSubmitRequest(BaseModel):
    customer_name: str
    customer_email: str
    plan: str
    quantity: int = 1


@app.post("/api/v1/order/submit")
def submit_order(req: OrderSubmitRequest):
    if not req.customer_name.strip() or not req.customer_email.strip():
        raise HTTPException(status_code=422, detail="Vui lòng điền đầy đủ thông tin")
    try:
        order = order_store.create_order(
            req.customer_name.strip(), req.customer_email.strip(), req.plan, req.quantity
        )
        return {"ok": True, "order_id": order["id"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    )


@app.post(f"/api/{settings.api_version}/license/validate", response_model=ValidateResponse)
def validate_v1(req: ValidateRequest) -> ValidateResponse:
    return validate(req)


@app.post("/api/license/heartbeat", response_model=HeartbeatResponse)
def heartbeat(req: HeartbeatRequest) -> HeartbeatResponse:
    result = license_service.heartbeat(req.token, req.device_id)
    return HeartbeatResponse(ok=bool(result["ok"]), message=result["message"])


@app.post(f"/api/{settings.api_version}/license/heartbeat", response_model=HeartbeatResponse)
def heartbeat_v1(req: HeartbeatRequest) -> HeartbeatResponse:
    return heartbeat(req)


@app.post("/api/license/deactivate", response_model=DeactivateResponse)
def deactivate(req: DeactivateRequest) -> DeactivateResponse:
    result = license_service.deactivate(req.token, req.device_id)
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
        latest_version=manifest["latest_version"],
        download_url=manifest["download_url"],
        sha256=manifest["sha256"],
        mandatory=manifest["mandatory"],
        release_notes=manifest["release_notes"],
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
        release_notes=manifest["release_notes"],
        signature=manifest["signature"],
    )


@app.get(f"/api/{settings.api_version}/releases/{{platform}}/{{version}}", response_model=ReleaseManifestResponse)
def release_manifest_v1(platform: str, version: str) -> ReleaseManifestResponse:
    return release_manifest(platform, version)


@app.get("/api/admin/licenses")
def admin_licenses() -> dict:
    return {
        "items": [
            {
                "license_key": record.license_key,
                "customer_name": record.customer_name,
                "seat_limit": record.seat_limit,
                "active_devices": len(record.active_devices),
            }
            for record in license_service.licenses.values()
        ]
    }


@app.get("/api/admin/devices")
def admin_devices() -> dict:
    devices = []
    for record in license_service.licenses.values():
        for device_id, payload in record.active_devices.items():
            devices.append(
                {
                    "license_key": record.license_key,
                    "device_id": device_id,
                    "platform": payload.get("platform", ""),
                    "app_version": payload.get("app_version", ""),
                }
            )
    return {"items": devices}
