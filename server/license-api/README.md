# 3T Reader License API

Linux VPS backend for license, activation, heartbeat, update manifest, and
audit-oriented service hooks.

## Phase 1 scope

- License activation and validation.
- Device binding and seat limits.
- Heartbeat, revoke, and deactivate flows.
- Signed update manifest for Windows and macOS.
- Placeholder admin endpoints.

## Current implementation

- FastAPI app with a health endpoint.
- In-memory license store for development and smoke testing.
- HMAC-signed token payloads for activation and update manifests.
- API contract aligned with the Phase 1 three-stream plan.

## Files

- `app/main.py` - FastAPI entrypoint and routes.
- `app/config.py` - environment-based settings.
- `app/schemas.py` - request/response models.
- `app/services/license_service.py` - in-memory license logic.
- `app/services/token_service.py` - HMAC token and manifest signing.
- `app/services/update_service.py` - signed update manifest builder.

## Run locally

```bash
cd server/license-api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment variables

- `THREET_ENV`
- `THREET_LICENSE_SIGNING_SECRET`
- `THREET_DEFAULT_UPDATE_VERSION`
- `THREET_DEFAULT_UPDATE_URL`
- `THREET_GRACE_DAYS`

## Endpoints

- `GET /health`
- `POST /api/license/activate`
- `POST /api/license/validate`
- `POST /api/license/heartbeat`
- `POST /api/license/deactivate`
- `GET /api/update/check`
- `GET /api/releases/{platform}/{version}`
- `GET /api/admin/licenses`
- `GET /api/admin/devices`

## Notes

- This is a backend stream, not a desktop dependency.
- The first iteration uses in-memory storage only.
- Replace the in-memory store with PostgreSQL + migrations during later backend hardening.
- Add auth, audit logging, and release signing before commercial release.
