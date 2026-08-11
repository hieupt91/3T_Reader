# Spec triển khai chi tiết: đảo chiều luồng gửi/nhận phía Desktop 3TReader

Dành cho team Windows/Mac (dùng chung 1 codebase Python/PySide6) - bổ sung
chi tiết implementation cho Phase 1, 2, 7 trong
`docs/PLAN_2026-08-11_reverse_qr_send_flow.md`. Phía ScanDoc (iOS) đã xong
100% và đã lên TestFlight (commit `f4f4bd5`, repo `scandocapp-business`) -
tài liệu này CHỈ còn thiếu phần desktop để chạy được end-to-end.

**Nguyên tắc cốt lõi** (đã chốt với người dùng): bên NHẬN luôn tạo phiên +
hiện mã, bên GỬI luôn kết nối tới bằng mã đó.

**Format QR/mã đã chốt, KHÔNG được đổi** (ScanDoc đã code cứng theo format
này): `{"v":1,"transfer_session_id":"<uuid>"}` - JSON, field
`transfer_session_id` bắt buộc, các field khác nếu thêm sẽ bị ScanDoc bỏ
qua (không lỗi) nhưng đừng đổi tên field có sẵn.

---

## Phần 1: `packages/transfer/protocol.py` - 2 hàm mới

File hiện có `send_file_async()` (dòng 234-313) và `receive_file_async()`
(dòng 316-373). **KHÔNG sửa 2 hàm này** - chỉ thêm hàm mới bên cạnh, để
luồng cũ (nếu còn dùng ở đâu) không bị ảnh hưởng.

### 1a. `host_receive_file_async()` - vai NHẬN, tự tạo phiên

```python
async def host_receive_file_async(save_dir: str, *, on_progress=None, on_status=None) -> dict:
    """Vai NHẬN, bên TẠO phiên (đúng nguyên tắc "bên nhận tạo phiên" - khác
    receive_file_async() vốn chỉ JOIN phiên có sẵn). Dùng cho
    ReceiveDocumentDialog: mở dialog là gọi hàm này ngay, không đợi người
    dùng dán gì.
    on_status(stage, data) gọi với stage:
      'session_created' -> {"transfer_session_id", "qr_payload"}
      'connected' -> {}
    """
    from .authorization import get_transfer_client
    from aiortc import RTCSessionDescription

    client = get_transfer_client()
    token, device_id = client.get_credentials()

    # file_name/file_size chưa biết tới khi nhận manifest - truyền rỗng,
    # giống cách send_file_async() truyền file thật (khác biệt duy nhất: ở
    # đây ta là bên NHẬN nên chưa có file để mô tả lúc tạo phiên).
    session = client.create_transfer_session("", 0)
    transfer_session_id = session["transfer_session_id"]
    qr_payload = json.dumps({"v": 1, "transfer_session_id": transfer_session_id}, ensure_ascii=False)
    if on_status:
        on_status("session_created", {"transfer_session_id": transfer_session_id, "qr_payload": qr_payload})

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

        # Timeout DÀI hơn receive_file_async() (60s) vì giờ phải đợi thao
        # tác người dùng ở đầu kia (mở ScanDoc, quét QR) - dùng 180s khớp
        # thời gian retry-offer bên gửi.
        try:
            msg = await signaling.recv(timeout=180)
        except asyncio.TimeoutError:
            raise TransferError("Không có thiết bị nào quét mã trong thời gian chờ (3 phút).")
        if msg.get("type") != "sdp_offer":
            raise TransferError("Dữ liệu tín hiệu không hợp lệ (thiếu sdp_offer).")
        await pc.setRemoteDescription(RTCSessionDescription(sdp=msg["sdp"], type="offer"))

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await signaling.send({"type": "sdp_answer", "sdp": pc.localDescription.sdp})

        await asyncio.wait_for(channel_ready.wait(), timeout=30)
        if on_status:
            on_status("connected", {})

        # Tái dùng NGUYÊN _receive_file_over_channel() đã có - không viết lại.
        final_path, file_hash = await _receive_file_over_channel(holder["channel"], save_dir, on_progress)
        client.complete_transfer_session(transfer_session_id, "completed", file_hash)
        return {"transfer_session_id": transfer_session_id, "file_path": final_path, "sha256": file_hash}
    except Exception:
        try:
            client.complete_transfer_session(transfer_session_id, "failed")
        except Exception:
            pass
        raise
    finally:
        await signaling.close()
        await pc.close()
```

Lưu ý: `create_transfer_session("", 0)` - kiểm tra `TransferGatewayClient.create_transfer_session()`
(authorization.py dòng 88-96) có validate rỗng file_name không; nếu backend
từ chối file_name rỗng thì đổi tạm thành `"(đang chờ)"` - không phải vấn đề
lớn vì field này chỉ để hiển thị, không dùng để xác thực gì.

### 1b. `guest_send_file_async()` - vai GỬI, tham gia phiên có sẵn

```python
async def guest_send_file_async(transfer_session_id: str, file_path: str, *, on_progress=None, on_status=None, credentials=None) -> dict:
    """Vai GỬI, THAM GIA phiên do bên kia đã tạo (đọc mã/QR từ ScanDoc dán
    vào ô, hoặc dán trực tiếp transfer_session_id). Dùng cho
    SendDocumentDialog phiên bản mới: người dùng dán mã ScanDoc hiện ra, gọi
    hàm này thay vì send_file_async().
    on_status(stage, data) gọi với stage: 'connected' -> {} (không có
    'session_created' vì phiên đã tồn tại từ trước, transfer_session_id đã
    biết ngay từ tham số vào)."""
    from .authorization import get_transfer_client
    from aiortc import RTCSessionDescription

    if not os.path.isfile(file_path):
        raise TransferError("Không tìm thấy file để gửi.")

    client = get_transfer_client()
    token, device_id = credentials if credentials is not None else client.get_credentials()

    client.join_transfer_session(transfer_session_id, credentials=credentials)

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

        # Y HỆT đoạn retry-offer trong send_file_async() (dòng 279-296) -
        # COPY nguyên, đừng viết lại - lý do timing giải thích chi tiết ở đó
        # vẫn áp dụng y hệt.
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
        client.complete_transfer_session(transfer_session_id, "completed", file_hash, credentials=credentials)
        return {"transfer_session_id": transfer_session_id, "sha256": file_hash, "file_name": os.path.basename(file_path)}
    except Exception:
        try:
            client.complete_transfer_session(transfer_session_id, "failed", credentials=credentials)
        except Exception:
            pass
        raise
    finally:
        await signaling.close()
        await pc.close()
```

---

## Phần 2: `app/transfer_receive_dialog.py` - hiện QR + giữ dán mã dự phòng

Đổi `_setup_ui()` + `_on_start_clicked()`:

- [ ] **Bỏ** việc bắt buộc gõ mã trước khi bắt đầu. Thêm khu vực hiện QR
      (dùng lại đúng cách vẽ QR bên `transfer_pairing_dialog.py` - tìm hàm
      render QR ở đó, KHÔNG viết cách vẽ QR mới).
- [ ] **Mở dialog (`__init__`/`showEvent`) → tự gọi `protocol.host_receive_file_async(save_dir, on_progress, on_status)`
      ngay** (qua `protocol.run_async_in_thread` như code cũ đang làm).
- [ ] `on_status("session_created", data)` → vẽ QR từ `data["qr_payload"]`,
      hiện to giữa dialog, kèm text hiển thị `transfer_session_id` (để có
      thể đọc/gõ tay nếu QR lỗi).
- [ ] Nút **"Tạo mã mới"** - gọi lại `host_receive_file_async` từ đầu (huỷ
      task cũ nếu còn chạy trước khi tạo task mới).
- [ ] **Giữ lại ô dán mã cũ làm dự phòng** (đã chốt với người dùng
      11/08/2026): thêm 1 nút nhỏ/link "Nhập mã thủ công" phía dưới QR, bấm
      vào hiện lại ô `_code_input` + nút bắt đầu như code CŨ hiện tại
      (`_on_start_clicked` cũ, gọi `receive_file_async` cũ - **giữ nguyên
      hàm cũ này, không xoá**) - dùng khi người dùng ScanDoc chọn tab "Tạo
      mã (dự phòng)" bên điện thoại thay vì quét.
- [ ] Cập nhật text hướng dẫn đầu dialog: từ "dán mã/QR JSON do ScanDoc hiển
      thị" → "Mở ScanDoc → Gửi tài liệu → Quét mã QR bên dưới, hoặc bấm
      'Nhập mã thủ công' nếu ScanDoc hiện mã thay vì QR."

---

## Phần 3: `app/transfer_send_dialog.py` - đảo từ tự tạo mã sang dán mã

Hiện tại dùng `protocol.send_file_async(file_path, ...)` (tự tạo phiên +
hiện QR - **sai nguyên tắc mới**, vì ở đây desktop là bên GỬI). Đổi sang:

- [ ] **Bỏ** việc tự động tạo phiên khi mở dialog.
- [ ] Thêm ô nhập/dán mã (copy UI pattern từ `transfer_receive_dialog.py`
      **CŨ** - `_code_input` QTextEdit + nút "Bắt đầu" + `_parse_transfer_session_id()`
      để hỗ trợ dán cả JSON QR lẫn mã thô).
- [ ] Nút "Bắt đầu" → gọi `protocol.guest_send_file_async(transfer_session_id, file_path, on_progress, on_status)`
      thay vì `send_file_async(file_path, ...)`.
- [ ] Text hướng dẫn: "Mở ScanDoc → Nhận tài liệu, dán/gõ mã hiện ra ở đây."
- [ ] **Đổi tên hiển thị nếu cần** để đỡ nhầm: dialog "Chuyển tài liệu" giờ
      là nơi DÁN mã (không còn hiện QR) - cân nhắc đổi tiêu đề phụ hoặc text
      mô tả cho khớp hành vi mới, tránh người dùng cũ quen "Chuyển tài liệu
      = hiện mã" bị bỡ ngỡ.

---

## Phần 4: Test trước khi coi là xong

1. Test **thủ công 2 tiến trình Python trên cùng máy** trước khi đụng UI:
   viết script gọi `host_receive_file_async` ở 1 process,
   `guest_send_file_async` ở process kia với cùng `transfer_session_id`,
   xác nhận file truyền đúng + SHA-256 khớp.
2. Test **thật**: 1 Mac/Win chạy `transfer_receive_dialog.py` mới (hiện
   QR), 1 iPhone thật cài bản TestFlight mới nhất quét — xác nhận nhận file
   thành công, xuất hiện đúng trong "Inbox ScanDoc".
3. Test chiều ngược: ScanDoc "Nhận tài liệu" tạo mã → dán mã đó vào
   `transfer_send_dialog.py` mới → xác nhận desktop gửi thành công, file
   xuất hiện trong thư viện ScanDoc.
4. Test ca lỗi: dán nhầm mã ghép nối thiết bị (`pairing_session_id`) vào ô
   mã transfer - phải báo lỗi rõ ràng, không gửi request rác lên server
   (logic `_parse_transfer_session_id` cũ đã xử lý việc này, xác nhận vẫn
   hoạt động sau khi đổi vị trí dùng nó sang `transfer_send_dialog.py`).

Backend/VPS: **không cần đổi gì** (đã xác nhận ở
`PLAN_2026-08-11_reverse_qr_send_flow.md` mục 9).
