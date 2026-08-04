from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CompanionSessionCreateResponse(BaseModel):
    pairing_session_id: str
    code: str
    qr_payload: str
    expires_at: datetime


class CompanionSessionClaimRequest(BaseModel):
    code: str
    device_public_key: str
    device_type: str  # iphone | ipad
    display_name: str = ""


class CompanionSessionClaimResponse(BaseModel):
    device_token: str
    parent_desktop_device_id: str
    expires_at: datetime


class DeviceRevokeResponse(BaseModel):
    ok: bool
    device_id: str
    revoked_at: datetime


class DeviceListItem(BaseModel):
    device_id: str
    device_type: str
    display_name: str = ""
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None


class ErrorResponse(BaseModel):
    detail: str
