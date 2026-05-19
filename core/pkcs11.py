"""
Backward-compat shim for core.pkcs11.

Phase 0: signing logic has moved to packages/signing/.
- OS-specific driver detection → packages/signing/windows_provider.py (Windows)
                               → packages/signing/macos_provider.py (macOS)
- Shared cert/stamp utilities  → packages/signing/shared.py
- Font resolution              → packages/platform/fonts.py

This module re-exports the utilities that are still referenced externally,
so existing call-sites continue to work without changes.
"""
from __future__ import annotations

from packages.signing.shared import (
    _extract_tax_code_from_text,
    _safe_get_pkcs11_attr,
    build_vietnamese_stamp_style as _build_vietnamese_stamp_style,
    extract_signer_identity_from_der as _extract_signer_identity_from_der,
    strip_accents as _strip_accents,
)


def get_last_pkcs11_error() -> str:
    """Return the last driver-detection error from the active signing provider."""
    from packages.signing import get_signing_provider

    provider = get_signing_provider()
    return provider.get_last_error()
