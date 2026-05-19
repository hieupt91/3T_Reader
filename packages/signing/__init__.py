from .current_pkcs11_provider import CurrentPkcs11Provider
from .provider import SigningProvider, TokenInfo

_current_provider = CurrentPkcs11Provider()


def get_signing_provider() -> SigningProvider:
    return _current_provider


__all__ = [
    "CurrentPkcs11Provider",
    "SigningProvider",
    "TokenInfo",
    "get_signing_provider",
]
