# Missing / unverified features

Date: 2026-08-15

The following remain open until real paired testing:

- Windows-to-Mac parity for every ribbon/menu/context-menu item.
- Settings persistence and complete shortcut map.
- Invalid, locked, corrupt, permission-denied, offline and interrupted workflows.
- Real USB token signing and verification with vendor middleware.
- Mac Gatekeeper/codesign/notarization behavior after installation.
- B53 delta apply, rollback and recovery. Keep `delta_enabled=false`; use full installer fallback.
- Accessibility, VoiceOver, keyboard-only navigation, resize and performance evidence.

Each item is at least `PARTIAL (P1)`; security/update apply items are `P0` where they can invalidate the install.
