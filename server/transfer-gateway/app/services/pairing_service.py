from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import redis_client
from ..config import settings
from ..models import Device, LicenseV2, PairingSession
from .device_service import count_active_companions, get_device
from .token_service_v2 import token_service_v2

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # Base32 dễ đọc, bỏ ký tự dễ nhầm (0/O, 1/I/L)
# Mã QR/kết nối chỉ sống 120s (settings.pairing_code_ttl_seconds) nên không
# lo lẫn ảnh hưởng thiết bị khác, nhưng row hết hạn không ai dùng vẫn nằm lại
# DB mãi nếu không dọn - dọn tranh thủ mỗi lần tạo mã mới, giống transfer_sessions.
_PAIRING_RETENTION = timedelta(hours=24)


def _generate_code() -> str:
    raw = os.urandom(8)
    chars = [_CODE_ALPHABET[b % len(_CODE_ALPHABET)] for b in raw]
    code = "".join(chars[:8])
    return f"{code[:4]}-{code[4:]}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().replace("-", "").encode("utf-8")).hexdigest()


async def _cleanup_stale_pairing_sessions(db: AsyncSession) -> None:
    cutoff = datetime.now(timezone.utc) - _PAIRING_RETENTION
    await db.execute(delete(PairingSession).where(PairingSession.expires_at < cutoff))


async def create_companion_session(db: AsyncSession, desktop_device: Device) -> dict:
    await _cleanup_stale_pairing_sessions(db)
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

    # Nhúng cả `code` vào QR để app di động quét 1 phát là điền luôn ô mã,
    # không bắt gõ tay nữa. An toàn tương đương bản cũ vì QR và mã vốn đã
    # hiển thị cùng lúc trên cùng màn hình 3TReader - gộp lại không lộ thêm
    # thông tin gì so với đọc cả hai bằng mắt.
    qr_payload = (
        '{"v":2,"pairing_session_id":"%s","nonce":"%s","code":"%s"}'
        % (session.pairing_session_id, nonce, code)
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


def _hash_license_key(license_key: str) -> str:
    return hashlib.sha256(license_key.strip().upper().encode("utf-8")).hexdigest()


async def claim_by_key(
    db: AsyncSession,
    *,
    license_key: str,
    device_public_key: str,
    device_type: str,
    display_name: str,
    client_ip: str,
) -> dict:
    """Kích hoạt bằng cách gõ thẳng key `3TR-E` trên điện thoại - KHÔNG cần có
    desktop 3TReader ở gần trước. Khác `claim_companion_session` (yêu cầu
    pairing_session_id do desktop tạo): đường này xác thực trực tiếp key qua
    license-api V1 (endpoint /license/peek - chỉ đọc, không tiêu seat), rồi tự
    tạo/tái sử dụng LicenseV2 + Device companion, `parent_desktop_device_id`
    để trống vì chưa gắn với desktop nào."""
    if device_type not in ("iphone", "ipad"):
        raise HTTPException(status_code=400, detail="device_type phải là iphone hoặc ipad.")

    normalized_key = license_key.strip().upper()
    if not normalized_key.startswith("3TR-E"):
        raise HTTPException(status_code=403, detail="Chỉ hỗ trợ key doanh nghiệp 3TR-E.")

    attempts_key = f"key_claim_attempts:{client_ip}"
    attempts = await redis_client.incr(attempts_key)
    if attempts == 1:
        await redis_client.expire(attempts_key, 3600)
    if attempts > settings.pairing_max_attempts:
        raise HTTPException(status_code=429, detail="Quá nhiều lần thử key, vui lòng thử lại sau.")

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                f"{settings.license_api_internal_url}/api/v1/license/peek",
                json={"license_key": normalized_key},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Không gọi được license-api nội bộ.") from exc
    if resp.status_code != 200 or not resp.json().get("valid"):
        raise HTTPException(status_code=401, detail="Key không hợp lệ.")

    key_hash = _hash_license_key(normalized_key)
    license_row = (
        await db.execute(select(LicenseV2).where(LicenseV2.license_key_hash == key_hash))
    ).scalar_one_or_none()
    if license_row is None:
        seat_limit = int(resp.json().get("seat_limit") or 1)
        license_row = LicenseV2(
            license_key_hash=key_hash,
            key_type="3TR-E",
            desktop_seat_limit=seat_limit,
            mobile_companion_per_desktop=settings.default_mobile_companion_per_desktop,
            mobile_companion_limit=seat_limit * settings.default_mobile_companion_per_desktop,
        )
        db.add(license_row)
        await db.flush()

    active = await count_active_companions(db, license_row.license_id)
    if active >= license_row.mobile_companion_limit:
        raise HTTPException(status_code=403, detail="Đã đạt giới hạn thiết bị companion cho key này.")

    companion = Device(
        license_id=license_row.license_id,
        device_type=device_type,
        public_key=device_public_key,
        display_name=display_name or device_type,
        parent_desktop_device_id=None,
    )
    db.add(companion)
    await db.commit()
    await db.refresh(companion)

    now = datetime.now(timezone.utc)
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
        "parent_desktop_device_id": "",
        "expires_at": expires_at,
    }
