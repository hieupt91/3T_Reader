from __future__ import annotations

"""Lõi truyền P2P qua aiortc — chạy trong event loop asyncio riêng (KHÔNG
phải main thread Qt). Dùng non-trickle ICE (đợi gather xong rồi mới gửi
SDP qua signaling) để đơn giản hoá — không cần message ice_candidate riêng
cho bản đầu, dù server đã hỗ trợ sẵn loại message đó nếu sau này cần trickle
ICE cho kết nối nhanh hơn.

STUN dùng công khai tạm thời (xem SPEC_MOBILE_SCANDOC_TRANSFER.md mục 4.3)
— chưa có STUN service riêng của 3T.
"""

import asyncio
import time

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

from .protocol import CHUNK_SIZE, Manifest, ReceiveAssembler, iter_chunks
from .signaling_client import SignalingClient

_ICE_SERVERS = [RTCIceServer(urls="stun:stun.cloudflare.com:3478")]
_BUFFERED_AMOUNT_HIGH = 1024 * 1024  # 1 MiB — tạm dừng gửi khi vượt, chống tràn bộ nhớ đầu nhận
_ICE_GATHER_TIMEOUT = 15


class TransferError(RuntimeError):
    pass


def _make_pc() -> RTCPeerConnection:
    return RTCPeerConnection(configuration=RTCConfiguration(iceServers=_ICE_SERVERS))


async def _wait_ice_gathering_complete(pc: RTCPeerConnection) -> None:
    if pc.iceGatheringState == "complete":
        return
    done = asyncio.get_event_loop().create_future()

    @pc.on("icegatheringstatechange")
    def _on_change():
        if pc.iceGatheringState == "complete" and not done.done():
            done.set_result(None)

    try:
        await asyncio.wait_for(done, timeout=_ICE_GATHER_TIMEOUT)
    except asyncio.TimeoutError as exc:
        raise TransferError("Không thu thập được đường kết nối trực tiếp (ICE timeout).") from exc


async def send_file(
    signaling: SignalingClient,
    file_path: str,
    on_progress=None,
    on_connected=None,
) -> None:
    """Vai trò gửi: tạo offer, chờ answer, mở DataChannel, gửi manifest +
    chunk có flow-control, chờ xác nhận hoàn tất. on_connected() (không
    tham số) gọi đúng lúc DataChannel vừa mở, trước khi bắt đầu gửi dữ liệu
    - UI dùng để chuyển từ hiện mã/QR sang hiện progress bar."""
    manifest = Manifest.for_file(file_path)
    pc = _make_pc()
    channel = pc.createDataChannel("transfer", ordered=True)

    done = asyncio.get_event_loop().create_future()
    ack_received = asyncio.get_event_loop().create_future()

    @channel.on("open")
    def _on_open():
        if not done.done():
            done.set_result(None)

    @channel.on("message")
    def _on_message(message):
        if isinstance(message, str) and '"type":"ack"' in message and not ack_received.done():
            ack_received.set_result(None)

    try:
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await _wait_ice_gathering_complete(pc)

        await signaling.connect()
        await signaling.send_sdp_offer(pc.localDescription.sdp)

        # signaling_relay của server KHÔNG buffer message cho peer chưa kết
        # nối WS (chỉ forward tới socket đang mở tại đúng thời điểm gửi).
        # Bên nhận thật (người dùng quét QR bằng tay) luôn kết nối WS trễ
        # hơn bên gửi (không cần thao tác người dùng) - nếu chỉ gửi offer
        # đúng 1 lần, offer gần như chắc chắn bị rớt trước khi bên nhận kịp
        # đăng ký (đã tái hiện + xác nhận bằng test thật: chờ 12s mô phỏng
        # thời gian quét QR rồi mới kết nối bên nhận - chờ đúng 1 lần luôn
        # timeout, gửi lại định kỳ thì nhận được ngay). Gửi lại đúng SDP đã
        # tạo (không renegotiate) mỗi ~3s tới khi có answer, trong hạn 180s.
        deadline = time.monotonic() + 180
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransferError("Không có thiết bị nào tham gia trong thời gian chờ (3 phút).")
            try:
                answer_msg = await asyncio.wait_for(signaling.receive(), timeout=min(3.0, remaining))
            except asyncio.TimeoutError:
                await signaling.send_sdp_offer(pc.localDescription.sdp)
                continue
            if answer_msg.get("type") == "sdp_answer":
                break
            raise TransferError(f"Kỳ vọng sdp_answer, nhận '{answer_msg.get('type')}'.")
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_msg["sdp"], type="answer"))

        await asyncio.wait_for(done, timeout=30)  # chờ DataChannel mở
        if on_connected:
            on_connected()

        channel.send(manifest.to_json())
        sent_bytes = 0
        for raw_chunk in iter_chunks(file_path, manifest.chunk_size):
            while channel.bufferedAmount > _BUFFERED_AMOUNT_HIGH:
                await asyncio.sleep(0.05)
            channel.send(raw_chunk)
            sent_bytes += len(raw_chunk) - 4  # trừ 4 byte index
            if on_progress:
                on_progress(sent_bytes, manifest.size)

        try:
            await asyncio.wait_for(ack_received, timeout=60)
        except asyncio.TimeoutError as exc:
            raise TransferError("Không nhận được xác nhận hoàn tất từ đầu nhận.") from exc
    finally:
        await pc.close()
        await signaling.close()


async def receive_file(
    signaling: SignalingClient,
    on_progress=None,
) -> "tuple[str, bytes]":
    """Vai trò nhận: chờ offer, tạo answer, nhận manifest + chunk qua
    DataChannel, verify hash. Trả (file_name, data) — caller (UI) tự quyết
    định lưu vào đâu qua packages.transfer.inbox."""
    pc = _make_pc()
    channel_ready = asyncio.get_event_loop().create_future()
    result: dict = {}
    transfer_done = asyncio.get_event_loop().create_future()

    @pc.on("datachannel")
    def _on_datachannel(channel):
        assembler_holder: dict = {}

        @channel.on("message")
        def _on_message(message):
            if isinstance(message, str):
                manifest = Manifest.from_json(message)
                assembler_holder["assembler"] = ReceiveAssembler(manifest=manifest)
                assembler_holder["manifest"] = manifest
            else:
                assembler = assembler_holder.get("assembler")
                if assembler is None:
                    return  # chunk tới trước manifest — bỏ qua, không nên xảy ra trên ordered channel
                assembler.add_chunk(message)
                if on_progress:
                    on_progress(assembler.received_bytes, assembler_holder["manifest"].size)
                if assembler.is_complete:
                    try:
                        data = assembler.assemble_and_verify()
                        result["file_name"] = assembler_holder["manifest"].file_name
                        result["data"] = data
                        channel.send('{"type":"ack"}')
                    except ValueError as exc:
                        result["error"] = str(exc)
                    if not transfer_done.done():
                        transfer_done.set_result(None)

        if not channel_ready.done():
            channel_ready.set_result(None)

    try:
        await signaling.connect()
        offer_msg = await asyncio.wait_for(signaling.receive(), timeout=60)
        if offer_msg.get("type") != "sdp_offer":
            raise TransferError(f"Kỳ vọng sdp_offer, nhận '{offer_msg.get('type')}'.")
        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_msg["sdp"], type="offer"))

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await _wait_ice_gathering_complete(pc)
        await signaling.send_sdp_answer(pc.localDescription.sdp)

        await asyncio.wait_for(channel_ready, timeout=30)
        await asyncio.wait_for(transfer_done, timeout=600)

        if "error" in result:
            raise TransferError(result["error"])
        return result["file_name"], result["data"]
    finally:
        await pc.close()
        await signaling.close()
