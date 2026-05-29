# VPS License Target

The Linux VPS is part of the commercial product and is already deployed as a Docker Compose backend.

## Live deployment snapshot

- Backend repo: `/home/hieupt/projects/3T_Reader/phase1-backend`
- Backend branch: `phase1-backend`
- Live container: `backend-license-api-1`
- Image: `backend-license-api`
- Runtime command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Public hostnames:
  - `reader.3tcomputer.com`
  - `license.3tcomputer.com`
- Cloudflare Tunnel routes both hostnames to `http://localhost:8000`
- The backend project mounts:
  - `../../data:/data`
  - `../../downloads:/downloads`

The public static language pack files are served from:

- `/downloads/language/vi.json`
- `/downloads/language/en.json`

## Minimum backend scope

- `POST /api/v1/license/activate`
- `POST /api/v1/license/validate`
- `POST /api/v1/license/heartbeat`
- `POST /api/v1/license/deactivate`
- `GET /api/v1/update/check?platform=mac|win&current_version=...`
- Static files under `/downloads/`
- Admin APIs for customers, licenses, devices, releases, and audit logs

## Data model

The backend uses the standard license/update data set:

- `customers`
- `products`
- `plans`
- `licenses`
- `devices`
- `activations`
- `heartbeats`
- `update_channels`
- `audit_logs`

The current live `data/` folder on the VPS contains:

- `admin-config.json`
- `license-api-state.json`
- `orders.json`

## Security baseline

- HTTPS only for public access.
- License keys are stored as hashes on the server.
- The server signs license tokens with a private key.
- The desktop app verifies signed license tokens offline with a public key.
- Offline grace period is controlled by plan policy.
- Update responses should include URL, version, platform, channel, SHA-256, and signature.
- The returned token must remain opaque to the desktop app.
- `device_id` must stay stable per machine so activate / validate / heartbeat / deactivate remain consistent.

## Client baseline

- Windows stores the license token in DPAPI / Credential Manager.
- macOS stores the license token in Keychain.
- Cache files must be signed or encrypted.
- No server secret is embedded in the desktop app.
- Keep the desktop API contract aligned across Win and Mac.

## Important correction

The old placeholder instructions that used `/opt/threet`, a `threet-api.service` unit, and `/data/downloads` do not match the live VPS.

Use the Docker Compose layout in `infra/backend/docker-compose.yml` when updating the deployment notes.
