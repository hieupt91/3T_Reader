from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Device, TransferSession

# Base32 dễ đọc, bỏ ký tự dễ nhầm (0/O, 1/I/L) - ĐÚNG alphabet đã dùng cho
# mã ghép nối thiết bị (pairing_service._CODE_ALPHABET) để người dùng chỉ
# cần nhớ 1 quy ước duy nhất cho mọi loại mã trong app.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _generate_short_code() -> str:
    raw = os.urandom(8)
    chars = [_CODE_ALPHABET[b % len(_CODE_ALPHABET)] for b in raw]
    code = "".join(chars[:8])
    return f"{code[:4]}-{code[4:]}"


def _hash_short_code(code: str) -> str:
    # Không phân biệt hoa/thường, bỏ dấu gạch ngang trước khi hash - khớp
    # quy ước _hash_code() bên pairing_service.py.
    return hashlib.sha256(code.strip().upper().replace("-", "").encode("utf-8")).hexdigest()


async def _cleanup_stale_sessions(db: AsyncSession) -> None:
    """Xoá transfer_sessions hết hạn đã lâu (mã rác không ai dùng tới) - chạy
    tranh thủ mỗi lần tạo session mới, không cần scheduler/cron riêng."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.transfer_session_retention_seconds)
    await db.execute(delete(TransferSession).where(TransferSession.expires_at < cutoff))


async def create_session(
    db: AsyncSession,
    sender: Device,
    auth_mode: str,
    file_name: str,
    file_size: int,
    ttl_seconds: int | None = None,
) -> dict:
    if auth_mode != "business_key":
        # public_premium cần verify App Store Server API — chưa implement (Phase 3).
        raise HTTPException(status_code=501, detail="auth_mode 'public_premium' chưa được hỗ trợ.")

    await _cleanup_stale_sessions(db)

    effective_ttl = ttl_seconds if ttl_seconds is not None else settings.transfer_ticket_ttl_seconds
    effective_ttl = max(
        settings.transfer_ticket_ttl_min_seconds,
        min(effective_ttl, settings.transfer_ticket_ttl_max_seconds),
    )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=effective_ttl)
    manifest = {"file_name": file_name[:255], "file_size": max(0, int(file_size))} if file_name else None
    plaintext_code = _generate_short_code()

    session = TransferSession(
        sender_device_id=sender.device_id,
        code_hash=_hash_short_code(plaintext_code),
        auth_mode=auth_mode,
        file_manifest_meta=manifest,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "transfer_session_id": str(session.transfer_session_id),
        "expires_at": expires_at,
        "code": plaintext_code,
    }


async def resolve_code(db: AsyncSession, code: str) -> str:
    """Đổi mã ngắn 8 ký tự -> transfer_session_id thật, dùng trước khi join
    khi người dùng gõ tay mã thay vì quét QR (QR đã mang sẵn UUID đầy đủ,
    không cần bước này). Không kiểm tra license ở đây - việc đó join_session
    đã làm; resolve chỉ tra cứu."""
    code_hash = _hash_short_code(code)
    session = (
        await db.execute(select(TransferSession).where(TransferSession.code_hash == code_hash))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Mã không đúng hoặc đã hết hạn.")

    now = datetime.now(timezone.utc)
    if now > session.expires_at or session.status not in ("created", "signaling"):
        raise HTTPException(status_code=410, detail="Mã đã hết hạn hoặc phiên không còn nhận thiết bị mới.")

    return str(session.transfer_session_id)


async def join_session(db: AsyncSession, receiver: Device, transfer_session_id: uuid.UUID) -> dict:
    session = (
        await db.execute(
            select(TransferSession).where(TransferSession.transfer_session_id == transfer_session_id)
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên truyền.")

    now = datetime.now(timezone.utc)
    if now > session.expires_at:
        session.status = "expired"
        await db.commit()
        raise HTTPException(status_code=410, detail="Phiên truyền đã hết hạn.")

    if session.status not in ("created", "signaling"):
        raise HTTPException(status_code=410, detail="Phiên truyền không còn nhận thiết bị mới.")

    sender = (
        await db.execute(select(Device).where(Device.device_id == session.sender_device_id))
    ).scalar_one_or_none()
    if sender is None or sender.license_id != receiver.license_id:
        raise HTTPException(status_code=403, detail="Thiết bị không thuộc cùng key doanh nghiệp.")

    if session.receiver_device_id is not None and session.receiver_device_id != receiver.device_id:
        raise HTTPException(status_code=409, detail="Phiên truyền đã có thiết bị nhận khác.")

    session.receiver_device_id = receiver.device_id
    session.status = "signaling"
    await db.commit()

    return {
        "transfer_session_id": str(session.transfer_session_id),
        "sender_device_id": str(session.sender_device_id),
        "status": session.status,
    }


async def complete_session(
    db: AsyncSession, device: Device, transfer_session_id: uuid.UUID, status: str
) -> dict:
    if status not in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="status phải là completed hoặc failed.")

    session = (
        await db.execute(
            select(TransferSession).where(TransferSession.transfer_session_id == transfer_session_id)
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên truyền.")
    if device.device_id not in (session.sender_device_id, session.receiver_device_id):
        raise HTTPException(status_code=403, detail="Thiết bị không thuộc phiên truyền này.")

    session.status = status
    await db.commit()
    return {"ok": True, "status": session.status}


async def get_session_participants(db: AsyncSession, transfer_session_id: uuid.UUID) -> TransferSession | None:
    return (
        await db.execute(
            select(TransferSession).where(TransferSession.transfer_session_id == transfer_session_id)
        )
    ).scalar_one_or_none()
