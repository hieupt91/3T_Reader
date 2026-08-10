from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "3T Transfer Gateway"
    api_version: str = "v2"
    environment: str = os.environ.get("TRANSFER_ENV", "production")

    database_url: str = os.environ.get(
        "TRANSFER_DATABASE_URL",
        "postgresql+asyncpg://transfer:transfer@transfer-db:5432/transfer_gateway",
    )
    redis_url: str = os.environ.get("TRANSFER_REDIS_URL", "redis://transfer-redis:6379/0")

    ed25519_private_b64: str = os.environ.get("TRANSFER_ED25519_PRIVATE", "")
    ed25519_key_id: str = os.environ.get("TRANSFER_ED25519_KEY_ID", "v2-2026-08")

    # license-api V1 nội bộ (localhost, KHÔNG public) — dùng để xác nhận desktop
    # đã activate key 3TR-E hợp lệ, tránh làm lại toàn bộ activation flow.
    license_api_internal_url: str = os.environ.get(
        "TRANSFER_LICENSE_API_INTERNAL_URL", "http://license-api:8000"
    )

    pairing_code_ttl_seconds: int = int(os.environ.get("TRANSFER_PAIRING_TTL", "120"))
    pairing_max_attempts: int = int(os.environ.get("TRANSFER_PAIRING_MAX_ATTEMPTS", "5"))
    # Mặc định 1h - người dùng có thể tự chỉnh ngắn/dài hơn qua ttl_seconds khi
    # tạo transfer session (bị kẹp [60, 86400] trong transfer_session_service).
    transfer_ticket_ttl_seconds: int = int(os.environ.get("TRANSFER_TICKET_TTL", "3600"))
    transfer_ticket_ttl_min_seconds: int = int(os.environ.get("TRANSFER_TICKET_TTL_MIN", "60"))
    transfer_ticket_ttl_max_seconds: int = int(os.environ.get("TRANSFER_TICKET_TTL_MAX", "86400"))
    # Dọn transfer_sessions hết hạn quá lâu để tránh tồn đọng mã rác vô thời hạn.
    transfer_session_retention_seconds: int = int(
        os.environ.get("TRANSFER_SESSION_RETENTION", str(24 * 3600))
    )
    default_mobile_companion_per_desktop: int = 2


settings = Settings()
