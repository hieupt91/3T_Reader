from __future__ import annotations

"""WebRTC P2P file transfer (Phase 2) cho transfer-gateway V2.

Xem docs/SPEC_MOBILE_SCANDOC_TRANSFER.md mục 3-5 cho đầy đủ contract REST +
WSS signaling + giao thức DataChannel. Tóm tắt kiến trúc:

- REST (authorization.py): tạo/join/complete transfer-session.
- WSS signaling: relay thuần JSON (sdp_offer/sdp_answer/ice_candidate/control)
  giữa đúng 2 thiết bị của phiên — server không đọc nội dung SDP/ICE.
- aiortc dựng RTCPeerConnection thật, negotiate không cần trickle ICE (aiortc
  mặc định đợi gom xong ICE candidate rồi mới trả về từ setLocalDescription(),
  candidate đã nằm sẵn trong SDP) — không cần tự gửi message ice_candidate
  riêng cho luồng cơ bản này.
- Giao thức file trên DataChannel (KHÔNG qua signaling): manifest JSON trước,
  rồi từng chunk nhị phân tối đa 64 KiB (prepend 4-byte big-endian chunk
  index), verify SHA-256 toàn file trước khi đổi tên atomic sang tên thật.

send_file_async()/receive_file_async() là 2 entry point async chính. UI
(Qt, đồng bộ) gọi qua run_async_in_thread() ở cuối file — chạy 1 event loop
asyncio riêng trong thread nền, dùng callback on_progress/on_status để báo
lại UI thread (Qt signal an toàn gọi cross-thread qua queued connection).
"""

import asyncio
import hashlib
import json
import os
import re
import struct
import threading
import time
from urllib.parse import quote

CHUNK_SIZE = 65536  # 64 KiB - đúng SPEC_MOBILE_SCANDOC_TRANSFER.md mục 5.3
BUFFERED_AMOUNT_HIGH = 1024 * 1024  # 1 MiB - spec mục 5.4 khuyến nghị tạm dừng khi vượt
PROGRESS_INTERVAL_S = 0.25
_STUN_SERVERS = ["stun:stun.l.google.com:19302", "stun:stun.cloudflare.com:3478"]


class TransferError(RuntimeError):
    """Lỗi trong quá trình truyền file (kết nối, timeout, hash sai...)."""


def _ws_url(http_base_url: str, transfer_session_id: str, token: str, device_id: str) -> str:
    ws_base = http_base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    return (
        f"{ws_base}/api/v2/transfer-sessions/{transfer_session_id}/signal"
        f"?token={quote(token, safe='')}&device_id={quote(device_id, safe='')}"
    )


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(str(name or "tai_lieu.pdf"))
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip() or "tai_lieu.pdf"
    return name[:200]


def _sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class SignalingClient:
    """Kết nối WSS tới transfer-gateway, gửi/nhận đúng JSON message theo
    4 type server chấp nhận (sdp_offer/sdp_answer/ice_candidate/control)."""

    def __init__(self, ws_url: str):
        self._ws_url = ws_url
        self._ws = None

    async def connect(self) -> None:
        import websockets

        try:
            self._ws = await websockets.connect(self._ws_url, open_timeout=10)
        except Exception as exc:
            raise TransferError(f"Không kết nối được máy chủ tín hiệu: {exc}") from exc

    async def send(self, message: dict) -> None:
        await self._ws.send(json.dumps(message))

    async def recv(self, timeout: float | None = None) -> dict:
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            raise TransferError(f"Mất kết nối máy chủ tín hiệu: {exc}") from exc
        return json.loads(raw)

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass


def _new_peer_connection():
    from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection

    config = RTCConfiguration(iceServers=[RTCIceServer(urls=u) for u in _STUN_SERVERS])
    return RTCPeerConnection(configuration=config)


async def _send_file_over_channel(channel, file_path: str, on_progress) -> str:
    file_size = os.path.getsize(file_path)
    file_hash = _sha256_of_file(file_path)
    chunk_count = max(1, (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE) if file_size else 0

    manifest = {
        "type": "manifest",
        "file_name": os.path.basename(file_path),
        "size": file_size,
        "sha256": file_hash,
        "chunk_size": CHUNK_SIZE,
        "chunk_count": chunk_count,
    }
    channel.send(json.dumps(manifest))

    sent_bytes = 0
    last_emit = 0.0
    with open(file_path, "rb") as f:
        idx = 0
        while True:
            data = f.read(CHUNK_SIZE)
            if not data:
                break
            while channel.bufferedAmount > BUFFERED_AMOUNT_HIGH:
                await asyncio.sleep(0.05)
            channel.send(struct.pack(">I", idx) + data)
            sent_bytes += len(data)
            idx += 1
            now = time.monotonic()
            if on_progress and now - last_emit > PROGRESS_INTERVAL_S:
                on_progress(sent_bytes, file_size)
                last_emit = now
    # Đợi hàng đợi SCTP gửi hết trước khi coi là xong (bufferedAmount về 0).
    while channel.bufferedAmount > 0:
        await asyncio.sleep(0.05)
    if on_progress:
        on_progress(sent_bytes, file_size)
    return file_hash


async def _receive_file_over_channel(channel, save_dir: str, on_progress) -> tuple[str, str]:
    os.makedirs(save_dir, exist_ok=True)
    state: dict = {"manifest": None, "received": 0, "fh": None, "tmp_path": None,
                   "final_path": None, "expected_idx": 0, "error": None}
    done = asyncio.Event()
    last_emit = [0.0]

    def _on_message(message):
        try:
            if isinstance(message, (bytes, bytearray)):
                if state["manifest"] is None:
                    raise TransferError("Nhận chunk nhị phân trước khi có manifest.")
                idx = struct.unpack(">I", bytes(message[:4]))[0]
                if idx != state["expected_idx"]:
                    raise TransferError(f"Chunk lệch thứ tự (mong {state['expected_idx']}, nhận {idx}).")
                state["expected_idx"] += 1
                payload = bytes(message[4:])
                state["fh"].write(payload)
                state["received"] += len(payload)
                now = time.monotonic()
                if on_progress and now - last_emit[0] > PROGRESS_INTERVAL_S:
                    on_progress(state["received"], state["manifest"]["size"])
                    last_emit[0] = now
                if state["received"] >= state["manifest"]["size"]:
                    state["fh"].close()
                    state["fh"] = None
                    if on_progress:
                        on_progress(state["received"], state["manifest"]["size"])
                    done.set()
            else:
                data = json.loads(message)
                if data.get("type") == "manifest":
                    if state["manifest"] is not None:
                        return
                    state["manifest"] = data
                    safe_name = _sanitize_filename(data.get("file_name"))
                    tmp_path = os.path.join(save_dir, safe_name + ".part")
                    state["tmp_path"] = tmp_path
                    state["final_path"] = os.path.join(save_dir, safe_name)
                    state["fh"] = open(tmp_path, "wb")
                    if int(data.get("size") or 0) == 0:
                        state["fh"].close()
                        state["fh"] = None
                        done.set()
        except Exception as exc:  # noqa: BLE001 - báo lỗi lên orchestrator, không để callback aiortc nuốt exception
            state["error"] = exc
            if state["fh"] is not None:
                try:
                    state["fh"].close()
                except Exception:
                    pass
            done.set()

    channel.on("message", _on_message)
    await done.wait()

    if state["error"] is not None:
        if state["tmp_path"] and os.path.exists(state["tmp_path"]):
            try:
                os.remove(state["tmp_path"])
            except Exception:
                pass
        raise state["error"] if isinstance(state["error"], TransferError) else TransferError(str(state["error"]))

    manifest = state["manifest"]
    if manifest is None:
        raise TransferError("Không nhận được manifest từ bên gửi.")

    actual_hash = _sha256_of_file(state["tmp_path"]) if manifest["size"] else hashlib.sha256(b"").hexdigest()
    expected_hash = manifest.get("sha256", "")
    if manifest["size"] and actual_hash != expected_hash:
        try:
            os.remove(state["tmp_path"])
        except Exception:
            pass
        raise TransferError("Nội dung nhận được không khớp SHA-256 gốc - file lỗi, thử lại.")

    os.replace(state["tmp_path"], state["final_path"])
    return state["final_path"], actual_hash


async def send_file_async(file_path: str, *, on_progress=None, on_status=None) -> dict:
    """Vai trò GỬI: tạo transfer-session, đợi bên nhận join + negotiate SDP
    (bên gửi luôn là offerer), mở DataChannel, gửi file, báo hoàn tất.
    on_status(stage, data) gọi với stage lần lượt:
    'session_created' -> {"transfer_session_id", "qr_payload"}, 'connected' -> {}."""
    from .authorization import get_transfer_client
    from aiortc import RTCSessionDescription

    if not os.path.isfile(file_path):
        raise TransferError("Không tìm thấy file để gửi.")

    client = get_transfer_client()
    token, device_id = client.get_credentials()

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    session = client.create_transfer_session(file_name, file_size)
    transfer_session_id = session["transfer_session_id"]
    qr_payload = json.dumps({"v": 1, "transfer_session_id": transfer_session_id}, ensure_ascii=False)
    if on_status:
        on_status("session_created", {"transfer_session_id": transfer_session_id, "qr_payload": qr_payload})

    signaling = SignalingClient(_ws_url(client.base_url, transfer_session_id, token, device_id))
    await signaling.connect()
    pc = _new_peer_connection()
    try:
        channel = pc.createDataChannel("transfer")
        channel_open = asyncio.Event()
        channel.on("open", lambda: channel_open.set())

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        offer_msg = {"type": "sdp_offer", "sdp": pc.localDescription.sdp}
        await signaling.send(offer_msg)

        # signaling_relay của server KHÔNG buffer message cho peer chưa kết
        # nối WS (relay() chỉ forward tới socket đang mở, không lưu lại) -
        # bên nhận (người quét QR bằng tay) luôn kết nối WS trễ hơn 1 nhịp
        # so với bên gửi (không cần thao tác người dùng). Nếu chỉ gửi offer
        # đúng 1 lần, offer gần như chắc chắn bị rớt trước khi bên nhận kịp
        # đăng ký, và receive_file_async() sẽ treo tới hết 180s dù bên nhận
        # đã kết nối đúng ngay sau đó. Gửi lại offer định kỳ (an toàn - chỉ
        # gửi lại đúng SDP đã tạo 1 lần, không tạo offer mới) tới khi có
        # answer, để bất kể bên nhận kết nối WS lúc nào trong 180s cũng
        # nhận được offer ở lần gửi lại gần nhất.
        deadline = time.monotonic() + 180
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                try:
                    msg = await signaling.recv(timeout=min(3.0, remaining))
                except asyncio.TimeoutError:
                    await signaling.send(offer_msg)
                    continue
                if msg.get("type") == "sdp_answer":
                    await pc.setRemoteDescription(RTCSessionDescription(sdp=msg["sdp"], type="answer"))
                    break
                if msg.get("type") == "control" and msg.get("error"):
                    raise TransferError(f"Lỗi tín hiệu: {msg['error']}")
        except asyncio.TimeoutError:
            raise TransferError("Không có thiết bị nào tham gia trong thời gian chờ (3 phút).")

        await asyncio.wait_for(channel_open.wait(), timeout=30)
        if on_status:
            on_status("connected", {})

        file_hash = await _send_file_over_channel(channel, file_path, on_progress)
        client.complete_transfer_session(transfer_session_id, "completed", file_hash)
        return {"transfer_session_id": transfer_session_id, "sha256": file_hash, "file_name": file_name}
    except Exception:
        try:
            client.complete_transfer_session(transfer_session_id, "failed")
        except Exception:
            pass
        raise
    finally:
        await signaling.close()
        await pc.close()


async def receive_file_async(transfer_session_id: str, save_dir: str, *, on_progress=None, on_status=None,
                              credentials: tuple[str, str] | None = None) -> dict:
    """Vai trò NHẬN: tham gia transfer-session, đợi offer từ bên gửi, trả
    lời answer (bên nhận luôn là answerer), nhận file qua DataChannel.

    `credentials` (token, device_id) mặc định None -> dùng desktop V1 hiện
    tại (get_transfer_client().get_credentials()). Chỉ truyền tường minh khi
    vai NHẬN là 1 thiết bị companion V2 khác (device_id để trống "" vì token
    V2 tự chứa danh tính, xem TransferGatewayClient._auth_headers) - dùng
    trong script test giả lập vì chưa có app ScanDoc mobile thật."""
    from .authorization import get_transfer_client
    from aiortc import RTCSessionDescription

    client = get_transfer_client()
    token, device_id = credentials if credentials is not None else client.get_credentials()

    client.join_transfer_session(transfer_session_id, credentials=credentials)

    signaling = SignalingClient(_ws_url(client.base_url, transfer_session_id, token, device_id))
    await signaling.connect()
    pc = _new_peer_connection()
    try:
        channel_ready = asyncio.Event()
        holder: dict = {}

        @pc.on("datachannel")
        def _on_datachannel(channel):
            holder["channel"] = channel
            channel_ready.set()

        try:
            msg = await signaling.recv(timeout=60)
        except asyncio.TimeoutError:
            raise TransferError("Không nhận được đề nghị kết nối từ bên gửi (hết thời gian chờ).")
        if msg.get("type") != "sdp_offer":
            raise TransferError("Dữ liệu tín hiệu không hợp lệ (thiếu sdp_offer).")
        await pc.setRemoteDescription(RTCSessionDescription(sdp=msg["sdp"], type="offer"))

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await signaling.send({"type": "sdp_answer", "sdp": pc.localDescription.sdp})

        await asyncio.wait_for(channel_ready.wait(), timeout=30)
        if on_status:
            on_status("connected", {})

        final_path, file_hash = await _receive_file_over_channel(holder["channel"], save_dir, on_progress)
        client.complete_transfer_session(transfer_session_id, "completed", file_hash, credentials=credentials)
        return {"file_path": final_path, "sha256": file_hash}
    except Exception:
        try:
            client.complete_transfer_session(transfer_session_id, "failed", credentials=credentials)
        except Exception:
            pass
        raise
    finally:
        await signaling.close()
        await pc.close()


def run_async_in_thread(coro_factory, on_done, on_error) -> threading.Thread:
    """Chạy 1 coroutine (vd send_file_async(...)) trong event loop asyncio
    riêng ở thread nền - UI thread (Qt) không bị chặn. on_done(result)/
    on_error(exc) được gọi lại TRÊN THREAD NỀN NÀY - caller tự đảm bảo
    chuyển tiếp về UI thread an toàn (vd qua Qt signal emit, không gọi
    thẳng widget từ thread khác)."""

    def _runner():
        try:
            result = asyncio.run(coro_factory())
        except Exception as exc:  # noqa: BLE001
            on_error(exc)
            return
        on_done(result)

    thread = threading.Thread(target=_runner, daemon=True, name="transfer-protocol")
    thread.start()
    return thread
