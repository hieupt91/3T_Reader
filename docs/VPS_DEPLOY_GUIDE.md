# VPS Deploy Guide - 3T Reader License & Update API

This guide reflects the live backend layout verified on the VPS.

## Live Snapshot

- Backend repo path on VPS: `/home/hieupt/projects/3T_Reader/phase1-backend`
- Backend branch: `phase1-backend`
- Latest observed backend commit: `ccbe90c` (`hardening license backend deployment`)
- Container name: `backend-license-api-1`
- Container image: `backend-license-api`
- Runtime command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Compose file: `infra/backend/docker-compose.yml`
- Public endpoints via Cloudflare Tunnel:
  - `https://reader.3tcomputer.com`
  - `https://license.3tcomputer.com`
  - `ssh.dev3tcomputer.com` for SSH access
- Host Nginx is separate and serves `3tcomputer.com`, `www.3tcomputer.com`, `test.3tcomputer.com`, and other non-reader services.

## Actual storage layout

The live backend project uses local folders inside the repo:

- `/home/hieupt/projects/3T_Reader/phase1-backend/data`
- `/home/hieupt/projects/3T_Reader/phase1-backend/downloads`

The Docker Compose file mounts them as:

- `../../data:/data`
- `../../downloads:/downloads`

The current `data` directory contains:

- `admin-config.json`
- `license-api-state.json`
- `orders.json`

The `downloads` directory is the public static release root for:

- update artifacts
- language packs
- other downloadable files

Language packs are currently published at:

- `https://reader.3tcomputer.com/downloads/language/vi.json`
- `https://reader.3tcomputer.com/downloads/language/en.json`

## Backend compose file

The live backend is defined in:

`/home/hieupt/projects/3T_Reader/phase1-backend/infra/backend/docker-compose.yml`

Important env values from that file:

- `THREET_ENV=production`
- `THREET_DEFAULT_UPDATE_VERSION`
- `THREET_DEFAULT_UPDATE_URL`
- `THREET_UPDATE_URL_MAC`
- `THREET_UPDATE_URL_WIN`
- `THREET_DATA_DIR=/data`
- `THREET_STATE_FILE=license-api-state.json`
- `THREET_DOWNLOADS_DIR=/downloads`
- `THREET_PUBLIC_BASE_URL=https://reader.3tcomputer.com`

## Secret env template

Use `infra/backend/.env.example` as the template for secrets.

Do not commit the real `.env`.

The template currently includes:

- `THREET_LICENSE_SIGNING_SECRET`
- `THREET_LICENSE_ED25519_PRIVATE`
- `THREET_ADMIN_PASSWORD`
- `THREET_ADMIN_EMAIL`
- `THREET_SMTP_USER`
- `THREET_SMTP_PASS`

## Deploy flow

1. Update code in `/home/hieupt/projects/3T_Reader/phase1-backend`.
2. Update `infra/backend/.env`.
3. Place release files in `downloads/`.
4. Rebuild and restart the container.

Typical commands:

```bash
cd /home/hieupt/projects/3T_Reader/phase1-backend
git checkout phase1-backend
docker compose -f infra/backend/docker-compose.yml up -d --build
```

## Release files

When publishing a new version, place files under `downloads/` and update the compose env.

Recommended names:

- `3TReader-<version>-mac.dmg`
- `3TReader-<version>-win.exe`

Then update:

- `THREET_DEFAULT_UPDATE_VERSION`
- `THREET_DEFAULT_UPDATE_URL`
- `THREET_UPDATE_URL_MAC`
- `THREET_UPDATE_URL_WIN`

## Language packs

Language packs are served from the same backend through the public `downloads` path.

Expected URLs:

- `https://reader.3tcomputer.com/downloads/language/vi.json`
- `https://reader.3tcomputer.com/downloads/language/en.json`
- `https://license.3tcomputer.com/downloads/language/vi.json`
- `https://license.3tcomputer.com/downloads/language/en.json`

## Verification

Read-only checks that matched the live VPS:

- `docker logs backend-license-api-1`
- `curl https://reader.3tcomputer.com/api/v1/update/check?platform=windows&current_version=1.0.2`
- `curl https://license.3tcomputer.com/api/v1/license/validate`

The container logs already show successful `POST /api/v1/license/validate` and `GET /api/v1/update/check` requests from Windows clients.

## Important correction

The old placeholder layout that used `/opt/threet`, a systemd unit named `threet-api`, and `/data/downloads` is not the live deployment on this VPS.

Use the Docker Compose layout above when updating the docs or publishing releases.
