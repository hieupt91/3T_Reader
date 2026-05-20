# Backend Client Contract

This document defines the API contract that Windows and macOS desktop clients
use to connect to the Linux VPS backend.

## Base rules

- Desktop clients must use HTTPS in production.
- Desktop clients must treat the backend as the source of truth for license and
  update decisions.
- Desktop clients must not hardcode backend secrets.
- Backend responses are versioned under `/api/v1/...` for Phase 1 stability.

## Endpoints

### Health

- `GET /health`
- `GET /api/v1/health`

### License activation

- `POST /api/license/activate`
- `POST /api/v1/license/activate`

Request fields:

- `license_key`
- `device_id`
- `platform`
- `app_version`
- `machine_name`

Response fields:

- `status`
- `message`
- `license_key`
- `device_id`
- `token`
- `expires_at`
- `grace_days`
- `seat_limit`

### License validation

- `POST /api/license/validate`
- `POST /api/v1/license/validate`

### Heartbeat

- `POST /api/license/heartbeat`
- `POST /api/v1/license/heartbeat`

### Deactivate

- `POST /api/license/deactivate`
- `POST /api/v1/license/deactivate`

### Update check

- `GET /api/update/check`
- `GET /api/v1/update/check`

### Release manifest

- `GET /api/releases/{platform}/{version}`
- `GET /api/v1/releases/{platform}/{version}`

## Data model notes

- License tokens are HMAC-signed in Phase 1 backend.
- Backend keeps an on-disk JSON state file mounted to `/data`.
- A real PostgreSQL store can replace the JSON store later without changing the
  desktop contract.

## Desktop integration rule

Windows and macOS apps should both call the same contract names and only differ
in platform-specific device ID, bundle metadata, and file paths.
