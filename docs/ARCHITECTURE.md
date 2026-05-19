# Target Architecture

The product direction is one platform with three delivery areas:

- Windows desktop app.
- macOS desktop app.
- Linux VPS backend.

The desktop apps must share UI/UX, workflow, and business logic. OS differences belong behind adapters.

Phase 0 keeps the current source mostly in place while preparing these boundaries:

- `app/`: existing desktop UI and action handlers.
- `core/`: existing PDF/signing/recent logic that will be migrated gradually.
- `packages/platform/`: OS-specific paths and single-instance behavior.
- `packages/pdf_engine/`: future replaceable PDF engine boundary.
- `packages/signing/`: future Windows/macOS PKCS#11 providers.
- `packages/license_client/`: future VPS license client.
- `packages/update_client/`: future signed VPS update client.
- `server/license-api/`: future Linux VPS backend.

Do not create divergent Windows and macOS app logic until shared modules are extracted.
