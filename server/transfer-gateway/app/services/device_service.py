from __future__ import annotations

import hashlib
import uuid

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Device, LicenseV2


def _hash_license_key(license_key: str) -> str:
    return hashlib.sha256(license_key.strip().upper().encode("utf-8")).hexdigest()


async def resolve_desktop_device(db: AsyncSession, v1_token: str, v1_device_id: str) -> Device:
    """Cầu nối V1 -> V2: xác nhận desktop đã activate key 3TR-E hợp lệ qua
    license-api V1 nội bộ (KHÔNG public), rồi tìm/tạo Device+LicenseV2 tương ứng
    bên phía transfer-gateway. Không làm lại toàn bộ activation flow của V1.

    Giới hạn MVP: desktop chưa có device keypair X25519/Ed25519 riêng (phần đó
    thuộc `packages/transfer/` phía 3TReader client, chưa triển khai — mục 5.2
    trong SPEC_TRANSFER_GATEWAY_V2.md). Dùng device_id fingerprint V1 làm khóa
    tra cứu idempotent tạm thời qua display_name, đánh dấu rõ để thay khi có
    device keypair thật.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                f"{settings.license_api_internal_url}/api/v1/license/validate",
                json={"token": v1_token, "device_id": v1_device_id},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Không gọi được license-api nội bộ.") from exc

    if resp.status_code != 200 or not resp.json().get("valid"):
        raise HTTPException(status_code=401, detail="Token license V1 không hợp lệ.")

    license_key = resp.json().get("license_key") or ""
    if not license_key.upper().startswith("3TR-E"):
        raise HTTPException(status_code=403, detail="Transfer-gateway V2 chỉ hỗ trợ key doanh nghiệp 3TR-E.")

    key_hash = _hash_license_key(license_key)
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

    device_row = (
        await db.execute(
            select(Device).where(
                Device.license_id == license_row.license_id,
                Device.device_type == "desktop",
                Device.display_name == v1_device_id,
            )
        )
    ).scalar_one_or_none()
    if device_row is None:
        device_row = Device(
            license_id=license_row.license_id,
            device_type="desktop",
            public_key=f"v1-bridge:{v1_device_id}",
            display_name=v1_device_id,
        )
        db.add(device_row)
        await db.flush()

    if device_row.revoked_at is not None:
        raise HTTPException(status_code=403, detail="Thiết bị desktop này đã bị thu hồi.")

    await db.commit()
    return device_row


async def count_active_companions(db: AsyncSession, license_id: uuid.UUID) -> int:
    rows = (
        await db.execute(
            select(Device).where(
                Device.license_id == license_id,
                Device.device_type.in_(["iphone", "ipad"]),
                Device.revoked_at.is_(None),
            )
        )
    ).scalars().all()
    return len(rows)


async def get_device(db: AsyncSession, device_id: uuid.UUID) -> Device | None:
    return (
        await db.execute(select(Device).where(Device.device_id == device_id))
    ).scalar_one_or_none()


async def resolve_companion_device(db: AsyncSession, v2_token: str) -> Device:
    """Xác thực device_token V2 (companion iPhone/iPad đã claim ở pairing) và
    trả về Device tương ứng. Khác resolve_desktop_device (cầu nối V1) — đây
    xác thực trực tiếp bằng token V2 tự ký, không cần gọi license-api."""
    from .token_service_v2 import TokenV2Error, token_service_v2

    try:
        payload = token_service_v2.verify(v2_token)
    except TokenV2Error as exc:
        raise HTTPException(status_code=401, detail=f"Token V2 không hợp lệ: {exc}") from exc

    device_id = payload.get("device_id")
    if not device_id:
        raise HTTPException(status_code=401, detail="Token V2 thiếu device_id.")

    device_row = await get_device(db, uuid.UUID(device_id))
    if device_row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị.")
    if device_row.revoked_at is not None:
        raise HTTPException(status_code=403, detail="Thiết bị đã bị thu hồi.")
    return device_row
