from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import SessionLocal, get_db, init_db
from .models import Device
from .schemas import (
    CompanionClaimByKeyRequest,
    CompanionSessionClaimRequest,
    CompanionSessionClaimResponse,
    CompanionSessionCreateResponse,
    DeviceListItem,
    DeviceRevokeResponse,
    TransferSessionCompleteRequest,
    TransferSessionCompleteResponse,
    TransferSessionCreateRequest,
    TransferSessionCreateResponse,
    TransferSessionJoinResponse,
)
from .services import audit_service, pairing_service, transfer_session_service
from .services.device_service import get_device, resolve_companion_device, resolve_desktop_device
from .services.signaling import SignalingError, signaling_relay, validate_message

_RATE_BUCKETS: dict[tuple[str, str], list[float]] = {}


def _client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    xr = request.headers.get("x-real-ip")
    if xr:
        return xr.strip()
    return request.client.host if request.client else "unknown"


def rate_dep(bucket: str, max_hits: int, window_s: float):
    def _dep(request: Request) -> None:
        ip = _client_ip(request)
        now = time.time()
        key = (bucket, ip)
        hits = [t for t in _RATE_BUCKETS.get(key, []) if now - t < window_s]
        if len(hits) >= max_hits:
            raise HTTPException(status_code=429, detail="Quá nhiều yêu cầu, vui lòng thử lại sau.")
        hits.append(now)
        _RATE_BUCKETS[key] = hits

    return _dep


async def desktop_auth(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None),
) -> Device:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Thiếu Authorization: Bearer <token license V1>.")
    if not x_device_id:
        raise HTTPException(status_code=401, detail="Thiếu header X-Device-Id.")
    v1_token = authorization.split(" ", 1)[1].strip()
    return await resolve_desktop_device(db, v1_token, x_device_id)


async def any_device_auth(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None),
) -> Device:
    """Desktop (token V1 + X-Device-Id) hoặc companion đã pairing (token V2,
    4 phần dạng body.sig.ed2.key_id) — dùng cho transfer-sessions vì cả hai
    loại thiết bị đều có thể là bên gửi/nhận PDF."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Thiếu Authorization: Bearer <token>.")
    token = authorization.split(" ", 1)[1].strip()

    if token.count(".") == 3 and token.split(".")[2] == "ed2":
        return await resolve_companion_device(db, token)

    if not x_device_id:
        raise HTTPException(status_code=401, detail="Thiếu header X-Device-Id (token desktop V1).")
    return await resolve_desktop_device(db, token, x_device_id)


async def ws_any_device_auth(db: AsyncSession, token: str, v1_device_id: str | None) -> Device:
    if token.count(".") == 3 and token.split(".")[2] == "ed2":
        return await resolve_companion_device(db, token)
    if not v1_device_id:
        raise HTTPException(status_code=401, detail="Thiếu device_id cho token desktop V1.")
    return await resolve_desktop_device(db, token, v1_device_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.post(
    "/api/v2/business/companion-sessions",
    response_model=CompanionSessionCreateResponse,
    dependencies=[Depends(rate_dep("companion_create", 10, 300))],
)
async def create_companion_session(
    db: AsyncSession = Depends(get_db),
    desktop: Device = Depends(desktop_auth),
) -> CompanionSessionCreateResponse:
    correlation_id = str(uuid.uuid4())
    try:
        result = await pairing_service.create_companion_session(db, desktop)
    except HTTPException as exc:
        await audit_service.record(
            db, event_type="pair_create", result="error", correlation_id=correlation_id,
            device_id=desktop.device_id,
        )
        raise exc
    await audit_service.record(
        db, event_type="pair_create", result="ok", correlation_id=correlation_id,
        device_id=desktop.device_id,
    )
    return CompanionSessionCreateResponse(**result)


@app.post(
    "/api/v2/business/companion-sessions/{pairing_session_id}/claim",
    response_model=CompanionSessionClaimResponse,
    dependencies=[Depends(rate_dep("companion_claim", 30, 300))],
)
async def claim_companion_session(
    pairing_session_id: uuid.UUID,
    req: CompanionSessionClaimRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CompanionSessionClaimResponse:
    correlation_id = str(uuid.uuid4())
    try:
        result = await pairing_service.claim_companion_session(
            db,
            pairing_session_id=pairing_session_id,
            code=req.code,
            device_public_key=req.device_public_key,
            device_type=req.device_type,
            display_name=req.display_name,
            client_ip=_client_ip(request),
        )
    except HTTPException as exc:
        await audit_service.record(
            db, event_type="pair_claim", result="error", correlation_id=correlation_id,
        )
        raise exc
    await audit_service.record(db, event_type="pair_claim", result="ok", correlation_id=correlation_id)
    return CompanionSessionClaimResponse(**result)


@app.post(
    "/api/v2/business/companion-sessions/claim-by-key",
    response_model=CompanionSessionClaimResponse,
    dependencies=[Depends(rate_dep("companion_claim_by_key", 10, 300))],
)
async def claim_companion_by_key(
    req: CompanionClaimByKeyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CompanionSessionClaimResponse:
    """Kích hoạt bằng gõ thẳng key `3TR-E` trên điện thoại - không cần
    pairing_session_id do desktop tạo trước. Xem pairing_service.claim_by_key."""
    correlation_id = str(uuid.uuid4())
    try:
        result = await pairing_service.claim_by_key(
            db,
            license_key=req.license_key,
            device_public_key=req.device_public_key,
            device_type=req.device_type,
            display_name=req.display_name,
            client_ip=_client_ip(request),
        )
    except HTTPException as exc:
        await audit_service.record(
            db, event_type="key_claim", result="error", correlation_id=correlation_id,
        )
        raise exc
    await audit_service.record(db, event_type="key_claim", result="ok", correlation_id=correlation_id)
    return CompanionSessionClaimResponse(**result)


@app.get("/api/v2/business/devices", response_model=list[DeviceListItem])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    # Trước chỉ desktop_auth - companion (iPhone/iPad) không tự xem được danh
    # sách thiết bị cùng key. any_device_auth cho cả 2 loại gọi, response chỉ
    # gồm device_id/type/display_name/last_seen_at/revoked_at (không có token
    # hay dữ liệu nhạy cảm) nên an toàn khi mở cho companion.
    caller: Device = Depends(any_device_auth),
) -> list[DeviceListItem]:
    from sqlalchemy import select

    rows = (
        await db.execute(
            select(Device).where(
                Device.license_id == caller.license_id,
                Device.device_type.in_(["iphone", "ipad"]),
            )
        )
    ).scalars().all()
    return [
        DeviceListItem(
            device_id=str(d.device_id),
            device_type=d.device_type,
            display_name=d.display_name or "",
            last_seen_at=d.last_seen_at,
            revoked_at=d.revoked_at,
        )
        for d in rows
    ]


@app.post("/api/v2/devices/{device_id}/revoke", response_model=DeviceRevokeResponse)
async def revoke_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    desktop: Device = Depends(desktop_auth),
) -> DeviceRevokeResponse:
    target = await get_device(db, device_id)
    if target is None or target.license_id != desktop.license_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị thuộc key này.")

    from datetime import datetime, timezone

    target.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(target)

    await audit_service.record(
        db, event_type="revoke", result="ok", correlation_id=str(uuid.uuid4()), device_id=target.device_id
    )
    return DeviceRevokeResponse(ok=True, device_id=str(target.device_id), revoked_at=target.revoked_at)


@app.post("/api/v2/devices/self/revoke", response_model=DeviceRevokeResponse)
async def revoke_self(
    db: AsyncSession = Depends(get_db),
    device: Device = Depends(any_device_auth),
) -> DeviceRevokeResponse:
    """Cho companion (iPhone/iPad) tự huỷ ghép nối bằng chính device_token của
    nó - `revoke_device` ở trên chỉ nhận desktop_auth nên companion không gọi
    được. Thiếu route này là lý do "Huỷ ghép nối" trên ScanDoc trước đây chỉ
    xoá token cục bộ mà không giải phóng slot mobile_companion_limit ở server,
    khiến nhập lại đúng key báo "Đã đạt giới hạn" dù đã huỷ."""
    from datetime import datetime, timezone

    device.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(device)

    await audit_service.record(
        db, event_type="revoke_self", result="ok", correlation_id=str(uuid.uuid4()), device_id=device.device_id
    )
    return DeviceRevokeResponse(ok=True, device_id=str(device.device_id), revoked_at=device.revoked_at)


# ── Phase 2: transfer-sessions (P2P PDF, chỉ signaling — không có file bytes) ──


@app.post(
    "/api/v2/transfer-sessions",
    response_model=TransferSessionCreateResponse,
    dependencies=[Depends(rate_dep("transfer_create", 20, 60))],
)
async def create_transfer_session(
    req: TransferSessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    device: Device = Depends(any_device_auth),
) -> TransferSessionCreateResponse:
    correlation_id = str(uuid.uuid4())
    try:
        result = await transfer_session_service.create_session(
            db, device, req.auth_mode, req.file_name, req.file_size, req.ttl_seconds
        )
    except HTTPException as exc:
        await audit_service.record(
            db, event_type="transfer_start", result="error", correlation_id=correlation_id,
            device_id=device.device_id,
        )
        raise exc
    await audit_service.record(
        db, event_type="transfer_start", result="ok", correlation_id=correlation_id, device_id=device.device_id
    )
    return TransferSessionCreateResponse(**result)


@app.post(
    "/api/v2/transfer-sessions/{transfer_session_id}/join",
    response_model=TransferSessionJoinResponse,
    dependencies=[Depends(rate_dep("transfer_join", 20, 60))],
)
async def join_transfer_session(
    transfer_session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    device: Device = Depends(any_device_auth),
) -> TransferSessionJoinResponse:
    result = await transfer_session_service.join_session(db, device, transfer_session_id)
    return TransferSessionJoinResponse(**result)


@app.post(
    "/api/v2/transfer-sessions/{transfer_session_id}/complete",
    response_model=TransferSessionCompleteResponse,
)
async def complete_transfer_session(
    transfer_session_id: uuid.UUID,
    req: TransferSessionCompleteRequest,
    db: AsyncSession = Depends(get_db),
    device: Device = Depends(any_device_auth),
) -> TransferSessionCompleteResponse:
    correlation_id = str(uuid.uuid4())
    result = await transfer_session_service.complete_session(db, device, transfer_session_id, req.status)
    await audit_service.record(
        db, event_type=f"transfer_{req.status}", result="ok", correlation_id=correlation_id,
        device_id=device.device_id,
    )
    return TransferSessionCompleteResponse(**result)


@app.websocket("/api/v2/transfer-sessions/{transfer_session_id}/signal")
async def transfer_session_signal(websocket: WebSocket, transfer_session_id: uuid.UUID) -> None:
    token = websocket.query_params.get("token", "")
    v1_device_id = websocket.query_params.get("device_id")

    async with SessionLocal() as db:
        try:
            device = await ws_any_device_auth(db, token, v1_device_id)
        except HTTPException:
            await websocket.close(code=4401)
            return

        session = await transfer_session_service.get_session_participants(db, transfer_session_id)
        if session is None or device.device_id not in (session.sender_device_id, session.receiver_device_id):
            await websocket.close(code=4403)
            return

    await websocket.accept()
    await signaling_relay.register(transfer_session_id, device.device_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = validate_message(raw)
            except SignalingError as exc:
                await websocket.send_json({"type": "control", "error": str(exc)})
                continue
            await signaling_relay.relay(transfer_session_id, device.device_id, message)
    except WebSocketDisconnect:
        pass
    finally:
        signaling_relay.unregister(transfer_session_id, device.device_id)
