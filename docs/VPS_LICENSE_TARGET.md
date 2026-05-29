# VPS License Target

The Linux VPS is part of the commercial product, not just a download host.

Phase 0 only prepares client and server placeholders. Real implementation starts after the clean desktop foundation is reviewed.

Minimum backend scope:

- `POST /api/v1/license/activate`
- `POST /api/v1/license/validate`
- `POST /api/v1/license/heartbeat`
- `POST /api/v1/license/deactivate`
- `GET /api/v1/update/check?platform=mac|win&current_version=...`
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
- Update response includes URL, version, platform, channel, SHA-256, and signature.
- The returned token is opaque to the desktop app; Win/Mac should store/cache it without parsing internal fields.
- `device_id` must stay stable per machine so activate/validate/heartbeat/deactivate stay consistent.

Client baseline:

- Windows stores license token in DPAPI/Credential Manager.
- macOS stores license token in Keychain.
- Cache files must be signed or encrypted.
- No server secret is embedded in the desktop app.
- Keep the desktop API contract aligned across Win and Mac.
