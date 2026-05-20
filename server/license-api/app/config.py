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
    data_dir: str = os.getenv("THREET_DATA_DIR", "/data")
    state_file: str = os.getenv("THREET_STATE_FILE", "license-api-state.json")
    api_version: str = "v1"


settings = Settings()
