# VPS License Target

The Linux VPS is part of the commercial product, not just a download host.

Phase 0 only prepares client and server placeholders. Real implementation starts after the clean desktop foundation is reviewed.

Minimum backend scope:

- `POST /v1/activate`
- `POST /v1/deactivate`
- `POST /v1/heartbeat`
- `GET /v1/license/status`
- `GET /v1/updates/manifest`
- Admin APIs for customers, licenses, devices, releases, and audit logs.

Minimum data model:

- `customers`
- `products`
- `plans`
- `licenses`
- `devices`
- `activations`
- `heartbeats`
- `update_channels`
- `audit_logs`

Security baseline:

- HTTPS only.
- License keys stored as hashes on the server.
- Server signs license tokens with a private key.
- Desktop app verifies signed license tokens offline with a public key.
- Offline grace period is controlled by plan policy.
- Update manifest includes URL, version, platform, channel, SHA-256, and signature.

Client baseline:

- Windows stores license token in DPAPI/Credential Manager.
- macOS stores license token in Keychain.
- Cache files must be signed or encrypted.
- No server secret is embedded in the desktop app.
