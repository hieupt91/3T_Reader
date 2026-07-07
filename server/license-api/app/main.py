from __future__ import annotations

import os
import re
import secrets as _secrets
import time
from pathlib import Path

_KEY_PATTERN = re.compile(r'^3TR-[BPE]-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
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
_TOKEN_TTL_SECONDS = 8 * 3600  # phiên đăng nhập admin/staff hết hạn sau 8 giờ
_active_tokens: dict[str, float] = {}  # token → thời điểm hết hạn (epoch)
_staff_tokens: dict[str, dict] = {}  # token → {username, permissions, expires_at}
_bearer = HTTPBearer(auto_error=False)
_RATE_BUCKETS: dict[tuple[str, str], list[float]] = {}


def _rate_dep(bucket: str, max_hits: int, window_s: float):
    """Dependency chống brute-force theo IP (fixed-window trong bộ nhớ)."""

    def _dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        key = (bucket, ip)
        hits = [t for t in _RATE_BUCKETS.get(key, []) if now - t < window_s]
        if len(hits) >= max_hits:
            raise HTTPException(status_code=429, detail="Quá nhiều yêu cầu, vui lòng thử lại sau.")
        hits.append(now)
        _RATE_BUCKETS[key] = hits

    return _dep


def _token_live(expires_at: float | None) -> bool:
    """True nếu token phiên còn hạn."""
    return expires_at is not None and time.time() <= expires_at

app = FastAPI(title=settings.app_name, version="0.3.0")

# Serve download files (DMG/EXE)
_DOWNLOADS = os.environ.get("THREET_DOWNLOADS_DIR", "/downloads")
if os.path.isdir(_DOWNLOADS):
    app.mount("/downloads", StaticFiles(directory=_DOWNLOADS), name="downloads")


# ── Sales page & admin ────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(_STATIC / "index.html", media_type="text/html")


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


@app.post("/api/admin/login", dependencies=[Depends(_rate_dep("admin_login", 5, 300))])
def admin_login(req: LoginRequest):
    if not admin_config.verify_password(req.password):
        raise HTTPException(status_code=401, detail="Mật khẩu không đúng")
    tok = _secrets.token_hex(32)
    _active_tokens[tok] = time.time() + _TOKEN_TTL_SECONDS
    return {"token": tok, "role": "admin"}


class StaffLoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/staff/login", dependencies=[Depends(_rate_dep("staff_login", 5, 300))])
def staff_login(req: StaffLoginRequest):
    if not staff_service.authenticate(req.username, req.password):
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng")
    info = staff_service.get_staff(req.username)
    tok = _secrets.token_hex(32)
    _staff_tokens[tok] = {
        "username": req.username.strip().lower(),
        "permissions": info.get("permissions", []),
        "expires_at": time.time() + _TOKEN_TTL_SECONDS,
    }
    return {
        "token": tok,
        "role": "staff",
        "username": req.username.strip().lower(),
        "permissions": info.get("permissions", []),
    }


def _admin_token_active(tok: str) -> bool:
    if not _token_live(_active_tokens.get(tok)):
        _active_tokens.pop(tok, None)  # dọn token hết hạn
        return False
    return True


def _staff_token_info(tok: str) -> dict | None:
    info = _staff_tokens.get(tok)
    if info is None:
        return None
    if not _token_live(info.get("expires_at")):
        _staff_tokens.pop(tok, None)
        return None
    return info


def _require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if creds is None or not _admin_token_active(creds.credentials):
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên hết hạn")
    return creds.credentials


def _require_staff_or_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if creds is None:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    tok = creds.credentials
    if _admin_token_active(tok):
        return {"role": "admin", "permissions": ["approve", "reject", "delete"]}
    info = _staff_token_info(tok)
    if info is not None:
        return info
    raise HTTPException(status_code=401, detail="Phiên đăng nhập hết hạn")


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


@app.post("/api/v1/order/submit", dependencies=[Depends(_rate_dep("order_submit", 5, 300))])
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


@app.post(
    "/api/license/activate",
    response_model=ActivateResponse,
    dependencies=[Depends(_rate_dep("license_activate", 10, 60))],
)
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


@app.post(
    f"/api/{settings.api_version}/license/activate",
    response_model=ActivateResponse,
    dependencies=[Depends(_rate_dep("license_activate", 10, 60))],
)
def activate_v1(req: ActivateRequest) -> ActivateResponse:
    return activate(req)


@app.post(
    "/api/license/validate",
    response_model=ValidateResponse,
    dependencies=[Depends(_rate_dep("license_validate", 60, 60))],
)
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


@app.post(
    f"/api/{settings.api_version}/license/validate",
    response_model=ValidateResponse,
    dependencies=[Depends(_rate_dep("license_validate", 60, 60))],
)
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

    target = "mac" if platform.lower() in ("mac", "darwin", "macos") else "win"
    safe_version = re.sub(r"[^0-9A-Za-z._-]", "", version).strip() or "1.0.0"
    ext = ".dmg" if target == "mac" else ".exe"
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
    mac_version: str = ""
    mac_url: str = ""
    win_version: str = ""
    win_url: str = ""
    release_notes: str = ""
    mandatory: bool = False


@app.post("/api/admin/update-config")
def set_update_config(req: UpdateConfigRequest, _=Depends(_require_admin)) -> dict:
    admin_config.set_update_config(req.model_dump())
    # Inject updated config into update_service so next check picks it up
    update_service.admin_config = admin_config
    return {"ok": True}

@app.get("/api/admin/licenses")
def admin_licenses(_=Depends(_require_staff_or_admin)) -> dict:
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
def admin_devices(_=Depends(_require_staff_or_admin)) -> dict:
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
