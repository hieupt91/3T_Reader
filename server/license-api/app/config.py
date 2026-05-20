from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "3T Reader License API"
    environment: str = os.getenv("THREET_ENV", "development")
    signing_secret: str = os.getenv("THREET_LICENSE_SIGNING_SECRET", "dev-secret-change-me")
    default_update_version: str = os.getenv("THREET_DEFAULT_UPDATE_VERSION", "0.0.0")
    default_update_url: str = os.getenv("THREET_DEFAULT_UPDATE_URL", "")
    grace_days: int = int(os.getenv("THREET_GRACE_DAYS", "3"))


settings = Settings()
