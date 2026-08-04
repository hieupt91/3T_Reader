from __future__ import annotations

"""Client gọi transfer-gateway V2 (companion device pairing cho key doanh
nghiệp 3TR-E). Tách biệt hoàn toàn packages/license_client (V1) — chỉ dùng
lại token/device_id V1 đã có sẵn qua get_cached_credentials() để xác thực
desktop, KHÔNG đổi bất kỳ hành vi nào của license_client hiện có.

Xem SPEC_TRANSFER_GATEWAY_V2.md (docs/) để biết đầy đủ API contract.
Chỉ implement phần Phase 1 (companion pairing) — chưa có transfer-sessions
(Phase 2, truyền PDF qua WebRTC), cố tình chưa code phần đó.
"""

_CONNECT_TIMEOUT = 6
_READ_TIMEOUT = 10


class TransferNotAvailable(RuntimeError):
    """Raise khi chưa kích hoạt license V1, hoặc license không phải 3TR-E,
    hoặc transfer-gateway chưa cấu hình."""


class TransferGatewayClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def _auth_headers(self) -> dict:
        from packages.license_client import get_license_client

        client = get_license_client()
        get_creds = getattr(client, "get_cached_credentials", None)
        if get_creds is None:
            raise TransferNotAvailable("Client license hiện tại không hỗ trợ companion pairing.")
        creds = get_creds()
        if creds is None:
            raise TransferNotAvailable("Chưa kích hoạt license. Vui lòng kích hoạt key 3TR-E trước.")
        token, device_id = creds
        return {"Authorization": f"Bearer {token}", "X-Device-Id": device_id}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        import requests
        from requests.exceptions import ConnectionError, Timeout

        url = f"{self._base}{path}"
        headers = self._auth_headers()
        try:
            resp = requests.request(
                method, url, headers=headers, timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT), **kwargs
            )
        except Timeout as exc:
            raise RuntimeError("Kết nối quá chậm hoặc máy chủ không phản hồi.") from exc
        except ConnectionError as exc:
            raise RuntimeError("Không thể kết nối máy chủ. Kiểm tra kết nối internet.") from exc

        if not resp.ok:
            try:
                detail = resp.json().get("detail", f"Lỗi {resp.status_code}")
            except Exception:
                detail = f"Lỗi {resp.status_code}"
            raise RuntimeError(str(detail))
        return resp.json()

    def create_companion_session(self) -> dict:
        """Tạo mã/QR ghép nối 120s. Trả {pairing_session_id, code, qr_payload, expires_at}."""
        return self._request("POST", "/api/v2/business/companion-sessions")

    def list_devices(self) -> list[dict]:
        """Danh sách thiết bị companion (iPhone/iPad) đã ghép nối với key hiện tại."""
        return self._request("GET", "/api/v2/business/devices")

    def revoke_device(self, device_id: str) -> dict:
        """Thu hồi 1 thiết bị companion ngay lập tức."""
        return self._request("POST", f"/api/v2/devices/{device_id}/revoke")


_client: TransferGatewayClient | None = None


def get_transfer_client() -> TransferGatewayClient:
    global _client
    if _client is None:
        try:
            from app.config import TRANSFER_GATEWAY_BASE_URL  # type: ignore[import]
        except Exception:
            TRANSFER_GATEWAY_BASE_URL = ""
        if not TRANSFER_GATEWAY_BASE_URL:
            raise TransferNotAvailable("Transfer-gateway chưa được cấu hình.")
        _client = TransferGatewayClient(TRANSFER_GATEWAY_BASE_URL)
    return _client
