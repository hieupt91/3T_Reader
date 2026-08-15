from __future__ import annotations

import sys

from .provider import SigningProvider, TokenInfo

__all__ = [
    "SigningProvider",
    "TokenInfo",
    "get_signing_provider",
]

_provider: SigningProvider | None = None


def get_signing_provider() -> SigningProvider:
    """Return the OS-appropriate PKCS#11 signing provider."""
    global _provider
    if _provider is not None:
        return _provider
    if sys.platform == "darwin":
        from .macos_provider import MacOSPkcs11Provider
        _provider = MacOSPkcs11Provider()
        return _provider
    # Windows and any other platform fall back to the Windows DLL detector.
    # On Linux this will find nothing, which is acceptable (VPS-only use case).
    from .windows_provider import WindowsPkcs11Provider
    _provider = WindowsPkcs11Provider()
    return _provider
