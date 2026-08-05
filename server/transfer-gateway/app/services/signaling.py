from __future__ import annotations

import json
import uuid

from fastapi import WebSocket

_ALLOWED_TYPES = {"sdp_offer", "sdp_answer", "ice_candidate", "control"}
_MAX_MESSAGE_BYTES = 16 * 1024


class SignalingError(ValueError):
    pass


def validate_message(raw: str | bytes) -> dict:
    """Chỉ chấp nhận message loại sdp_offer/sdp_answer/ice_candidate/control,
    giới hạn kích thước — không bao giờ để lọt payload chứa file bytes qua
    kênh signaling này."""
    size = len(raw.encode("utf-8")) if isinstance(raw, str) else len(raw)
    if size > _MAX_MESSAGE_BYTES:
        raise SignalingError(f"Message vượt giới hạn {_MAX_MESSAGE_BYTES} bytes.")

    try:
        data = json.loads(raw)
    except Exception as exc:
        raise SignalingError("Message không phải JSON hợp lệ.") from exc

    if not isinstance(data, dict) or data.get("type") not in _ALLOWED_TYPES:
        raise SignalingError(f"type phải thuộc {sorted(_ALLOWED_TYPES)}.")

    return data


class SignalingRelay:
    """Relay thuần túy giữa 2 thiết bị trong 1 transfer_session — không lưu,
    không hiểu nội dung SDP/ICE, chỉ chuyển tiếp giữa đúng 2 participant đã
    được xác thực thuộc phiên đó."""

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, dict[uuid.UUID, WebSocket]] = {}

    async def register(self, transfer_session_id: uuid.UUID, device_id: uuid.UUID, ws: WebSocket) -> None:
        self._connections.setdefault(transfer_session_id, {})[device_id] = ws

    def unregister(self, transfer_session_id: uuid.UUID, device_id: uuid.UUID) -> None:
        peers = self._connections.get(transfer_session_id)
        if peers:
            peers.pop(device_id, None)
            if not peers:
                self._connections.pop(transfer_session_id, None)

    async def relay(self, transfer_session_id: uuid.UUID, from_device_id: uuid.UUID, message: dict) -> bool:
        peers = self._connections.get(transfer_session_id, {})
        for device_id, ws in peers.items():
            if device_id != from_device_id:
                await ws.send_json(message)
                return True
        return False


signaling_relay = SignalingRelay()
