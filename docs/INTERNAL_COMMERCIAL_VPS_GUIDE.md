# Internal Commercial Validation via VPS

This guide matches the live backend that is already running on the VPS.

## Goal

- Run the app as a commercial build, but only for internal validation.
- Check the stability of license and update traffic through the real VPS backend.
- Test activate / validate / heartbeat / update / revoke against the live service.

## Live backend layout

- Backend repo: `/home/hieupt/projects/3T_Reader/phase1-backend`
- Branch: `phase1-backend`
- Latest observed backend commit: `ccbe90c`
- Container: `backend-license-api-1`
- Image: `backend-license-api`
- Runtime command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Public hostnames:
  - `reader.3tcomputer.com`
  - `license.3tcomputer.com`
- Cloudflare Tunnel routes both hostnames to the same backend container on port `8000`

## Client side

Keep these files stable:

- `app/config.py`
- `packages/license_client/*`
- `app/license_dialog.py`

Validation steps on the client:

- Open the app and enter a real test key.
- Confirm the token cache is saved.
- Close and reopen the app to verify cached token validation.
- Disconnect the network briefly and check offline grace behavior.
- Reconnect and confirm heartbeat recovery.

## Server side

The live backend uses the repo-mounted storage:

- `/home/hieupt/projects/3T_Reader/phase1-backend/data`
- `/home/hieupt/projects/3T_Reader/phase1-backend/downloads`

The `data` directory currently contains:

- `admin-config.json`
- `license-api-state.json`
- `orders.json`

The `downloads` directory is the public static root for:

- release artifacts
- language packs
- other downloadable files

Live language pack URLs:

- `https://reader.3tcomputer.com/downloads/language/vi.json`
- `https://reader.3tcomputer.com/downloads/language/en.json`

## Stable API flow

The live logs already show successful calls to:

- `POST /api/v1/license/validate`
- `GET /api/v1/update/check?platform=windows&current_version=1.0.2`

Keep these endpoints stable:

- `POST /api/v1/license/activate`
- `POST /api/v1/license/validate`
- `POST /api/v1/license/heartbeat`
- `POST /api/v1/license/deactivate`
- `GET /api/v1/update/check?platform=mac|win&current_version=...`
- `GET /downloads/language/{code}.json`

## Important correction

Do not use the old placeholder deployment notes that mention `/opt/threet`, a `threet-api.service` unit, or `/data/downloads`.

Those paths do not match the live VPS.
