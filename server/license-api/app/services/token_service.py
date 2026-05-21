from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _load_ed25519_private_key():
    """Load Ed25519 private key from env var THREET_LICENSE_ED25519_PRIVATE."""
    raw_b64 = os.environ.get("THREET_LICENSE_ED25519_PRIVATE", "")
    if not raw_b64:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        raw = base64.b64decode(raw_b64)
        return Ed25519PrivateKey.from_private_bytes(raw)
    except Exception:
        return None


@dataclass
class TokenService:
    secret: str
    _ed25519_key: object = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self._ed25519_key = _load_ed25519_private_key()

    def sign(self, payload: dict) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        body_b64 = _b64url(body)

        if self._ed25519_key is not None:
            # Ed25519 — asymmetric, client can verify offline
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            sig_bytes = self._ed25519_key.sign(body_b64.encode("ascii"))
            sig = _b64url(sig_bytes)
            pub_bytes = self._ed25519_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            alg = f"ed.{_b64url(pub_bytes)}"
            return f"{body_b64}.{sig}.{alg}"
        else:
            # HMAC-SHA256 fallback (khi chưa set env var)
            sig = hmac.new(self.secret.encode("utf-8"), body_b64.encode("ascii"), hashlib.sha256).hexdigest()
            return f"{body_b64}.{sig}"

    def verify(self, token: str) -> dict:
        parts = token.split(".")
        body_b64 = parts[0]
        sig_part = parts[1]

        if len(parts) == 4 and parts[2] == "ed":
            # Ed25519 token: body.sig.ed.pubkey
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pub_b64 = parts[3]
            pub_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64 + "=="))
            sig_bytes = _b64url_decode(sig_part)
            pub_key.verify(sig_bytes, body_b64.encode("ascii"))  # raises on bad sig
        else:
            # HMAC fallback
            expected = hmac.new(self.secret.encode("utf-8"), body_b64.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig_part, expected):
                raise ValueError("Invalid token signature")

        body = _b64url_decode(body_b64)
        return json.loads(body.decode("utf-8"))
