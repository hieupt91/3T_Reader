# PR6 VPS Requirements

Date: 2026-05-31

This file only lists VPS/API changes that matter for the hardened client in `PR6`.

## 1. Update manifest must be signed

Endpoint:

- `GET /api/v1/update/check`

Required response fields for an available update:

```json
{
  "version": "1.0.8",
  "download_url": "https://reader.3tcomputer.com/downloads/3TReader-1.0.8-win.exe",
  "sha256": "<hex sha256 of installer>",
  "signature": "<base64 ed25519 signature>",
  "release_notes": "..."
}
```

Signature contract:

- Sign the canonical JSON bytes of:

```json
{"download_url":"...","sha256":"...","version":"..."}
```

Rules:

- UTF-8 encoding
- no extra whitespace
- keys sorted alphabetically
- same as Python `json.dumps(payload, separators=(',', ':'), sort_keys=True)`

The client now rejects update install if either:

- `sha256` is missing
- `signature` is missing
- signature verification fails
- downloaded file hash does not match `sha256`

## 2. License offline grace

Current client behavior:

- if signed token payload does not contain `grace_days`, client uses a fixed offline grace of `7` days
- client no longer trusts `grace_days` from local cache for offline validation

Optional VPS improvement:

- include signed `grace_days` inside the token payload if the product needs configurable offline grace longer or shorter than 7 days

This is optional for immediate compatibility, but required if server-side grace policy must differ from 7 days offline.

## 3. Verification checklist after VPS update

1. Call `/api/v1/update/check?platform=win&current_version=1.0.7`
2. Confirm `version`, `download_url`, `sha256`, `signature` are all present
3. Recompute SHA-256 of the hosted installer and compare to `sha256`
4. Verify the signature against the embedded Ed25519 public key used by the app
5. Open the app and run manual update check
6. Confirm download completes and installer launches
