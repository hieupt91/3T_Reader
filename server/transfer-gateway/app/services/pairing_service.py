from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import redis_client
from ..config import settings
from ..models import Device, PairingSession
from .device_service import count_active_companions, get_device
from .token_service_v2 import token_service_v2

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # Base32 dễ đọc, bỏ ký tự dễ nhầm (0/O, 1/I/L)


def _generate_code() -> str:
    raw = os.urandom(8)
    chars = [_CODE_ALPHABET[b % len(_CODE_ALPHABET)] for b in raw]
    code = "".join(chars[:8])
    return f"{code[:4]}-{code[4:]}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().replace("-", "").encode("utf-8")).hexdigest()


async def create_companion_session(db: AsyncSession, desktop_device: Device) -> dict:
    license_id = desktop_device.license_id
    from ..models import LicenseV2

    license_row = (
        await db.execute(select(LicenseV2).where(LicenseV2.license_id == license_id))
    ).scalar_one_or_none()
    if license_row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy license.")

    active = await count_active_companions(db, license_id)
    if active >= license_row.mobile_companion_limit:
        raise HTTPException(status_code=403, detail="Đã đạt giới hạn thiết bị companion cho key này.")

    code = _generate_code()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.pairing_code_ttl_seconds)
    nonce = base64.urlsafe_b64encode(os.urandom(12)).decode("ascii").rstrip("=")

    session = PairingSession(
        code_hash=_hash_code(code),
        initiator_device_id=desktop_device.device_id,
        intended_direction="add_companion",
        nonce=nonce,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()
    await db.commit()

    redis_key = f"pairing:{session.pairing_session_id}"
    await redis_client.set(redis_key, "pending", ex=settings.pairing_code_ttl_seconds)

    qr_payload = (
        '{"v":1,"pairing_session_id":"%s","nonce":"%s"}' % (session.pairing_session_id, nonce)
    )
    return {
        "pairing_session_id": str(session.pairing_session_id),
        "code": code,
        "qr_payload": qr_payload,
        "expires_at": expires_at,
    }


async def claim_companion_session(
    db: AsyncSession,
    *,
    pairing_session_id: uuid.UUID,
    code: str,
    device_public_key: str,
    device_type: str,
    display_name: str,
    client_ip: str,
) -> dict:
    if device_type not in ("iphone", "ipad"):
        raise HTTPException(status_code=400, detail="device_type phải là iphone hoặc ipad.")

    attempts_key = f"pairing_attempts:{client_ip}:{pairing_session_id}"
    attempts = await redis_client.incr(attempts_key)
    if attempts == 1:
        await redis_client.expire(attempts_key, settings.pairing_code_ttl_seconds)
    if attempts > settings.pairing_max_attempts:
        raise HTTPException(status_code=429, detail="Quá nhiều lần thử mã, phiên ghép nối đã bị khóa.")

    session = (
        await db.execute(
            select(PairingSession).where(PairingSession.pairing_session_id == pairing_session_id)
        )
    ).scalar_one_or_none()
    if session is None or session.status != "pending":
        raise HTTPException(status_code=410, detail="Phiên ghép nối không tồn tại hoặc đã dùng.")

    now = datetime.now(timezone.utc)
    if now > session.expires_at:
        session.status = "expired"
        await db.commit()
        raise HTTPException(status_code=410, detail="Mã đã hết hạn.")

    if session.code_hash != _hash_code(code):
        raise HTTPException(status_code=400, detail="Mã không đúng.")

    desktop = await get_device(db, session.initiator_device_id)
    if desktop is None or desktop.revoked_at is not None:
        raise HTTPException(status_code=403, detail="Thiết bị desktop khởi tạo phiên đã bị thu hồi.")

    from ..models import LicenseV2

    license_row = (
        await db.execute(select(LicenseV2).where(LicenseV2.license_id == desktop.license_id))
    ).scalar_one_or_none()
    active = await count_active_companions(db, desktop.license_id)
    if active >= license_row.mobile_companion_limit:
        raise HTTPException(status_code=403, detail="Đã đạt giới hạn thiết bị companion cho key này.")

    companion = Device(
        license_id=desktop.license_id,
        device_type=device_type,
        public_key=device_public_key,
        display_name=display_name or device_type,
        parent_desktop_device_id=desktop.device_id,
    )
    db.add(companion)

    session.status = "claimed"
    session.consumed_at = now
    await db.commit()
    await db.refresh(companion)

    await redis_client.delete(f"pairing:{pairing_session_id}")

    expires_at = now + timedelta(days=365)
    token_payload = {
        "device_id": str(companion.device_id),
        "license_id": str(companion.license_id),
        "device_type": device_type,
        "aud": "transfer-session",
        "scope": ["companion:pair", "transfer:send", "transfer:receive"],
        "issued_at": time.time(),
        "expires_at": expires_at.timestamp(),
    }
    device_token = token_service_v2.sign(token_payload)

    return {
        "device_token": device_token,
        "parent_desktop_device_id": str(desktop.device_id),
        "expires_at": expires_at,
    }
