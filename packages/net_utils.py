"""Tien ich mang dung chung - SSL context an toan voi fallback."""

import ssl
import logging
import urllib.request

_log = logging.getLogger(__name__)


def make_ssl_context(*, allow_fallback: bool = True) -> ssl.SSLContext:
    """Tao SSL context an toan. Fallback sang unverified neu may thieu CA certs."""
    try:
        ctx = ssl.create_default_context()
        return ctx
    except ssl.SSLError:
        if allow_fallback:
            _log.warning(
                "SSL certificate verification failed - falling back to unverified. "
                "This may indicate missing CA certificates on this system."
            )
            return ssl._create_unverified_context()
        raise


def build_opener(*, timeout: int = 30) -> urllib.request.OpenerDirector:
    """Tao opener voi SSL an toan va bo proxy."""
    ctx = make_ssl_context()
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.ProxyHandler({}),
    )
