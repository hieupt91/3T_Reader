# Bàn giao chi tiết — Tính năng truyền tài liệu P2P, phía ScanDoc (iOS)

**Đọc trước:** `docs/HANDOFF_TRANSFER_WIN_VPS_2026-08-11.md` +
`...-08-14.md` (kiến trúc/luồng chung, phía desktop) — file này là bản đối
xứng phía iOS, viết 16/08/2026, đối chiếu trực tiếp với code Swift đang
chạy trong repo `scandocapp-business` (nhánh `main`, commit mới nhất
`d45d5cd`).

**Mục đích:** cho team Win/Mac tham khảo đầy đủ khi cần đối chiếu logic 2
phía, hoặc khi tự điều tra lỗi kết nối tương tự phía desktop.

---

## 1. Sơ đồ file (repo `scandocapp-business`, thư mục `Shared/Transfer/`)

| File | Vai trò |
|---|---|
| `WebRTCSendService.swift` | Vai GỬI (offerer) — tạo/tham gia phiên, đẩy bytes qua DataChannel |
| `WebRTCReceiveService.swift` | Vai NHẬN (answerer) — tự tạo phiên, nhận bytes qua DataChannel |
| `SignalingChannel.swift` | Bọc `URLSessionWebSocketTask` — 1 vòng đọc WSS duy nhất, tự kết nối lại khi rớt |
| `WebRTCICEConfig.swift` | STUN/TURN dùng chung, `URLSession` riêng cho kênh signaling |
| `TransferGatewayClient.swift` | REST client: create/join/resolve/complete transfer-session |
| `TransferModels.swift` | `TransferError`, request/response models, parse QR payload |
| `SendToDesktopView.swift` | UI "Gửi tới 3TReader" — 2 tab: "Quét mã" (chính) / "Tạo mã" (dự phòng) |
| `ReceiveFromDesktopView.swift` | UI "Nhận từ 3TReader" — tự tạo phiên + hiện mã khi mở |
| `PairingQRScannerView.swift` | Camera scanner dùng chung (ghép nối thiết bị + quét mã transfer) |
| `CompanionAuthStore.swift` | Quản lý `device_token` (V2, ký JWT) dùng cho mọi request transfer |

---

## 2. Kiến trúc & nguyên tắc — khớp 100% với tài liệu phía desktop

**Bên NHẬN luôn tạo phiên + hiện mã/QR trước, bên GỬI luôn kết nối tới.**
ScanDoc có thể đóng CẢ 2 vai tuỳ màn hình:

| Màn hình iOS | Vai trò phiên | Vai trò WebRTC | Class |
|---|---|---|---|
| "Gửi tới 3TReader" → tab "Quét mã" | Join phiên (quét/gõ mã 3TReader hiện) | Offerer (đẩy bytes) | `WebRTCSendService.sendByJoining()` |
| "Gửi tới 3TReader" → tab "Tạo mã" | Tự tạo phiên, hiện mã | Offerer (đẩy bytes) | `WebRTCSendService.send()` |
| "Nhận từ 3TReader" | Tự tạo phiên, hiện mã/QR | Answerer (nhận bytes) | `WebRTCReceiveService.receive()` |

Cả 2 class dùng chung 1 lõi WebRTC qua `WebRTCICEConfig` (STUN/TURN) và
`SignalingChannel` (WSS) — không viết lại logic 2 lần.

### Format QR/mã — khớp chính xác phía Python

```json
{"v":1,"transfer_session_id":"87d0e760-ab07-4516-a02a-4909a20a1ca3"}
```

`TransferQRPayload.parse()` (`TransferModels.swift`) từ chối JSON thiếu
`transfer_session_id` hoặc không phải JSON hợp lệ — không gửi rác lên
server, tránh nhầm QR ghép nối thiết bị (payload khác, có `pairing_session_id`).

**Lưu ý khác với mô tả trong tài liệu 16/08 phía desktop:** mã ngắn 8 ký tự
**KHÔNG** phải "8 ký tự đầu của `transfer_session_id`" — đây là 1 mã ngẫu
nhiên riêng (Base32, cùng alphabet với mã ghép nối thiết bị), server lưu
`code_hash` (SHA-256, không lưu plaintext) và trả plaintext đúng 1 lần lúc
tạo phiên. Đổi mã ngắn → UUID thật qua `POST /api/v2/transfer-sessions/resolve`
(`TransferGatewayClient.resolveTransferCode()`).

---

## 3. Giao thức DataChannel — không đổi, khớp `protocol.py`

Message đầu tiên (text/JSON) — manifest:
```json
{"type":"manifest","file_name":"hopdong.pdf","size":2451332,"sha256":"<hex>","chunk_size":65536,"chunk_count":38}
```
Các message sau (binary) — 4-byte big-endian chunk index + payload tối đa
64 KiB. Nhận đủ `manifest.size` → SHA-256 toàn bộ, so với `manifest.sha256`
— khớp thì đổi tên atomic, không khớp thì xoá + báo lỗi. Flow-control dựa
`RTCDataChannel.bufferedAmount` (ngưỡng 1 MiB), khớp `BUFFERED_AMOUNT_HIGH`
phía Python.

---

## 4. Lịch sử điều tra lỗi kết nối — 5 vòng bằng chứng thật (11–16/08/2026)

Ghi lại đầy đủ để team desktop hiểu rõ **tại sao** code hiện tại trông như
vậy — mỗi lần sửa đều dựa trên bằng chứng cụ thể team desktop cung cấp
(log SCTP/REST/timestamp), không phải đoán mò.

### Vòng 1 — "chunk send failed at index 0"
Log SCTP: desktop nhận đủ manifest, ScanDoc tự gửi `AbortChunk` ngay sau.
**Nguyên nhân:** `RTCDataChannel.sendData()` trả `false` 1 lần ngay sau khi
kênh vừa mở — race transient của libwebrtc, không phải lỗi mạng thật.
**Fix:** `sendDataWithRetry()` (`WebRTCSendService.swift`) — retry tối đa
10 lần, cách nhau 100ms.

### Vòng 2 — WebSocket đóng sớm, không gửi được offer
**Nguyên nhân:** code cũ tự gọi `receive()` MỚI mỗi lần retry timeout 3s —
Task cancellation không đảm bảo dừng ngay lời gọi cũ, có thể có 2 lời gọi
`receive()` chồng lấn trên cùng 1 socket, message thật bị "nuốt".
**Fix:** viết `SignalingChannel.swift` — 1 vòng đọc nền DUY NHẤT, đẩy
message vào `AsyncStream`, code gọi chỉ tiêu thụ qua `nextMessage()`.

### Vòng 3 — lỗi xảy ra sau đúng ~85 giây (không phải tức thì)
Team desktop đo 2 lần độc lập: 85.0s và 77.8s. **Giả thuyết lúc đó:** race
lúc mới gửi (send ngay sau `.resume()` khi WebSocket chưa bắt tay xong).
**Fix:** `SignalingChannel.send()` tự retry ngắn (~1.5s) trước khi ném lỗi.
**Kết quả:** build có fix này (build 18) vẫn lỗi y hệt — **giả thuyết sai**,
loại bỏ.

### Vòng 4 — nghi Cloudflare edge timeout
`curl -I https://transfer.3tcomputer.com` xác nhận domain qua Cloudflare
proxy. **Giả thuyết:** ping/pong WebSocket cấp thấp không được Cloudflare
tính là "hoạt động" để reset đồng hồ rảnh rỗi.
**Fix:** ping định kỳ 15s + heartbeat DỮ LIỆU THẬT (`{"type":"control"}`
qua `send()` bình thường, không phải `sendPing`).
**Kết quả:** vẫn không đủ — cần điều tra sâu hơn.

### Vòng 5 — XÁC NHẬN THẬT qua log hệ thống trên VPS (không còn giả thuyết)
```
ssh hieupt "journalctl -u cloudflared --since '2026-08-11' | grep 'no recent network activity'"
```
Kết quả: `cloudflared` (giao thức QUIC) **định kỳ tự rớt 1 trong 4 kết nối
nền** ra Cloudflare edge với lỗi *"no recent network activity"* — timeout
xảy ra **ở phía server** (giữa VPS và Cloudflare edge), hoàn toàn ngoài
khả năng kiểm soát của bất kỳ client nào. Đây là lý do cả 4 vòng sửa
trước đều vô ích — tất cả nhắm vào phía client trong khi lỗi nằm ở hạ
tầng server.

**Đã cân nhắc:** đổi `cloudflared` sang giao thức HTTP2 (khuyến nghị chính
thức của Cloudflare cho đúng lỗi QUIC này) — nhưng đây là hạ tầng dùng
chung cho MỌI dịch vụ qua tunnel (website, license-api, reader...), không
riêng transfer. Chủ dự án đã quyết định **không đụng vào** ở giai đoạn
này.

**Fix cuối cùng (commit `d45d5cd`):** vì không ngăn được việc rớt kết nối,
làm CLIENT tự phục hồi. `SignalingChannel.reconnect()` đóng kết nối cũ, mở
lại kết nối mới tới CÙNG URL (token/`transfer_session_id` vẫn hợp lệ phía
server, chỉ cần đăng ký lại participant). Cả `WebRTCSendService.waitForAnswer()`
và `WebRTCReceiveService`'s offer/answer loop bắt riêng
`TransferError.signalingConnectionLost`, gọi `reconnect()` rồi tiếp tục —
**không coi là lỗi cuối cùng**. Cơ chế này chạy được vì bên offerer (dù là
ScanDoc hay desktop) đã tự gửi lại offer mỗi ~3s trong tối đa 180s sẵn có
— chỉ cần signaling sống lại kịp trong khung đó là vẫn ghép được cặp
offer/answer, dù tunnel có rớt bất kỳ lúc nào giữa chừng.

**Trạng thái tại thời điểm viết:** build cục bộ thành công, đã push, đang
chờ Xcode Cloud build ra bản TestFlight mới để team test lại (vòng 6).

---

## 5. `TransferError` — các case liên quan lỗi kết nối (đã tách theo góp ý team desktop)

```swift
case peerConnectionFailed(String)   // WebRTC/ICE lỗi cụ thể
case iceGatheringTimedOut           // ICE/TURN không tìm được đường trong 45s
case signalingConnectionLost(String) // Kênh WSS chết giữa chừng (nay tự reconnect trước khi lộ ra UI)
case timedOut                        // Hết 180s tổng mà vẫn chưa ghép được offer/answer
```

Việc tách riêng `iceGatheringTimedOut`/`signalingConnectionLost` giúp lần
sau chẩn đoán ngay qua message hiện trên UI, không cần đo log server như
trước.

---

## 6. Việc còn tồn đọng / rủi ro đã biết (không có gì mới ngoài tài liệu desktop)

- TURN chỉ hoạt động trong mạng WiFi văn phòng cho tới khi port-forward
  router xong (rủi ro đã ghi từ 11/08, chưa xác nhận đã xử lý).
- Chiều Desktop gửi → ScanDoc nhận: code 2 phía đã xong (`guest_send_file_async()`
  ↔ `WebRTCReceiveService`), **chưa từng test với 1 cặp thiết bị thật**.
- Fix vòng 5 (auto-reconnect) chưa có xác nhận test thật — đây là việc ưu
  tiên nhất hiện tại.
