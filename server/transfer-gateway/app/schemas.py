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


class CompanionClaimByKeyRequest(BaseModel):
    license_key: str
    device_public_key: str
    device_type: str  # iphone | ipad
    display_name: str = ""


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


class TransferSessionCreateRequest(BaseModel):
    auth_mode: str = "business_key"  # business_key | public_premium (public_premium chưa implement)
    file_name: str = ""
    file_size: int = 0


class TransferSessionCreateResponse(BaseModel):
    transfer_session_id: str
    expires_at: datetime


class TransferSessionJoinRequest(BaseModel):
    pass


class TransferSessionJoinResponse(BaseModel):
    transfer_session_id: str
    sender_device_id: str
    status: str


class TransferSessionCompleteRequest(BaseModel):
    status: str  # completed | failed
    sha256: str = ""


class TransferSessionCompleteResponse(BaseModel):
    ok: bool
    status: str
