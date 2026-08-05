# Đặc tả triển khai cho ScanDoc / ScanDoc Business (iOS) — Companion Pairing + P2P Transfer

**Dành cho:** team mobile (Swift/iOS), triển khai `TransferAuthorizationProvider` phía ScanDoc Business.
**Trạng thái backend:** `transfer-gateway` V2 đã chạy thật tại `https://transfer.3tcomputer.com`, đã test kỹ (REST + WebSocket qua domain công khai thật, không chỉ localhost).
**Chưa có gì phía mobile** — tài liệu này là điểm bắt đầu duy nhất, không có code Swift mẫu nào khác.
**Tài liệu liên quan:** `SPEC_TRANSFER_GATEWAY_V2.md` (kiến trúc tổng, data model), `ENTERPRISE_P2P_TRANSFER_AND_LICENSING_PLAN.md` (định hướng gốc).

---

## 1. Nguyên tắc bất biến (bắt buộc tuân thủ)

- Không bao giờ gửi raw key `3TR-E-...` qua network sau bước activate — chỉ gửi mã ghép nối 8 ký tự hoặc QR (xem mục 2).
- Không lưu `device_token` V2 ở đâu khác ngoài **Keychain** (tương đương macOS Keychain / Windows Credential Manager bên desktop).
- VPS **không bao giờ** nhận file bytes — toàn bộ endpoint dưới đây chỉ trao đổi metadata (mã, token, SDP/ICE, tên file/kích thước/hash). PDF đi thẳng qua WebRTC DataChannel giữa 2 thiết bị.
- Không tự ý fallback qua server nếu P2P direct thất bại — báo lỗi rõ ràng cho người dùng đổi mạng.

---

## 2. Bước 1 — Ghép nối thiết bị (Companion Pairing)

Người dùng mở app ScanDoc Business lần đầu → chọn "Quét mã từ 3TReader" → quét QR hoặc nhập mã 8 ký tự do desktop hiển thị.

### 2.1. Endpoint claim

```
POST https://transfer.3tcomputer.com/api/v2/business/companion-sessions/{pairing_session_id}/claim
Content-Type: application/json

{
  "code": "YTSG-WCTG",
  "device_public_key": "<base64, xem mục 2.2>",
  "device_type": "iphone",   // hoặc "ipad"
  "display_name": "iPhone của Nam"
}
```

`pairing_session_id` lấy từ nội dung QR — QR chứa JSON dạng:
```json
{"v":1,"pairing_session_id":"5b5e2800-...","nonce":"i88KP9OJSMCr7W6v"}
```
Parse `pairing_session_id` từ đó, KHÔNG cần dùng `nonce` cho request (nonce chỉ để đối chiếu hiển thị nếu cần).

**Response 200:**
```json
{
  "device_token": "eyJhdWQiOi....ed2.v2-2026-08",
  "parent_desktop_device_id": "f72d44bc-...",
  "expires_at": "2027-08-04T23:05:01Z"
}
```

**Lỗi cần xử lý UI rõ ràng:**
| HTTP | Ý nghĩa | UI nên hiện |
|---|---|---|
| 400 | Mã không đúng | "Mã không đúng, kiểm tra lại" |
| 410 | Mã hết hạn (>120s) hoặc đã dùng | "Mã đã hết hạn, xin mã mới từ 3TReader" |
| 429 | Thử sai quá 5 lần | "Thử lại sau vài phút" |
| 403 | Vượt giới hạn thiết bị companion | "Key đã đủ số thiết bị cho phép" |

### 2.2. `device_public_key` — sinh key thiết bị

MVP hiện tại chấp nhận bất kỳ chuỗi định danh duy nhất nào cho `device_public_key` (dùng để hiển thị/audit, KHÔNG dùng để mã hoá message ở signaling — signaling dùng `device_token` để xác thực, không dùng public key này). **Khuyến nghị chuẩn cho production:** sinh cặp khoá X25519 lúc cài app lần đầu (CryptoKit `Curve25519.KeyAgreement.PrivateKey`), lưu private key trong Keychain, gửi public key (base64) ở bước claim. Cặp khoá này sẽ dùng để mã hoá tầng ứng dụng ở P1 bảo mật tăng cường (xem mục 5.5 kế hoạch gốc) — **chưa bắt buộc cho bản đầu**, có thể gửi placeholder ổn định (vd hash của `identifierForVendor`) và nâng cấp sau.

### 2.3. Lưu `device_token`

`device_token` có hiệu lực **1 năm** (`expires_at` ~365 ngày kể từ lúc claim). Lưu trong Keychain, dùng làm `Authorization: Bearer <device_token>` cho MỌI request ở mục 3 trở đi. Token có định dạng `body.sig.ed2.key_id` — không tự parse/decode phía client, chỉ dùng nguyên chuỗi.

---

## 3. Bước 2 — Tạo/tham gia phiên truyền PDF (Transfer Session)

### 3.1. Bên gửi tạo phiên

```
POST https://transfer.3tcomputer.com/api/v2/transfer-sessions
Authorization: Bearer <device_token>
Content-Type: application/json

{
  "auth_mode": "business_key",
  "file_name": "hopdong.pdf",
  "file_size": 2451332
}
```

**Response 200:**
```json
{"transfer_session_id": "87d0e760-...", "expires_at": "2026-08-05T03:17:33Z"}
```
`expires_at` ~5 phút — đây là ticket ngắn hạn, phải bắt đầu signaling trước khi hết hạn.

Chia sẻ `transfer_session_id` cho đầu nhận qua **QR/mã mới** (KHÔNG tái dùng mã pairing) — cơ chế QR cho transfer session cụ thể chưa định nghĩa trong bản này, tạm thời có thể dùng chính giá trị `transfer_session_id` làm QR payload (UUID, không nhạy cảm) cho tới khi có thiết kế QR chuẩn riêng.

### 3.2. Bên nhận tham gia

```
POST https://transfer.3tcomputer.com/api/v2/transfer-sessions/{transfer_session_id}/join
Authorization: Bearer <device_token>
```

**Response 200:**
```json
{"transfer_session_id": "87d0e760-...", "sender_device_id": "f72d44bc-...", "status": "signaling"}
```

**Ràng buộc đã test:** chỉ thiết bị **cùng `license_id`** (cùng key doanh nghiệp) mới join được — thiết bị công ty khác bị từ chối `403`.

### 3.3. Báo hoàn tất

```
POST https://transfer.3tcomputer.com/api/v2/transfer-sessions/{transfer_session_id}/complete
Authorization: Bearer <device_token>
Content-Type: application/json

{"status": "completed", "sha256": "<hash file đã nhận, optional>"}
```
Gọi ở **cả 2 đầu** sau khi xác nhận DataChannel đóng thành công (hoặc `"failed"` nếu lỗi giữa chừng).

---

## 4. Bước 3 — WebRTC Signaling qua WSS

### 4.1. Kết nối

```
wss://transfer.3tcomputer.com/api/v2/transfer-sessions/{transfer_session_id}/signal?token=<device_token>
```

Trên iOS dùng `URLSessionWebSocketTask` — truyền token qua **query param** (đã test, không dùng custom header vì tương thích tốt hơn giữa các client). Server chỉ chấp nhận đúng 2 thiết bị đã `create`/`join` phiên đó — thiết bị khác kết nối sẽ bị từ chối ngay ở bước handshake (HTTP 403, không hoàn tất WS upgrade).

### 4.2. Message format

Chỉ 4 loại được chấp nhận, JSON, tối đa **16 KiB/message**:

```json
{"type": "sdp_offer", "sdp": "<SDP string>"}
{"type": "sdp_answer", "sdp": "<SDP string>"}
{"type": "ice_candidate", "candidate": "<ICE candidate string>", "sdpMLineIndex": 0, "sdpMid": "0"}
{"type": "control", "action": "cancel" }
```

Server **relay thuần** — gửi từ 1 bên, bên còn lại nhận nguyên message qua `receive()`. Không có ACK ở tầng signaling (tầng ứng dụng tự làm ACK/progress qua DataChannel, xem mục 5).

Gửi sai `type` → nhận lại `{"type":"control","error":"..."}`, **không bị ngắt kết nối** — tiếp tục gửi message hợp lệ được.

### 4.3. STUN

Server hiện **chưa triển khai STUN service riêng**. Dùng STUN công khai tạm thời cho `RTCConfiguration.iceServers` (ví dụ STUN của Google/Cloudflare) để có ICE candidate — đây là điểm cần nâng cấp sau (kế hoạch gốc mục 3.1 dự tính STUN riêng, chưa làm). Không dùng TURN — nếu ICE connection state rơi vào `failed`, báo người dùng đổi mạng, **không fallback** qua server.

---

## 5. Bước 4 — Giao thức truyền file qua DataChannel (thiết kế, CHƯA có code tham chiếu bên nào)

Đây là phần chưa ai implement (cả mobile lẫn desktop) — thiết kế dưới đây để 2 bên làm khớp nhau, dựa theo kế hoạch gốc mục 5.2:

1. Mở `RTCDataChannel` (`ordered: true, maxRetransmits: nil` — reliable/ordered).
2. Bên gửi gửi **manifest** trước, dạng JSON UTF-8 làm message đầu tiên:
   ```json
   {"type":"manifest","file_name":"hopdong.pdf","size":2451332,"sha256":"<hash toàn file>","chunk_size":65536,"chunk_count":38}
   ```
3. Gửi từng chunk nhị phân tối đa **64 KiB**, tuần tự theo thứ tự (DataChannel ordered nên không cần đánh số, nhưng khuyến nghị prepend 4-byte big-endian chunk index để bên nhận verify không thiếu).
4. Bên gửi theo dõi `bufferedAmount` — tạm dừng gửi khi vượt ngưỡng (khuyến nghị 1MB), tránh tràn bộ nhớ đầu nhận.
5. Bên nhận gửi lại message JSON nhỏ định kỳ qua cùng DataChannel để báo progress: `{"type":"progress","received_bytes":1245184}` — không bắt buộc, nhưng nên có để UI hiện % tiến độ.
6. Nhận đủ `chunk_count` → verify SHA-256 toàn bộ dữ liệu ghép lại khớp `manifest.sha256` → ghi file vào `.part` → đổi tên atomic sang tên thật (giống cách 3TReader desktop đang làm với `_pdf_save.py`, dùng `os.replace`/`FileManager.replaceItem`) → chỉ hiển thị "Mở/Lưu vào thư viện" sau khi hash khớp.
7. Hash sai → xoá file `.part`, KHÔNG hiển thị trong danh sách tài liệu, báo lỗi "Truyền thất bại, thử lại".
8. Gọi `POST /transfer-sessions/{id}/complete` với `status` tương ứng sau bước 6/7.

---

## 6. Test đã xác nhận từ phía backend (bạn không cần lo lại các case này)

- Tạo/join/complete transfer-session qua REST — đúng luồng, đúng lỗi khi sai quyền.
- WSS signaling relay 2 chiều — test thật qua `wss://transfer.3tcomputer.com` (không chỉ nội bộ VPS), cả 2 phía nhận đúng message.
- Message type lạ bị từ chối, không sập kết nối.
- Thiết bị/token giả mạo bị chặn ở bước handshake WS (HTTP 403).
- Thiết bị khác công ty (khác `license_id`) không join được phiên nhau.

## 7. Chưa test được / cần mobile tự xác nhận

- Toàn bộ luồng WebRTC thật (SDP negotiation, ICE gathering, DataChannel mở) — backend chỉ test được phần relay, **chưa test được 2 đầu client thật đàm phán P2P thành công** vì cần 2 thiết bị/app thật.
- Hành vi mạng di động/NAT thực tế (4G, mạng công ty chặn UDP) — cần test ma trận Wi-Fi/4G như kế hoạch gốc mục 12.1.
- Giao thức manifest/chunk ở mục 5 là **thiết kế đề xuất**, chưa có code tham chiếu nào implement — nếu mobile làm trước desktop (`packages/transfer/protocol.py` bên 3TReader), báo lại để đồng bộ format chính xác từng field tránh lệch giữa 2 nền tảng.
