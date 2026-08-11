# Báo cáo lỗi: ScanDoc (iOS) kết nối P2P không ổn định khi gửi tài liệu

**Ngày:** 11/08/2026
**Người test:** Team Windows desktop (3T Reader)
**Đối tượng cần xử lý:** Team phụ trách ScanDoc (Swift/iOS)
**Liên quan:** `docs/PLAN_2026-08-11_reverse_qr_send_flow.md`,
`docs/SPEC_2026-08-11_desktop_reverse_flow_implementation.md` (nhánh `phase1-backend`)

## Tóm tắt

Sau khi hoàn thành phần desktop cho luồng đảo chiều gửi/nhận (desktop tạo
phiên + hiện QR, ScanDoc quét mã + gửi file), đã test end-to-end nhiều lần
với 1 điện thoại thật + máy tính Windows thật, cùng mạng WiFi/LAN
(`192.168.1.0/24`). Kết luận:

- **Phía desktop (3T Reader) đã xác nhận chạy đúng** — có ít nhất 1 lần kết
  nối thành công hoàn chỉnh ở tầng mạng: ICE, DTLS, thiết lập kênh dữ liệu
  SCTP, nhận được dữ liệu từ ScanDoc.
- **Phía ScanDoc (iOS) không ổn định** — quan sát được **3 kiểu lỗi khác
  nhau** ở các lần test khác nhau, dù cùng thao tác (quét đúng QR, cùng
  mạng, cùng máy tính). Cả 3 đều xảy ra ở phía ScanDoc, không phải do
  server hay desktop.

Đính kèm dưới đây là log/bằng chứng chi tiết cho từng phần để team iOS có
đủ thông tin điều tra mà không cần dựng lại toàn bộ môi trường test.

---

## 1. Môi trường test

- Desktop: Windows 11, chạy `3T Reader` bản dev (`python main.py`, chưa
  đóng gói .exe) trên nhánh `piper-vps-sync`.
- Điện thoại: iPhone, ScanDoc bản đã lên TestFlight (theo
  `SPEC_2026-08-11_desktop_reverse_flow_implementation.md`, phần ScanDoc
  "đã xong 100%").
- Cùng mạng WiFi nội bộ, dải `192.168.1.0/24` (desktop `192.168.1.2`,
  điện thoại `192.168.1.7`).
- Server tín hiệu (signaling relay) + REST transfer-session: container
  `transfer-gateway-transfer-gateway-1` trên VPS nội bộ — không có thay
  đổi gì ở phần này, không phải nguyên nhân.
- Có bổ sung 1 TURN relay server (coturn) làm phương án dự phòng khi
  không nối trực tiếp được — xem `packages/transfer/webrtc_transport.py`
  đầu file để biết chi tiết cấu hình. Việc này **không ảnh hưởng** tới các
  lỗi mô tả dưới đây (log cho thấy lỗi xảy ra cả ở candidate pair KHÔNG
  qua TURN, tức là nối trực tiếp LAN bình thường).

## 2. Bằng chứng: phía desktop hoạt động đúng

Ở 1 lần test (khoảng 11/08/2026, phiên `4c2959fa-...` — xem log SCTP đầy
đủ ở mục 3.1), log chi tiết của thư viện WebRTC phía desktop
(`aiortc`/`aioice`, bật debug logging tạm thời để điều tra) cho thấy:

```
iceConnectionState: checking -> completed
connectionState: connecting -> connected
RTCDtlsTransport(client): DTLS handshake negotiated SRTP_AES128_CM_SHA1_80
RTCDtlsTransport(client): DTLS handshake complete, State.CONNECTING -> State.CONNECTED
RTCSctpTransport(server): State.CLOSED -> State.ESTABLISHED
RTCDataChannel(1): connecting -> open
```

Nghĩa là: ICE tìm được đường kết nối, bắt tay mã hoá DTLS thành công, thiết
lập được kênh truyền SCTP, kênh dữ liệu (DataChannel) mở thành công. Tất cả
các bước này đều do 2 bên (desktop + ScanDoc) cùng thực hiện qua giao thức
chuẩn WebRTC — nếu phía ScanDoc có lỗi nghiêm trọng trong tầng kết nối, các
bước này sẽ không bao giờ thành công. Việc chúng thành công xác nhận:
**code phía desktop, cấu hình STUN/TURN, và mạng vật lý đều ổn**, vấn đề
nằm ở bước sau đó (gửi dữ liệu ứng dụng qua kênh đã mở).

## 3. Ba kiểu lỗi quan sát được ở ScanDoc

### 3.1. Lỗi 1: Tự huỷ kết nối ngay sau khi gửi chunk đầu tiên ("chunk send failed at index 0")

**Thông báo hiện trên ScanDoc:**
> Không thể kết nối trực tiếp tới 3TReader: chunk send failed at index 0

**Log SCTP phía desktop tại đúng thời điểm lỗi** (nối tiếp log ở mục 2):

```
RTCSctpTransport(server) < InitChunk(flags=0)
RTCSctpTransport(server) - Peer supports 65535 outbound streams, 65535 max inbound streams
RTCSctpTransport(server) > InitAckChunk(flags=0)
RTCSctpTransport(server) < CookieEchoChunk(flags=0)
RTCSctpTransport(server) > CookieAckChunk(flags=0)
RTCSctpTransport(server) - State.CLOSED -> State.ESTABLISHED
RTCSctpTransport(server) < DataChunk(flags=3, tsn=1500590898, stream_id=1, stream_seq=0)
RTCDataChannel(1) - connecting -> open
RTCSctpTransport(server) > DataChunk(flags=3, tsn=3272463329, stream_id=1, stream_seq=0)   # DCEP ACK từ desktop
RTCSctpTransport(server) - T3 start
RTCSctpTransport(server) > SackChunk(...)
RTCSctpTransport(server) < DataChunk(flags=3, tsn=1500590899, stream_id=1, stream_seq=1)    # tin nhắn thứ 2 từ ScanDoc (manifest JSON)
RTCSctpTransport(server) > SackChunk(...)
RTCSctpTransport(server) < SackChunk(...)
RTCSctpTransport(server) - T3 cancel
# ... vài BINDING request/response STUN keepalive bình thường ...
RTCSctpTransport(server) < AbortChunk(flags=0)
RTCSctpTransport(server) x Association was aborted by remote party      # <-- ScanDoc chủ động gửi ABORT
RTCSctpTransport(server) - State.ESTABLISHED -> State.CLOSED
RTCDataChannel(1) - open -> closed
RTCDtlsTransport(client) - DTLS shutdown by remote party
```

**Đọc log này ra sao:** desktop đã **nhận đúng** 2 message đầu (khớp DCEP
mở kênh + manifest JSON), gửi SACK xác nhận đầy đủ, không có gói nào bị
mất hay lỗi checksum. Sau đó chính ScanDoc **chủ động gửi `AbortChunk`**
(lệnh huỷ liên kết SCTP), khiến kết nối bị đóng ngay lập tức — đây không
phải do mạng rớt hay do desktop từ chối, mà là ScanDoc tự quyết định huỷ.

**Gợi ý điều tra phía Swift:** lỗi hiện đúng lúc gửi **chunk dữ liệu thứ 3**
(sau DCEP + manifest, tức "chunk index 0" theo cách đánh số riêng của
ScanDoc — file thật đầu tiên). Kiểm tra:
- Code xử lý `RTCDataChannel.send()` phía Swift — có ném lỗi/throw khi
  nào? (`bufferedAmount` vượt ngưỡng? gọi `send()` từ thread không đúng?
  buffer đầy do gửi quá nhanh không chờ `didChangeBufferedAmount`?)
- Kích thước chunk 3T Reader gửi là 64 KiB (65536 bytes, cộng 4 byte index
  ở đầu = 65540 bytes/message) — nằm trong giới hạn `max-message-size`
  262144 mà chính SDP của ScanDoc khai báo, nên không phải do vượt giới
  hạn kích thước message.
- Có exception/log nào phía Swift ngay tại thời điểm này không (crash log,
  console log trên máy dùng Xcode để xem trực tiếp khi tái hiện)?

### 3.2. Lỗi 2: Đóng kết nối tín hiệu (WebSocket) sớm, không gửi offer

Log server tín hiệu (transfer-gateway, container
`transfer-gateway-transfer-gateway-1`) cho 1 phiên khác:

```
WebSocket .../signal?...&device_id=650b8423... [accepted]   # desktop (windows)
connection open
WebSocket .../signal?...&device_id=                          # ScanDoc (iphone)
connection open
connection closed
connection closed
```

**Cập nhật (tái hiện lần 2, cùng ngày):** lặp lại đúng lỗi này, lần này bắt
được thêm 2 bằng chứng mới:

1. **Thông báo lỗi thấy được trên màn hình ScanDoc:**
   > Không thể hoàn tất tác vụ. Socket không được kết nối.

   Đây là message lỗi cấp thấp (socket-level), không phải lỗi WebRTC/SDP —
   gợi ý mạnh là lỗi nằm ở tầng kết nối WebSocket/network của ScanDoc (ví
   dụ dùng socket đã đóng, hoặc gọi API trước khi socket kết nối xong).
   Team iOS có thể grep chuỗi "Socket không được kết nối" /
   tương đương tiếng Anh ("socket is not connected" — có thể là message gốc
   từ `URLSessionWebSocketTask`/`NWConnection` trước khi được dịch sang
   tiếng Việt trong app) để tìm đúng vị trí ném lỗi này trong code Swift.

2. **Log REST xác nhận ScanDoc tự đánh dấu phiên thất bại:**
   ```
   POST /api/v2/transfer-sessions/<id>/join       -> 200 OK
   POST /api/v2/transfer-sessions/<id>/complete   -> 200 OK   (gọi 2 lần liên tiếp, cùng 1 session id)
   ```
   ScanDoc chủ động gọi API `/complete` (đánh dấu completed/failed) **trước
   khi** từng gửi bất kỳ `sdp_offer` nào qua WebSocket — xác nhận lỗi xảy ra
   ở bước tạo `RTCPeerConnection`/gather ICE candidate cục bộ trên chính
   ScanDoc, TRƯỚC KHI kịp bắt đầu quy trình WebRTC thật sự. Việc gọi
   `/complete` 2 lần liên tiếp cho cùng 1 session có thể là dấu hiệu retry
   logic phía ScanDoc cũng có vấn đề (gọi lại complete thay vì thử kết nối
   lại từ đầu).

Cả 2 bên đều kết nối WebSocket thành công (bằng chứng: cả 2 dòng
`connection open`), nhưng phiên kết thúc (`connection closed`) rất nhanh
sau đó. Ở lần đầu tái hiện, không thấy request `/complete` nào đi kèm; ở
lần tái hiện thứ 2 (mục cập nhật ở trên) thì CÓ — cho thấy hành vi cụ thể
(có gọi `/complete` hay không) có thể khác nhau tuỳ nguyên nhân lỗi cụ thể
bên trong ScanDoc mỗi lần, nhưng điểm chung là: ScanDoc tự đóng kết nối
sớm, không phải do timeout hay do server chủ động ngắt (server đợi tới 180
giây mới coi là hết hạn).

**Gợi ý điều tra:** kiểm tra code phía Swift quản lý WebSocket signaling
— có case nào tự đóng kết nối ngay sau khi mở (ví dụ do lỗi khi bắt đầu
tạo `RTCPeerConnection`/gather ICE candidate cục bộ trên chính ScanDoc,
rồi catch lỗi đó bằng cách đóng WebSocket) không?

### 3.3. Lỗi 3: Giao diện ScanDoc treo ở "đang kết nối" mãi mãi dù kết nối đã chết

Ở 1 lần test khác: phía desktop báo hết hạn phiên (đủ 180 giây không nhận
được offer, tự động hiện lại nút "Tạo mã mới") — nghĩa là về mặt logic,
phiên đã kết thúc/thất bại. Nhưng màn hình ScanDoc **vẫn đứng yên hiện
"đang kết nối"** không đổi, không báo lỗi, không có cách nào cho người
dùng biết là đã thất bại (phải tự đóng app).

**Gợi ý điều tra:** phía Swift cần có cơ chế timeout/theo dõi trạng thái
kết nối (`RTCPeerConnection.iceConnectionState`/`connectionState`) để tự
phát hiện và báo lỗi cho người dùng khi WebSocket đóng hoặc khi không
nhận được `sdp_answer` trong thời gian hợp lý, thay vì treo UI vô thời
hạn. Đây là vấn đề UX/error-handling, độc lập với 2 lỗi kết nối ở trên
nhưng cũng cần sửa vì ảnh hưởng trải nghiệm người dùng thật.

---

## 4. Cách tái hiện

1. Trên desktop: mở 3T Reader → License đã kích hoạt 3TR-E → bấm
   **"Nhận từ ĐT"** trên thanh công cụ (hoặc menu License → "Nhận tài
   liệu...") → dialog tự hiện QR + mã ngắn.
2. Trên ScanDoc: mở app → "Gửi tới 3TReader" → tab "Quét mã" → quét đúng
   QR vừa hiện (hoặc gõ tay mã ngắn ở tab "Tạo mã (dự phòng)").
3. Chọn 1 file PDF bất kỳ để gửi.
4. Quan sát: đa số lần test cho ra 1 trong 3 kiểu lỗi ở mục 3 — **tỉ lệ
   thất bại rất cao, không phải hiện tượng hiếm gặp** (nhiều lần test liên
   tiếp trong cùng buổi, cùng thiết bị, cùng mạng đều gặp lỗi).

## 5. Những gì đã loại trừ (không phải nguyên nhân)

- **Không phải do mạng/router:** ping trực tiếp giữa 2 máy 0% mất gói,
  cùng dải LAN, không có "client isolation".
- **Không phải do Windows Firewall:** đã thêm rule cho phép, và log SCTP
  thành công ở mục 2/3.1 xảy ra SAU khi rule này đã có.
- **Không phải do thiếu STUN/TURN:** log ở mục 3.1 cho thấy ICE/DTLS/SCTP
  đã hoàn tất trước khi lỗi xảy ra — lỗi nằm ở bước gửi dữ liệu ứng dụng,
  sau khi kết nối mạng đã ổn.
- **Không phải do format manifest/protocol sai:** desktop nhận và xử lý
  đúng message DCEP + manifest JSON trước khi ScanDoc tự abort (xem log
  mục 3.1 — 2 message đầu đều được desktop ACK đầy đủ).
- **Không phải do sai transfer_session_id/mã:** log REST (`/join` trả
  `200 OK`) xác nhận ScanDoc join đúng phiên trước khi các lỗi trên xảy ra.

## 6. Tham chiếu code phía desktop (không cần sửa gì thêm ở đây)

- `packages/transfer/webrtc_transport.py` — `host_receive_file_async()` /
  `receive_file()`: vai trò nhận, đã test xác nhận hoạt động đúng.
- `packages/transfer/protocol.py` — định dạng manifest/chunk (64 KiB/chunk,
  4-byte index, SHA-256 verify).

Nếu team iOS cần xem log chi tiết hơn (log SCTP/ICE đầy đủ của các lần
test), liên hệ team desktop — có lưu log debug đầy đủ của các phiên trên.
