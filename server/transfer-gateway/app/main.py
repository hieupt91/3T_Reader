from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_db, init_db
from .models import Device
from .schemas import (
    CompanionSessionClaimRequest,
    CompanionSessionClaimResponse,
    CompanionSessionCreateResponse,
    DeviceListItem,
    DeviceRevokeResponse,
)
from .services import audit_service, pairing_service
from .services.device_service import get_device, resolve_desktop_device

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


@app.get("/api/v2/business/devices", response_model=list[DeviceListItem])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    desktop: Device = Depends(desktop_auth),
) -> list[DeviceListItem]:
    from sqlalchemy import select

    rows = (
        await db.execute(
            select(Device).where(
                Device.license_id == desktop.license_id,
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
