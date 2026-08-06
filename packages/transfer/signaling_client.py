from __future__ import annotations

"""WSS client nối tới transfer-gateway /signal — chỉ gửi/nhận 4 loại message
(sdp_offer, sdp_answer, ice_candidate, control) theo đúng
SPEC_MOBILE_SCANDOC_TRANSFER.md mục 4. Không hiểu nội dung SDP/ICE, chỉ
làm nhiệm vụ giao vận qua WSS.
"""

import json


class SignalingError(RuntimeError):
    pass


class SignalingClient:
    """Bọc quanh `websockets` — dùng trong asyncio event loop riêng của
    webrtc_transport.py (KHÔNG gọi trực tiếp từ Qt main thread)."""

    def __init__(self, base_url: str, transfer_session_id: str, device_token: str, v1_device_id: str = "") -> None:
        scheme = "wss" if base_url.startswith("https") else "ws"
        host = base_url.split("://", 1)[1].rstrip("/")
        url = f"{scheme}://{host}/api/v2/transfer-sessions/{transfer_session_id}/signal?token={device_token}"
        if v1_device_id:
            url += f"&device_id={v1_device_id}"
        self._url = url
        self._ws = None

    async def connect(self) -> None:
        import websockets

        try:
            self._ws = await websockets.connect(self._url, open_timeout=10)
        except Exception as exc:  # noqa: BLE001
            raise SignalingError(f"Không kết nối được signaling: {exc}") from exc

    async def send_sdp_offer(self, sdp: str) -> None:
        await self._send({"type": "sdp_offer", "sdp": sdp})

    async def send_sdp_answer(self, sdp: str) -> None:
        await self._send({"type": "sdp_answer", "sdp": sdp})

    async def send_ice_candidate(self, candidate: str, sdp_mline_index: int, sdp_mid: str) -> None:
        await self._send(
            {
                "type": "ice_candidate",
                "candidate": candidate,
                "sdpMLineIndex": sdp_mline_index,
                "sdpMid": sdp_mid,
            }
        )

    async def send_control(self, action: str) -> None:
        await self._send({"type": "control", "action": action})

    async def _send(self, message: dict) -> None:
        if self._ws is None:
            raise SignalingError("Chưa kết nối signaling.")
        await self._ws.send(json.dumps(message, separators=(",", ":")))

    async def receive(self) -> dict:
        if self._ws is None:
            raise SignalingError("Chưa kết nối signaling.")
        raw = await self._ws.recv()
        data = json.loads(raw)
        if "error" in data:
            raise SignalingError(str(data["error"]))
        return data

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
