# Đặc tả triển khai cho ScanDoc / ScanDoc Business (iOS) — Companion Pairing + P2P Transfer

**Cập nhật 06/08/2026** — bản này thay thế bản trước, đồng bộ 100% với code THẬT đang chạy (`packages/transfer/protocol.py`, `app/transfer_send_dialog.py` trên 3TReader desktop, đã test P2P thật qua `wss://transfer.3tcomputer.com` — file 300KB và 5MB, hash khớp).

**Dành cho:** team mobile (Swift/iOS), triển khai ScanDoc Business — **chưa có code Swift nào tồn tại**, tài liệu này là điểm bắt đầu duy nhất.
**Trạng thái backend:** `transfer-gateway` V2 chạy thật tại `https://transfer.3tcomputer.com`.

---

## 0. Quan trọng — làm ĐÚNG THỨ TỰ, đừng làm ngược

Chiều **3TReader (desktop) → ScanDoc (điện thoại)** đã có UI hoàn chỉnh bên desktop và đã test thật. Chiều ngược lại (điện thoại gửi lên desktop) **desktop chưa có UI nhận** — nếu mobile làm "gửi" trước sẽ không có gì để test cùng.

**→ Làm "NHẬN file" (vai trò receiver/answerer) trên ScanDoc trước.** Vai "gửi" làm sau, cần phối hợp thêm với desktop.

---

## 1. Nguyên tắc bất biến (bắt buộc tuân thủ)

- Không gửi raw key `3TR-E-...` qua network sau bước activate — chỉ dùng mã ghép nối 8 ký tự hoặc QR.
- `device_token` V2 chỉ lưu trong **Keychain**.
- VPS không bao giờ nhận file bytes — mọi endpoint dưới đây chỉ trao đổi metadata (mã, token, SDP/ICE, tên file/kích thước/hash). PDF đi thẳng qua WebRTC DataChannel.
- ICE dùng STUN công khai hiện tại: `stun.l.google.com:19302` và `stun.cloudflare.com:3478` — cấu hình `RTCConfiguration.iceServers` với cả 2. Không dùng TURN. Nếu P2P direct thất bại, báo lỗi rõ ràng, không fallback qua server.

---

## 2. Bước 1 — Ghép nối thiết bị (Companion Pairing) — không đổi so với bản trước

```
POST https://transfer.3tcomputer.com/api/v2/business/companion-sessions/{pairing_session_id}/claim
Content-Type: application/json

{
  "code": "YTSG-WCTG",
  "device_public_key": "<base64, placeholder ổn định là đủ cho bản đầu — xem ghi chú dưới>",
  "device_type": "iphone",
  "display_name": "iPhone của Nam"
}
```

`pairing_session_id` lấy từ QR desktop hiện ra khi bấm **License → Thiết bị ScanDoc → Thêm thiết bị**, nội dung QR:
```json
{"v":1,"pairing_session_id":"5b5e2800-...","nonce":"..."}
```

**Response 200:**
```json
{"device_token":"eyJ...ed2.v2-2026-08", "parent_desktop_device_id":"...", "expires_at":"2027-08-04T23:05:01Z"}
```

Lưu `device_token` (hiệu lực ~1 năm) vào Keychain, dùng làm `Authorization: Bearer <device_token>` cho mọi request ở mục 3 trở đi.

**`device_public_key`:** hiện KHÔNG dùng để mã hoá gì (signaling xác thực bằng `device_token`, không phải public key này) — gửi placeholder ổn định (vd hash `identifierForVendor`) là đủ cho bản đầu. X25519 keypair thật + mã hoá tầng ứng dụng là hạng mục sau, chưa cần cho việc chạy được.

**Lỗi cần xử lý:** `400` mã sai, `410` mã hết hạn/đã dùng, `429` thử sai >5 lần, `403` vượt giới hạn companion.

---

## 3. Bước 2 — Nhận file (vai trò RECEIVER — làm trước)

### 3.1. Quét QR từ desktop

Người dùng trên desktop mở file PDF → **License → Chuyển tài liệu...** → desktop hiện QR + mã 8 ký tự (8 ký tự đầu của `transfer_session_id`, viết hoa). Nội dung QR:
```json
{"v":1,"transfer_session_id":"87d0e760-ab07-4516-a02a-4909a20a1ca3"}
```
Parse lấy `transfer_session_id`.

### 3.2. Join phiên truyền

```
POST https://transfer.3tcomputer.com/api/v2/transfer-sessions/{transfer_session_id}/join
Authorization: Bearer <device_token>
```

**Response 200:**
```json
{"transfer_session_id":"87d0e760-...","sender_device_id":"f72d44bc-...","status":"signaling"}
```

Lỗi `403` nếu thiết bị không cùng `license_id` (khác công ty) với bên gửi — không thể xảy ra bình thường vì cả 2 cùng activate 1 key, nhưng vẫn nên xử lý.

### 3.3. Kết nối WSS signaling

```
wss://transfer.3tcomputer.com/api/v2/transfer-sessions/{transfer_session_id}/signal?token=<device_token>&device_id=
```

Dùng `URLSessionWebSocketTask`. Tham số `device_id` để trống (token V2 tự chứa danh tính thiết bị, server tự nhận diện — không giống desktop dùng token V1 phải kèm `device_id`).

**⚠️ QUAN TRỌNG — bên gửi (desktop) gửi lại `sdp_offer` định kỳ mỗi ~3 giây trong tối đa 180 giây** cho tới khi nhận được `sdp_answer` (vì server KHÔNG buffer message cho socket chưa kết nối — nếu ScanDoc kết nối WS trễ so với lúc desktop gửi offer lần đầu, offer đó bị mất, nhưng sẽ có lần gửi lại tiếp theo). **→ ScanDoc chỉ cần connect WS rồi đợi nhận `sdp_offer` bình thường, timeout hợp lý ~60-90 giây, không cần tự làm gì đặc biệt** — cứ lấy `sdp_offer` mới nhất nhận được (đừng xử lý message `sdp_offer` trùng lặp như lỗi).

Message nhận được:
```json
{"type": "sdp_offer", "sdp": "<SDP string>"}
```

Set làm `RTCSessionDescription` remote (`type: .offer`), tạo answer:
```swift
let answer = try await peerConnection.answer(for: constraints)
try await peerConnection.setLocalDescription(answer)
```
Gửi lại qua WS:
```json
{"type": "sdp_answer", "sdp": "<SDP của answer>"}
```

Vì dùng non-trickle ICE (đợi gom hết candidate rồi mới lấy SDP), **không cần gửi/nhận message `ice_candidate` riêng** cho luồng cơ bản này — candidate đã nằm sẵn trong SDP offer/answer. `control` là loại message thứ 4 server hỗ trợ, hiện chỉ dùng để báo lỗi (`{"type":"control","error":"..."}`), không cần ScanDoc tự gửi.

### 3.4. Nhận file qua DataChannel

Đợi event `didOpen` trên `RTCDataChannel` do desktop tạo (`"transfer"`).

**Message đầu tiên luôn là JSON text (manifest):**
```json
{"type":"manifest","file_name":"hopdong.pdf","size":2451332,"sha256":"<hex sha256>","chunk_size":65536,"chunk_count":38}
```

**Các message sau là binary, mỗi cái = 4-byte big-endian chunk index + dữ liệu nhị phân (tối đa 65536 byte payload):**
```
[0x00,0x00,0x00,0x00] + <65536 bytes đầu tiên>
[0x00,0x00,0x00,0x01] + <65536 bytes tiếp theo>
...
```
Chunk đến **tuần tự đúng thứ tự** (DataChannel ordered/reliable) — nếu `idx` nhận được khác số chunk kỳ vọng tiếp theo, đó là lỗi (không nên xảy ra, nhưng phải kiểm tra và báo lỗi rõ nếu có).

Ghi từng chunk (bỏ 4 byte đầu) nối tiếp vào file tạm `<tên_file_đã_sanitize>.part`. Khi tổng byte nhận đủ `manifest.size`:
1. Tính SHA-256 toàn bộ file tạm.
2. So với `manifest.sha256` — **không khớp thì xoá `.part`, báo lỗi "Truyền thất bại, thử lại", KHÔNG lưu vào thư viện tài liệu.**
3. Khớp thì đổi tên atomic (`FileManager.replaceItem` hoặc `moveItem`) sang tên thật, mới hiển thị "Lưu vào thư viện"/"Mở xem".

Trường hợp `manifest.size == 0` (file rỗng — hiếm nhưng có thể xảy ra): coi như nhận xong ngay, hash SHA-256 của chuỗi rỗng.

### 3.5. Báo hoàn tất

```
POST https://transfer.3tcomputer.com/api/v2/transfer-sessions/{transfer_session_id}/complete
Authorization: Bearer <device_token>
Content-Type: application/json

{"status": "completed", "sha256": "<hash đã verify>"}
```
Gọi `"status":"failed"` (sha256 để trống) nếu lỗi/huỷ giữa chừng.

---

## 4. Bước 3 — Gửi file từ điện thoại (vai trò SENDER — làm SAU, cần thêm việc bên desktop)

Chưa có UI "Nhận" trên desktop tương ứng — **đừng làm phần này trước khi xác nhận với team desktop.** Khi tới lượt làm, logic đối xứng với mục 3 (ScanDoc tạo `POST /api/v2/transfer-sessions`, tự làm offerer, tự retry gửi offer định kỳ như desktop đang làm — xem `packages/transfer/protocol.py` hàm `send_file_async` trong repo `3T_Reader_Phase1` nếu cần đối chiếu chính xác từng dòng logic tham khảo, dù đó là code Python không phải Swift).

---

## 5. Test đã xác nhận từ phía 3TReader/backend (không cần lo lại)

- Toàn bộ REST (pairing claim, transfer-session create/join/complete) hoạt động đúng qua domain công khai.
- WSS signaling relay 2 chiều qua `wss://transfer.3tcomputer.com` — test thật, không phải nội bộ.
- **Truyền file P2P thật đã chạy thành công**: 300KB và 5MB, hash khớp 100%, đã bao gồm cơ chế retry-offer chống race condition.
- Message type lạ / token giả mạo bị chặn đúng, không sập kết nối.

## 6. Chưa test / mobile cần tự xác nhận

- Toàn bộ phía Swift/CryptoKit/URLSessionWebSocketTask — chưa có code tham khảo nào bằng Swift, chỉ có Python.
- Hành vi mạng di động thật (NAT 4G, mạng công ty) — STUN công khai có thể không đủ với NAT đối xứng chặt; nếu gặp, báo lại để cân nhắc STUN riêng.
- `RTCDataChannel` phía WebRTC-iOS (dùng thư viện `WebRTC` CocoaPod/SPM của Google, hoặc GoogleWebRTC) cần cấu hình đúng `isOrdered = true`, `maxRetransmits = nil` (reliable) để khớp giả định "ordered, không mất chunk" ở mục 3.4.
