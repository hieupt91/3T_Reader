from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .config import settings
from .schemas import (
    ActivateRequest,
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    ReleaseManifestResponse,
    UpdateCheckResponse,
    ValidateRequest,
    ValidateResponse,
)
from .services.license_service import LicenseService
from .services.token_service import TokenService
from .services.update_service import UpdateService


token_service = TokenService(settings.signing_secret)
license_service = LicenseService(token_service)
update_service = UpdateService(token_service)

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.post("/api/license/activate", response_model=ActivateResponse)
def activate(req: ActivateRequest) -> ActivateResponse:
    result = license_service.activate(
        req.license_key,
        req.device_id,
        req.platform,
        req.app_version,
        req.machine_name,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return ActivateResponse(
        status="ok",
        message=result["message"],
        license_key=result["license_key"],
        device_id=result["device_id"],
        token=result["token"],
        expires_at=result["expires_at"],
        grace_days=settings.grace_days,
        seat_limit=result["seat_limit"],
    )


@app.post("/api/license/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest) -> ValidateResponse:
    result = license_service.validate(req.token, req.device_id)
    return ValidateResponse(
        valid=bool(result["ok"]),
        message=result["message"],
        license_key=result.get("license_key"),
        device_id=result.get("device_id"),
        expires_at=result.get("expires_at"),
        grace_days=settings.grace_days if result["ok"] else None,
    )


@app.post("/api/license/heartbeat", response_model=HeartbeatResponse)
def heartbeat(req: HeartbeatRequest) -> HeartbeatResponse:
    result = license_service.heartbeat(req.token, req.device_id)
    return HeartbeatResponse(ok=bool(result["ok"]), message=result["message"])


@app.post("/api/license/deactivate", response_model=DeactivateResponse)
def deactivate(req: DeactivateRequest) -> DeactivateResponse:
    result = license_service.deactivate(req.token, req.device_id)
    return DeactivateResponse(ok=bool(result["ok"]), message=result["message"])


@app.get("/api/update/check", response_model=UpdateCheckResponse)
def update_check(platform: str, current_version: str) -> UpdateCheckResponse:
    manifest = update_service.build_manifest(platform, current_version)
    return UpdateCheckResponse(
        platform=manifest["platform"],
        current_version=manifest["current_version"],
        latest_version=manifest["latest_version"],
        download_url=manifest["download_url"],
        sha256=manifest["sha256"],
        mandatory=manifest["mandatory"],
        release_notes=manifest["release_notes"],
    )


@app.get("/api/releases/{platform}/{version}", response_model=ReleaseManifestResponse)
def release_manifest(platform: str, version: str) -> ReleaseManifestResponse:
    manifest = update_service.build_manifest(platform, version)
    return ReleaseManifestResponse(
        platform=manifest["platform"],
        version=manifest["latest_version"],
        download_url=manifest["download_url"],
        sha256=manifest["sha256"],
        release_notes=manifest["release_notes"],
        signature=manifest["signature"],
    )


@app.get("/api/admin/licenses")
def admin_licenses() -> dict:
    return {
        "items": [
            {
                "license_key": record.license_key,
                "customer_name": record.customer_name,
                "seat_limit": record.seat_limit,
                "active_devices": len(record.active_devices),
            }
            for record in license_service.licenses.values()
        ]
    }


@app.get("/api/admin/devices")
def admin_devices() -> dict:
    devices = []
    for record in license_service.licenses.values():
        for device_id, payload in record.active_devices.items():
            devices.append(
                {
                    "license_key": record.license_key,
                    "device_id": device_id,
                    "platform": payload.get("platform", ""),
                    "app_version": payload.get("app_version", ""),
                }
            )
    return {"items": devices}
