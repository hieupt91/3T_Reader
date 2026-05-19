# Signing Migration

Goal: keep Vietnamese USB token signing as a B2B differentiator without shipping GPL-only signing dependencies in the main commercial build.

## Current State

- UI calls `packages.signing.get_signing_provider()`.
- `CurrentPkcs11Provider` wraps the existing `core.pkcs11` implementation.
- `core.pkcs11` now uses `python-pkcs11` for driver probing, certificate lookup, and signing sessions.
- `PyKCS11` is not in primary dependencies.

## Platform Split Later

Do not fork signing logic in Phase 0. After the split gate:

- Windows provider: scan vendor `.dll` paths in System32/SysWOW64 and configured vendor locations.
- macOS provider: scan `.dylib/.so` token middleware locations and user-configured vendor paths.
- Both providers must expose the same `SigningProvider` protocol.

## Commercial Requirements

- Do not bundle vendor token drivers.
- Document supported CA/token vendors.
- Add mock signing tests before hardware integration tests.
- Keep python-pkcs11 license notice in SBOM/NOTICE.
- Only enable PyKCS11 legacy fallback after legal review.
