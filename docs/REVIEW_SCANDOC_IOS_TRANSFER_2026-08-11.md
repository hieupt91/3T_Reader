# Rà soát sâu code truyền file phía ScanDoc (iOS) — 11/08/2026

Viết sau khi nhận `docs/BUGREPORT_SCANDOC_IOS_CONNECTION_2026-08-11.md` từ
team desktop (2 lần tái hiện, có log SCTP/REST chi tiết). Mục đích: đọc lại
TOÀN BỘ code phía Swift phụ trách kết nối P2P, đối chiếu từng bước với log
phía desktop, liệt kê rõ đã sửa gì + còn gì cần lưu ý khi team desktop debug
tiếp — để không phải đoán mò dựa trên log 1 phía.

**Trạng thái code tại thời điểm viết**: đã sửa và build thành công cục bộ,
đang trong quá trình commit/push (repo `scandocapp-business`, nhánh `main`).

## 1. Sơ đồ file liên quan

| File | Vai trò |
|---|---|
| `Shared/Transfer/WebRTCSendService.swift` | Vai GỬI (offerer) - tạo/tham gia phiên, đẩy bytes |
| `Shared/Transfer/WebRTCReceiveService.swift` | Vai NHẬN (answerer) - tạo phiên, nhận bytes (chiều mới, xem mục 4) |
| `Shared/Transfer/SignalingChannel.swift` | Bọc WebSocket signaling - 1 vòng đọc duy nhất |
| `Shared/Transfer/WebRTCICEConfig.swift` | STUN/TURN dùng chung 2 service (mới thêm) |
| `Shared/Transfer/TransferGatewayClient.swift` | REST client (create/join/resolve/complete transfer-session) |
| `Shared/Transfer/SendToDesktopView.swift` / `ReceiveFromDesktopView.swift` | UI |

## 2. Đối chiếu 3 lỗi trong báo cáo gốc với code + fix đã áp dụng

### Lỗi 1: "chunk send failed at index 0"

Log SCTP: desktop nhận đủ DCEP + manifest, ScanDoc tự gửi `AbortChunk` ngay
sau. Đối chiếu code CŨ (trước sửa):

```swift
guard dataChannel.sendData(RTCDataBuffer(data: payload, isBinary: true)) else {
    throw TransferError.peerConnectionFailed("chunk send failed at index \(index)")
}
```

`sendData()` trả `false` → ném lỗi ngay → catch ở tầng ngoài gọi
`teardown()` → `peerConnection.close()` → SCTP gửi ABORT. Khớp 100% với log.
**Kết luận: đúng như nghi ngờ ban đầu, không phải giả thuyết sai.**

**Đã sửa**: `sendDataWithRetry()` (WebRTCSendService.swift) - retry tối đa
10 lần, cách nhau 100ms, trước khi coi là lỗi thật. Áp dụng cho cả manifest
lẫn từng chunk.

### Lỗi 2 + 3: WebSocket đóng sớm / UI treo mãi

Code CŨ tự gọi `webSocketTask.receive()` MỚI mỗi lần retry 3s (trong
`waitForAnswer()`'s loop). Rủi ro: Swift Task cancellation không đảm bảo
dừng NGAY 1 lời gọi `receive()` đang chờ ở tầng network - có thể có nhiều
lời gọi `receive()` tồn tại song song trên cùng 1 `URLSessionWebSocketTask`
(hành vi không được `URLSession` đảm bảo), khiến message thật (`sdp_answer`)
bị "nuốt" bởi 1 continuation đã bị bỏ dở.

**Đã sửa**: viết lại hoàn toàn cách đọc signaling
(`SignalingChannel.swift`) - 1 `Task` nền DUY NHẤT gọi `receive()` tuần tự
vô thời hạn, đẩy message vào `AsyncStream`. Mọi nơi cần đọc message chỉ tiêu
thụ từ stream này (`nextMessage(timeout:)`), không bao giờ tự gọi
`receive()` trực tiếp nữa - loại bỏ hoàn toàn khả năng chồng lấn.

Đồng thời thêm theo dõi `RTCIceConnectionState` ở cả 2 service - khi ICE
chuyển `.failed`, mọi vòng chờ (chờ DataChannel mở, chờ nhận xong) fail-fast
ngay với lỗi rõ ràng thay vì treo vô thời hạn dựa hoàn toàn vào timeout tầng
signaling.

### Bằng chứng bổ sung (tái hiện lần 2): "Socket không được kết nối"

Log REST cho thấy `/complete` (failed) được gọi TRƯỚC khi từng gửi
`sdp_offer` - nghĩa là lỗi xảy ra ngay trong `negotiateOffer()`, cụ thể ở
bước `signaling.send(offer)` cuối cùng, tức NGAY SAU khi tạo
`RTCPeerConnection`/gather ICE, trước khi handshake WebRTC thật sự bắt đầu.

**Giả thuyết root cause**: race giữa thời gian ICE gathering hoàn tất (có
thể dưới 1 giây trên mạng LAN/host candidate) và thời gian WebSocket bắt
tay TLS + HTTP upgrade xong (có thể lâu hơn trên mạng di động/WiFi chập
chờn). `send()` gọi ngay sau `.resume()` không được `URLSession` đảm bảo sẽ
tự queue chờ handshake xong ở mọi phiên bản/điều kiện mạng - có thể ném
thẳng lỗi cấp hệ thống.

**Đã sửa**: `SignalingChannel.send()` giờ tự retry tối đa 5 lần (300ms/lần,
~1.5s tổng) trước khi ném lỗi. Đồng thời phân biệt rõ "timeout bình thường"
(caller nên gửi lại) với "socket chết thật" (ném thẳng lỗi gốc, KHÔNG cho
caller cố gửi lại trên socket đã chết - đây chính là nguồn gốc thông báo
"Socket không được kết nối" confusing mà team thấy, vì code cũ coi mọi lỗi
là timeout rồi cố gửi lại).

**Lưu ý cho team desktop khi debug tiếp**: nếu VẪN thấy lỗi này sau khi
ScanDoc cập nhật bản mới, đó là dấu hiệu retry 1.5s vẫn chưa đủ (mạng thật
sự rất chậm/không ổn định) - cần log lại chính xác THỜI ĐIỂM WebSocket
"connection open" xuất hiện trên server so với thời điểm ScanDoc gọi
`create`/`join` REST, để đo khoảng cách thời gian thật.

## 3. Phát hiện thêm khi rà soát (KHÔNG có trong báo cáo gốc)

### 3.1. Thiếu TURN server phía iOS (đã sửa)

`Core/AppConstants.swift` trước đó chỉ có STUN (`stun.l.google.com`,
`stun.cloudflare.com`), không có TURN - trong khi
`packages/transfer/webrtc_transport.py` bên desktop đã thêm TURN relay từ
11/08/2026 (coturn tự host, `116.97.215.211:3478` + `192.168.1.254:3478`
LAN). Nếu mạng THẬT SỰ cần TURN để xuyên NAT (đúng kịch bản Windows Firewall
đã tái hiện), ScanDoc không có candidate TURN nào để dùng dù desktop có -
kết nối sẽ luôn thất bại trên mạng đó bất kể sửa lỗi 1-3 ở trên.

**Đã sửa**: `WebRTCICEConfig.swift` (mới) đồng bộ CHÍNH XÁC danh sách/
credential TURN với `_ICE_SERVERS` bên Python.

### 3.2. Answerer gửi SDP thiếu ICE candidate (bug thật, chưa từng test)

Đây là phát hiện quan trọng nhất của đợt rà soát này. `WebRTCReceiveService.swift`
(vai NHẬN - dùng khi ScanDoc là bên nhận file từ 3TReader, tính năng MỚI
viết cùng ngày, desktop CHƯA có counterpart để test) có đoạn:

```swift
// CODE CŨ (lỗi)
let answer: RTCSessionDescription = try await withCheckedThrowingContinuation { continuation in
    peerConnection.answer(for: constraints) { sdp, error in
        if let sdp { continuation.resume(returning: sdp) }
        ...
    }
}
try await withCheckedThrowingContinuation { ... peerConnection.setLocalDescription(answer) ... }
try await signaling.send(SignalingMessage(type: .sdpAnswer, sdp: answer.sdp))  // <-- answer.sdp CHỤP TRƯỚC KHI GATHER
```

`answer.sdp` là bản SDP "khung" trả về từ `createAnswer()`, được chụp lại
TRƯỚC KHI `setLocalDescription()` chạy - tức TRƯỚC KHI quá trình ICE
gathering (thu thập candidate qua STUN/TURN) bắt đầu. Gửi thẳng biến này đi
nghĩa là SDP answer KHÔNG chứa bất kỳ ICE candidate nào.

Giao thức này là **non-trickle ICE** (đã ghi rõ trong comment đầu file
`WebRTCSendService.swift` và `protocol.py` bên desktop - không xử lý message
`ice_candidate` riêng lẻ, mọi candidate PHẢI nằm sẵn trong SDP trước khi
gửi). Answer thiếu candidate → bên GỬI (offerer) nhận được answer nhưng
không biết kết nối tới đâu → **chỉ hoạt động tình cờ nếu 2 máy cùng chung 1
mạng LAN** (vì host candidate - địa chỉ IP nội bộ - có thể được liệt kê
sẵn trong `answer.sdp` ngay từ bước `createAnswer()` do không cần round-trip
mạng nào để biết, khác với server-reflexive/relay candidate cần STUN/TURN
phản hồi mới có).

So sánh với bên OFFERER (`WebRTCSendService.negotiateOffer()`) - làm ĐÚNG
ngay từ đầu:
```swift
await waitForIceGatheringComplete()
guard let finalOffer = peerConnection.localDescription else { ... }
try await signaling.send(SignalingMessage(type: .sdpOffer, sdp: finalOffer.sdp))
```

**Đã sửa**: `WebRTCReceiveService.swift` giờ đợi `waitForIceGatheringComplete()`
(thêm mới, y hệt pattern bên offerer, có timeout 45s) rồi đọc lại
`peerConnection.localDescription` (đã chứa đủ candidate) mới gửi.

**Vì sao đáng chú ý cho team desktop**: nếu sau này team desktop triển khai
xong Phase 6/7 (đóng vai GỬI tới ScanDoc-đang-nhận, xem
`SPEC_2026-08-11_desktop_reverse_flow_implementation.md`) và gặp lỗi kết
nối THẤT BẠI HOÀN TOÀN trên mạng khác LAN nhưng THÀNH CÔNG khi test cùng
LAN - đây chính xác là triệu chứng của bug này (may mắn hoạt động nhờ host
candidate, thất bại khi cần STUN/TURN). Bug đã sửa trước khi 2 bên kịp test
chiều này, nhưng nêu ra để team desktop hiểu rõ NẾU gặp triệu chứng tương tự
ở 1 lỗi khác sau này, đây là hướng chẩn đoán đáng thử trước.

### 3.3. ICE gathering không có timeout riêng (đã sửa)

Cả 2 service trước đó gọi `waitForIceGatheringComplete()` không có giới hạn
thời gian - nếu gathering không bao giờ hoàn tất (vd TURN server không phản
hồi), toàn bộ luồng treo vô thời hạn ở bước này, KHÔNG được timeout 180s ở
tầng signaling bắt được (vì lỗi xảy ra trước cả bước gửi offer/answer). Đã
thêm timeout 45s, khớp `_ICE_GATHER_TIMEOUT` bên Python.

## 4. Bối cảnh: vì sao có 2 chiều gửi/nhận

Xem `docs/PLAN_2026-08-11_reverse_qr_send_flow.md` mục 0 - nguyên tắc "bên
nhận luôn tạo phiên". `WebRTCSendService` (offerer, đẩy bytes) dùng cho
CẢ 2 chiều thực tế gửi file thật; `WebRTCReceiveService` (answerer, nhận
bytes) là code MỚI, chỉ dùng khi ScanDoc đóng vai bên NHẬN (chiều 3TReader
→ ScanDoc) - đây là lý do bug mục 3.2 tồn tại mà không ai phát hiện: chưa
từng có kịch bản test nào đi qua đường code đó.

## 5. Việc CHƯA làm / rủi ro còn lại (nói thẳng, không giấu)

- **Chưa test lại thật với thiết bị** sau các fix ở mục 2 + 3 - đang chờ
  build mới lên TestFlight. Nếu vẫn lỗi, log REST + log SCTP phía desktop
  vẫn là nguồn thông tin đáng tin cậy nhất để tiếp tục, xem lại đúng cách
  team đã làm ở báo cáo gốc.
- **Credential TURN là long-term/static**, nhúng thẳng trong code Swift lẫn
  Python - chấp nhận được theo đúng quyết định team desktop đã ghi trong
  comment `webrtc_transport.py` (rủi ro thấp: lộ token chỉ dùng relay qua
  đúng server 3T, không lộ dữ liệu người dùng), nhưng nếu sau này cần xoay
  vòng bí mật, PHẢI đổi đồng thời cả 2 phía.
- **Chưa test chiều ScanDoc-nhận (Phase 6/7)** với 1 desktop thật đóng vai
  gửi - phía desktop cần hoàn thành phần "dán mã, gọi guest_send_file_async"
  (đã có sẵn trong spec) trước khi test được trọn vẹn chiều này.
