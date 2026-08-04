from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditEvent


async def record(
    db: AsyncSession,
    *,
    event_type: str,
    result: str,
    correlation_id: str,
    device_id: uuid.UUID | None = None,
) -> None:
    db.add(
        AuditEvent(
            event_type=event_type,
            result=result,
            correlation_id=correlation_id,
            device_id=device_id,
        )
    )
    await db.commit()
