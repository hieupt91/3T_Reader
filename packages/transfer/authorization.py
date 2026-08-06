from __future__ import annotations

"""Client gọi transfer-gateway V2 (companion device pairing + transfer-sessions
cho key doanh nghiệp 3TR-E). Tách biệt hoàn toàn packages/license_client (V1)
— chỉ dùng lại token/device_id V1 đã có sẵn qua get_cached_credentials() để
xác thực desktop, KHÔNG đổi bất kỳ hành vi nào của license_client hiện có.

Xem SPEC_TRANSFER_GATEWAY_V2.md và SPEC_MOBILE_SCANDOC_TRANSFER.md (docs/)
để biết đầy đủ API contract. Phần WebRTC/DataChannel thật nằm ở protocol.py
(module này chỉ có REST — tạo/join/complete transfer-session).
"""

_CONNECT_TIMEOUT = 6
_READ_TIMEOUT = 10


class TransferNotAvailable(RuntimeError):
    """Raise khi chưa kích hoạt license V1, hoặc license không phải 3TR-E,
    hoặc transfer-gateway chưa cấu hình."""


class TransferGatewayClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def get_credentials(self) -> tuple[str, str]:
        """(token, device_id) V1 đã cache - dùng để xây header REST hoặc
        query param cho WSS signaling (mục 4.1 SPEC_MOBILE_SCANDOC_TRANSFER.md)."""
        from packages.license_client import get_license_client

        client = get_license_client()
        get_creds = getattr(client, "get_cached_credentials", None)
        if get_creds is None:
            raise TransferNotAvailable("Client license hiện tại không hỗ trợ companion pairing.")
        creds = get_creds()
        if creds is None:
            raise TransferNotAvailable("Chưa kích hoạt license. Vui lòng kích hoạt key 3TR-E trước.")
        return creds

    def _auth_headers(self, credentials: tuple[str, str] | None = None) -> dict:
        token, device_id = credentials if credentials is not None else self.get_credentials()
        headers = {"Authorization": f"Bearer {token}"}
        # Token V2 (companion, dạng body.sig.ed2.key_id) không cần X-Device-Id -
        # server tự resolve device từ chính token. Chỉ desktop token V1 cần.
        if device_id:
            headers["X-Device-Id"] = device_id
        return headers

    @property
    def base_url(self) -> str:
        return self._base

    def _request(self, method: str, path: str, *, credentials: tuple[str, str] | None = None, **kwargs) -> dict:
        import requests
        from requests.exceptions import ConnectionError, Timeout

        url = f"{self._base}{path}"
        headers = self._auth_headers(credentials)
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

    def create_transfer_session(self, file_name: str, file_size: int,
                                 *, credentials: tuple[str, str] | None = None) -> dict:
        """Bên gửi tạo phiên truyền (ticket ngắn hạn ~5 phút).
        Trả {transfer_session_id, expires_at}."""
        return self._request(
            "POST", "/api/v2/transfer-sessions",
            json={"auth_mode": "business_key", "file_name": file_name, "file_size": file_size},
            credentials=credentials,
        )

    def join_transfer_session(self, transfer_session_id: str,
                               *, credentials: tuple[str, str] | None = None) -> dict:
        """Bên nhận tham gia phiên. Trả {transfer_session_id, sender_device_id, status}.
        `credentials` cho phép truyền token V2 (companion) tường minh thay vì
        token desktop V1 mặc định - dùng khi vai NHẬN là 1 thiết bị companion
        khác thiết bị đang chạy tiến trình này (vd script test giả lập)."""
        return self._request(
            "POST", f"/api/v2/transfer-sessions/{transfer_session_id}/join",
            credentials=credentials,
        )

    def complete_transfer_session(self, transfer_session_id: str, status: str, sha256: str = "",
                                   *, credentials: tuple[str, str] | None = None) -> dict:
        """Báo hoàn tất/thất bại sau khi DataChannel đóng. status: completed|failed."""
        return self._request(
            "POST", f"/api/v2/transfer-sessions/{transfer_session_id}/complete",
            json={"status": status, "sha256": sha256},
            credentials=credentials,
        )


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
