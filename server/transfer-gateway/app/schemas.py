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
    # Người dùng có thể tuỳ chỉnh thời gian sống của mã ghép nối (giây). None
    # -> dùng mặc định server (settings.transfer_ticket_ttl_seconds). Bị kẹp
    # trong [60, 86400] ở transfer_session_service để tránh mã sống quá lâu
    # thành rác hoặc quá ngắn không kịp dùng.
    ttl_seconds: int | None = None


class TransferSessionCreateResponse(BaseModel):
    transfer_session_id: str
    expires_at: datetime
    # Mã ngắn 8 ký tự (vd "PJG8-PKQC") để người dùng gõ tay thay vì UUID đầy
    # đủ - trả về plaintext ĐÚNG 1 LẦN lúc tạo (server chỉ lưu hash), giống
    # cách pairing_session trả `code`. Dùng cùng POST .../resolve để đổi
    # sang transfer_session_id thật trước khi join.
    code: str


class TransferSessionResolveRequest(BaseModel):
    code: str


class TransferSessionResolveResponse(BaseModel):
    transfer_session_id: str


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
