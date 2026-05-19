from __future__ import annotations

import sys

from .provider import SigningProvider, TokenInfo

__all__ = [
    "SigningProvider",
    "TokenInfo",
    "get_signing_provider",
]


def get_signing_provider() -> SigningProvider:
    """Return the OS-appropriate PKCS#11 signing provider."""
    if sys.platform == "darwin":
        from .macos_provider import MacOSPkcs11Provider
        return MacOSPkcs11Provider()
    # Windows and any other platform fall back to the Windows DLL detector.
    # On Linux this will find nothing, which is acceptable (VPS-only use case).
    from .windows_provider import WindowsPkcs11Provider
    return WindowsPkcs11Provider()
