from __future__ import annotations

"""Lõi truyền P2P qua aiortc — chạy trong event loop asyncio riêng (KHÔNG
phải main thread Qt). Dùng non-trickle ICE (đợi gather xong rồi mới gửi
SDP qua signaling) để đơn giản hoá — không cần message ice_candidate riêng
cho bản đầu, dù server đã hỗ trợ sẵn loại message đó nếu sau này cần trickle
ICE cho kết nối nhanh hơn.

STUN dùng công khai tạm thời (xem SPEC_MOBILE_SCANDOC_TRANSFER.md mục 4.3)
— chưa có STUN service riêng của 3T.

Thêm 11/08/2026: TURN relay (coturn, container `coturn-3treader` trên máy
chủ 116.97.215.211, cấu hình tại `/home/hieupt/coturn/turnserver.conf`) -
STUN thôi không đủ khi 1 trong 2 bên bị chặn kết nối đến trực tiếp (vd
Windows Firewall coi WiFi là "Public network" - đã tái hiện + xác nhận bằng
test thật). TURN chỉ cần app gọi RA (luôn được phép), không cần ai gọi VÀO
máy, nên tránh được vấn đề này hoàn toàn. Dùng credential tĩnh (long-term,
không phải REST API ephemeral) - đơn giản, chấp nhận được vì token có thể
bị trích xuất từ app cũng chỉ dùng được để relay qua chính server 3T, không
lộ dữ liệu người dùng nào. Lưu ý: TURN mới mở port ở firewall NGAY TRÊN máy
chủ - máy chủ này còn nằm sau NAT của router (dùng chung IP public với máy
dev), nên user THẬT ở mạng khác chỉ dùng được sau khi ai đó port-forward
UDP/TCP 3478 + dải 49160-49200 trên router trỏ về 192.168.1.254 (việc này
không làm được qua SSH, cần vào trang quản trị router).
"""

import asyncio
import json
import time

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

from .protocol import CHUNK_SIZE, Manifest, ReceiveAssembler, iter_chunks
from .signaling_client import SignalingClient

_ICE_SERVERS = [
    RTCIceServer(urls="stun:stun.cloudflare.com:3478"),
    # 2 URL trỏ CÙNG 1 server TURN (coturn-3treader, xem comment ở đầu
    # file) - IP public (116.97.215.211) cho user ở mạng khác, và IP LAN
    # nội bộ (192.168.1.254) riêng cho trường hợp máy đang test/dùng CÙNG
    # mạng vật lý với server đó (gửi thẳng ra IP public khi đứng trong
    # chính mạng đó bị NAT hairpin của router chặn - đã tái hiện + xác
    # nhận). Đã test thật thành công 11/08/2026: ICE/DTLS/SCTP kết nối đầy
    # đủ qua đường LAN + firewall rule cho phép inbound tới python.exe.
    RTCIceServer(
        urls="turn:116.97.215.211:3478",
        username="3treader",
        credential="E0CRYgMm6InFRWCcnlGHqAJc9u6aoOsC",
    ),
    RTCIceServer(
        urls="turn:192.168.1.254:3478",
        username="3treader",
        credential="E0CRYgMm6InFRWCcnlGHqAJc9u6aoOsC",
    ),
]
_BUFFERED_AMOUNT_HIGH = 1024 * 1024  # 1 MiB — tạm dừng gửi khi vượt, chống tràn bộ nhớ đầu nhận
_ICE_GATHER_TIMEOUT = 45  # đủ chờ 1 trong nhiều candidate source hết retry (~40s theo RFC 5389) nếu 1 nguồn bị chặn


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
    *,
    channel_open_timeout: float = 30,
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

        try:
            await asyncio.wait_for(done, timeout=channel_open_timeout)  # chờ DataChannel mở
        except asyncio.TimeoutError as exc:
            # asyncio.TimeoutError không có message (str(exc) == "") - nếu
            # không bắt riêng ở đây, người dùng thấy lỗi TRẮNG KHÔNG CHỮ (đã
            # xác nhận: str(asyncio.TimeoutError()) == ''). Xảy ra thật khi
            # SDP/ICE trao đổi xong (đã qua bước gửi/nhận answer ở trên) nhưng
            # kết nối P2P thật sự không thiết lập được (TURN không tới được -
            # đúng lỗ hổng hạ tầng đã biết: TURN server đứng sau NAT router,
            # user ngoài mạng văn phòng chưa chắc dùng được).
            raise TransferError(
                "Không thiết lập được kết nối trực tiếp với thiết bị (có thể do "
                "tường lửa/mạng chặn). Hãy thử lại khi 2 thiết bị cùng WiFi, "
                "hoặc kiểm tra kết nối mạng."
            ) from exc
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
    *,
    offer_timeout: float = 60,
    channel_open_timeout: float = 30,
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
        try:
            offer_msg = await asyncio.wait_for(signaling.receive(), timeout=offer_timeout)
        except asyncio.TimeoutError as exc:
            raise TransferError(
                "Không có thiết bị nào quét mã trong thời gian chờ."
            ) from exc
        if offer_msg.get("type") != "sdp_offer":
            raise TransferError(f"Kỳ vọng sdp_offer, nhận '{offer_msg.get('type')}'.")
        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_msg["sdp"], type="offer"))

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await _wait_ice_gathering_complete(pc)
        await signaling.send_sdp_answer(pc.localDescription.sdp)

        try:
            await asyncio.wait_for(channel_ready, timeout=channel_open_timeout)
        except asyncio.TimeoutError as exc:
            # Cùng vấn đề như send_file(): asyncio.TimeoutError không có
            # message, phải bắt riêng để không hiện lỗi trắng không chữ.
            raise TransferError(
                "Không thiết lập được kết nối trực tiếp với thiết bị (có thể do "
                "tường lửa/mạng chặn). Hãy thử lại khi 2 thiết bị cùng WiFi, "
                "hoặc kiểm tra kết nối mạng."
            ) from exc
        try:
            await asyncio.wait_for(transfer_done, timeout=600)
        except asyncio.TimeoutError as exc:
            raise TransferError(
                "Quá thời gian chờ nhận dữ liệu - kết nối có thể đã bị gián đoạn "
                "giữa chừng. Hãy thử lại."
            ) from exc

        if "error" in result:
            raise TransferError(result["error"])
        return result["file_name"], result["data"]
    finally:
        await pc.close()
        await signaling.close()


# ── Đảo vai trò tạo phiên (xem docs/PLAN_2026-08-11_reverse_qr_send_flow.md,
# nhánh phase1-backend) ────────────────────────────────────────────────────
#
# send_file()/receive_file() ở trên gắn cứng "ai tạo phiên" với "vai WebRTC +
# chiều byte" thành đúng 2 tổ hợp: tạo phiên+offerer+đẩy file (send_file),
# hoặc join+answerer+nhận file (receive_file). Luồng mới (3TReader tự tạo
# phiên + hiện QR NHƯNG VẪN NHẬN bytes; ScanDoc quét QR + join NHƯNG VẪN GỬI
# bytes) cần tách "ai tạo phiên" ra khỏi "vai WebRTC" - 2 hàm dưới đây chỉ
# thêm bước REST tạo/join phiên rồi gọi lại NGUYÊN VẸN send_file()/
# receive_file() ở trên (không sửa, không viết lại logic WebRTC) cho đúng
# vai trò ngược lại.


async def host_receive_file_async(*, on_progress=None, on_status=None) -> "tuple[str, bytes]":
    """Vai TẠO PHIÊN (hiện QR) nhưng vẫn NHẬN bytes - dùng cho dialog "Nhận
    tài liệu" mở lên là tự tạo phiên ngay, không cần dán mã. on_status(stage,
    data) gọi với stage="created" ngay sau khi có transfer_session_id, data
    chứa {"transfer_session_id", "qr_payload"} để UI hiện QR trước khi vào
    receive_file() (vốn có thể block khá lâu chờ offer). Trả (file_name,
    data) giống hệt receive_file() - caller tự lưu inbox + complete session,
    không đổi convention hiện có ở transfer_receive_dialog.py."""
    from .authorization import get_transfer_client

    client = get_transfer_client()
    token, device_id = client.get_credentials()

    session = client.create_transfer_session("", 0)
    transfer_session_id = session["transfer_session_id"]
    # Cập nhật 11/08/2026: create_transfer_session giờ trả thêm "code" (mã
    # ngắn 8 ký tự, vd "7SH6-FHU2") cho người dùng gõ tay thay vì quét QR.
    # qr_payload vẫn tự dựng - server không trả field này cho transfer-session
    # (khác companion-session).
    qr_payload = json.dumps({"v": 1, "transfer_session_id": transfer_session_id})

    if on_status:
        on_status("created", {
            "transfer_session_id": transfer_session_id,
            "qr_payload": qr_payload,
            "code": session.get("code", ""),
            "expires_at": session.get("expires_at", ""),
        })

    signaling = SignalingClient(client.base_url, transfer_session_id, token, device_id)
    # offer_timeout dài hơn mặc định (180s thay vì 60s) vì giờ cần thời gian
    # cho người dùng thật cầm điện thoại quét QR/gõ mã, không phải 2 tiến
    # trình tự động nối nhau ngay như trước khi đảo vai.
    return await receive_file(signaling, on_progress=on_progress, offer_timeout=180)


async def guest_send_file_async(
    transfer_session_id: str,
    file_path: str,
    *,
    credentials: "tuple[str, str] | None" = None,
    on_progress=None,
    on_connected=None,
    on_status=None,
) -> None:
    """Vai THAM GIA phiên đã có (dán mã ScanDoc hiện ra) nhưng vẫn GỬI bytes -
    đảo ngược send_file() (vốn tự tạo phiên). Dùng thật cho
    transfer_send_dialog.py (desktop là bên gửi, dán mã do ScanDoc "Nhận tài
    liệu" tạo ra) và cho script test tự động xác minh giao thức đảo vai.
    `credentials` cho phép truyền token thiết bị khác (giả lập 2 thiết bị
    trong test) thay vì mặc định dùng credentials của máy đang chạy.
    on_status("joined", {}) gọi ngay sau khi join_transfer_session REST
    thành công - để UI không báo "đã tham gia" trước khi thực sự đúng
    (mã sai/hết hạn thì join raise lỗi, không gọi callback này)."""
    from .authorization import get_transfer_client

    client = get_transfer_client()
    token, device_id = credentials if credentials is not None else client.get_credentials()
    client.join_transfer_session(transfer_session_id, credentials=credentials)
    if on_status:
        on_status("joined", {})

    signaling = SignalingClient(client.base_url, transfer_session_id, token, device_id)
    await send_file(signaling, file_path, on_progress=on_progress, on_connected=on_connected)
