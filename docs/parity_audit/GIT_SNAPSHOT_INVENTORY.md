# Git snapshot inventory for Mac 1.0.32 port

Date: 2026-08-15  
Integration branch: `phase1-mac-1.0.32-port`  
Integration commit: `6345f60`

## Desktop/application refs included

The following refs are ancestors of the integration branch and therefore have
already been included in the application history:

- `origin/main`
- `origin/phase1-shared`
- `origin/piper-vps-sync`
- `origin/fix-mac-license-bypass`
- `origin/mac-edit-rotate-2026-07`
- `phase1-win-1.0.32` and its tag
- `phase0-closed`, `phase1-start`, `phase1-complete`, `phase1-win-checkpoint-1`,
  `mac-checkpoint-1`, `mac-checkpoint-2`

The Windows 1.0.32 source snapshot was merged with Mac-side conflict policy,
then smoke-tested and built as `.app/.dmg`.

## Backend refs intentionally excluded from the desktop tree

`origin/phase1-backend` and `origin/fix-vps-security` contain VPS
license-api/transfer-gateway, deployment scripts, admin pages and server-only
configuration. Their server commits are not desktop application features and
must be deployed/reviewed in the backend repository/branch separately.

The desktop client already contains the corresponding transfer protocol/UI
from `piper-vps-sync`, including QR, 8-character transfer codes, reverse send/
receive flow, TURN configuration and timeout/error handling. Backend endpoint
changes must be coordinated with the VPS owner before release.

## Excluded data and artifacts

The integration intentionally excludes hồ sơ pháp lý, PDF/XLSX/DOCX test data,
CCCD/PII, generated debug images, upload/deploy scratch scripts, backend
secrets and local Piper runtime directories. These are not application source
and must not be pushed to the desktop branch.

## Verification record

- Smoke tests: `30 passed, 5 skipped` on macOS.
- `.app` build: passed.
- `.dmg` build: passed.
- Runtime launch: passed.
- Windows-only provider tests are skipped on macOS and must run on Windows.
- Full UI/workflow parity is still open until the paired fixture matrix is
  exercised manually.
