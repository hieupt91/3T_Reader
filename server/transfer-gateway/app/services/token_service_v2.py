from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from ..config import settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class TokenV2Error(ValueError):
    pass


@dataclass
class TokenServiceV2:
    """Token V2 — khác hẳn V1: mang key_id thay vì raw pubkey trong token, hỗ trợ
    nhiều key tin cậy song song (phục vụ xoay key sau này mà không phá client cũ).
    """

    private_key_b64: str
    key_id: str
    _private_key: Ed25519PrivateKey | None = field(default=None, init=False, repr=False)
    _trusted_keys: dict[str, Ed25519PublicKey] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.private_key_b64:
            raw = base64.b64decode(self.private_key_b64)
            self._private_key = Ed25519PrivateKey.from_private_bytes(raw)
            self._trusted_keys[self.key_id] = self._private_key.public_key()

    def register_trusted_public_key(self, key_id: str, public_key_b64: str) -> None:
        """Thêm public key cũ vào danh sách tin cậy trong giai đoạn chuyển tiếp khi xoay key."""
        raw = base64.b64decode(public_key_b64)
        self._trusted_keys[key_id] = Ed25519PublicKey.from_public_bytes(raw)

    def sign(self, payload: dict) -> str:
        if self._private_key is None:
            raise TokenV2Error("TRANSFER_ED25519_PRIVATE chưa được cấu hình.")
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        body_b64 = _b64url(body)
        sig_bytes = self._private_key.sign(body_b64.encode("ascii"))
        sig_b64 = _b64url(sig_bytes)
        return f"{body_b64}.{sig_b64}.ed2.{self.key_id}"

    def verify(self, token: str) -> dict:
        parts = token.split(".")
        if len(parts) != 4 or parts[2] != "ed2":
            raise TokenV2Error("Token không đúng định dạng V2 (body.sig.ed2.key_id).")

        body_b64, sig_b64, _, key_id = parts
        pub_key = self._trusted_keys.get(key_id)
        if pub_key is None:
            raise TokenV2Error(f"key_id '{key_id}' không nằm trong danh sách tin cậy.")

        try:
            sig_bytes = _b64url_decode(sig_b64)
            pub_key.verify(sig_bytes, body_b64.encode("ascii"))
        except Exception as exc:  # noqa: BLE001 — mọi lỗi verify đều coi là token invalid
            raise TokenV2Error(f"Chữ ký không hợp lệ: {exc}") from exc

        payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
        expires_at = payload.get("expires_at")
        if expires_at is not None and time.time() > float(expires_at):
            raise TokenV2Error("Token đã hết hạn.")
        return payload

    def public_key_b64(self, key_id: str | None = None) -> str:
        pub = self._trusted_keys.get(key_id or self.key_id)
        if pub is None:
            raise TokenV2Error("Không có public key cho key_id yêu cầu.")
        raw = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return base64.b64encode(raw).decode("ascii")


token_service_v2 = TokenServiceV2(
    private_key_b64=settings.ed25519_private_b64,
    key_id=settings.ed25519_key_id,
)
