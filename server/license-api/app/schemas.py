from __future__ import annotations

from pydantic import BaseModel, Field


class ActivateRequest(BaseModel):
    license_key: str = Field(min_length=6)
    device_id: str = Field(min_length=3)
    platform: str = Field(default="unknown")
    app_version: str = Field(default="0.0.0")
    machine_name: str | None = None


class ActivateResponse(BaseModel):
    status: str
    message: str
    license_key: str
    device_id: str
    token: str
    expires_at: str
    grace_days: int
    seat_limit: int
    plan: str = "personal"


class PeekRequest(BaseModel):
    license_key: str = Field(min_length=6)


class PeekResponse(BaseModel):
    """Chỉ kiểm tra key có tồn tại/hợp lệ - KHÔNG đăng ký device, KHÔNG tiêu
    seat. Dùng cho transfer-gateway V2 xác thực key doanh nghiệp gõ trực tiếp
    trên điện thoại, trước khi có desktop nào activate key này."""
    valid: bool
    seat_limit: int | None = None
    plan: str | None = None


class ValidateRequest(BaseModel):
    token: str
    device_id: str


class ValidateResponse(BaseModel):
    valid: bool
    message: str
    license_key: str | None = None
    device_id: str | None = None
    expires_at: str | None = None
    grace_days: int | None = None
    plan: str = "free"


class HeartbeatRequest(BaseModel):
    token: str
    device_id: str


class HeartbeatResponse(BaseModel):
    ok: bool
    message: str
    plan: str = 'free'


class DeactivateRequest(BaseModel):
    token: str
    device_id: str
    reason: str | None = None


class DeactivateResponse(BaseModel):
    ok: bool
    message: str


class UpdateCheckResponse(BaseModel):
    platform: str
    current_version: str
    version: str = ""
    latest_version: str
    download_url: str
    sha256: str = ""
    portable_url: str = ""
    portable_sha256: str = ""
    mandatory: bool = False
    release_notes: str = ""
    signature: str = ""


class UpdateCheckV2Response(BaseModel):
    """B53: response route delta-update (/api/v2/update/check) - hoàn toàn
    tách biệt UpdateCheckResponse (v1) ở trên, không dùng chung field nào để
    đổi field v2 không bao giờ ảnh hưởng response v1. Xem
    docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md."""
    platform: str
    current_version: str
    current_base_version: str = ""
    latest_version: str
    update_type: str = "none"  # "full" | "delta" | "none"
    download_url: str = ""
    sha256: str = ""
    base_version: str = ""
    code_package_url: str = ""
    code_package_sha256: str = ""
    mandatory: bool = False
    release_notes: str = ""
    signature: str = ""
    code_signature: str = ""


class ReleaseManifestResponse(BaseModel):
    platform: str
    version: str
    download_url: str
    sha256: str = ""
    portable_url: str = ""
    portable_sha256: str = ""
    release_notes: str = ""
    signature: str = ""
