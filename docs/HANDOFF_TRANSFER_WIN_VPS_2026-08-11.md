# Bàn giao/tham khảo — Tính năng truyền tài liệu P2P (desktop Win + hạ tầng VPS) — 11/08/2026

**Đối tượng đọc:** team iOS (ScanDoc), team Mac (dùng chung codebase desktop
với Win), bất kỳ ai cần hiểu/đụng vào tính năng "Nhận từ ĐT" sau này.
**Trạng thái:** đã triển khai xong, test thật thành công ít nhất 1 lần
end-to-end (ICE/DTLS/SCTP), đang chờ ScanDoc ổn định để test lại trọn vẹn.
**Tài liệu liên quan:** `docs/PLAN_2026-08-11_reverse_qr_send_flow.md`,
`docs/SPEC_2026-08-11_desktop_reverse_flow_implementation.md`,
`docs/BUGREPORT_SCANDOC_IOS_CONNECTION_2026-08-11.md`,
`docs/REVIEW_SCANDOC_IOS_TRANSFER_2026-08-11.md` (đều trên nhánh `phase1-backend`
hoặc `piper-vps-sync` tuỳ file — xem phần dưới).

---

## 1. Kiến trúc tổng quan (nhắc lại, để đọc file này không cần mở lại PLAN/SPEC)

Nguyên tắc cốt lõi: **bên NHẬN luôn tạo phiên + hiện mã/QR, bên GỬI luôn kết
nối tới bằng mã đó** (đảo ngược so với thiết kế ban đầu trước 11/08/2026).

```
┌─────────────┐   1. tạo phiên (REST)    ┌──────────────────┐
│  Bên NHẬN   │ ───────────────────────> │  transfer-gateway │
│ (tạo mã/QR) │ <─── transfer_session_id │  (VPS, REST+WSS)  │
└─────────────┘        + code (8 ký tự)  └──────────────────┘
       │                                          ▲
       │ 2. hiện QR/mã cho bên kia                │ 3. join (REST)
       ▼                                          │
   [người dùng]  ────── quét/gõ mã ──────>  ┌─────────────┐
                                             │  Bên GỬI    │
                                             │ (dán/quét)  │
                                             └─────────────┘
       4. cả 2 bên connect WSS signaling cùng transfer_session_id
       5. trao đổi SDP offer/answer (non-trickle ICE - candidate nằm
          sẵn trong SDP, không có message ice_candidate riêng)
       6. DataChannel mở → gửi thẳng bytes P2P (ưu tiên) hoặc qua
          TURN relay (dự phòng, xem mục 3)
```

Desktop có thể đóng **CẢ 2 vai** tuỳ dialog:
- `ReceiveDocumentDialog` ("Nhận tài liệu") → vai NHẬN → tự tạo phiên, hiện
  QR, nhưng **WebRTC role = answerer** (nhận bytes) → `host_receive_file_async()`.
- `SendDocumentDialog` ("Chuyển tài liệu") → vai GỬI → dán mã ScanDoc đưa
  ra, nhưng **WebRTC role = offerer** (đẩy bytes) → `guest_send_file_async()`.

Lý do tách "ai tạo phiên" khỏi "vai WebRTC": xem comment đầu
`packages/transfer/webrtc_transport.py` — 2 hàm trên chỉ thêm bước REST
tạo/join phiên rồi gọi lại **nguyên vẹn** `send_file()`/`receive_file()` gốc
(logic WebRTC không đổi, không viết lại).

## 2. File code liên quan (nhánh `piper-vps-sync`, desktop Win/Mac dùng chung)

| File | Vai trò |
|---|---|
| `packages/transfer/webrtc_transport.py` | Lõi WebRTC (aiortc) — `send_file()`/`receive_file()` gốc (offerer/answerer thuần) + `host_receive_file_async()`/`guest_send_file_async()` (đảo vai tạo phiên) |
| `packages/transfer/protocol.py` | Format thuần (không phụ thuộc aiortc): `Manifest`, chunk 64 KiB + 4-byte index, SHA-256 verify, sanitize filename |
| `packages/transfer/authorization.py` | REST client: `create_transfer_session`, `join_transfer_session`, `resolve_transfer_code` (mã ngắn), `complete_transfer_session` |
| `packages/transfer/signaling_client.py` | Bọc WSS signaling |
| `app/transfer_receive_dialog.py` | UI "Nhận tài liệu" — tự tạo phiên + QR, có đường dự phòng nhập tay/resolve mã ngắn |
| `app/transfer_send_dialog.py` | UI "Chuyển tài liệu" — dán mã, gọi `guest_send_file_async()` |
| `app/transfer_pairing_dialog.py` | UI ghép nối thiết bị (Phase 1, không liên quan truyền file) + helper dùng chung `_extract_session_id`/`_is_short_code`/`_is_pairing_qr_payload`/`_render_qr_pixmap` |
| `installer_script.iss` | Installer tự đăng ký Windows Firewall rule lúc cài (xem mục 4) |

**Format QR/mã cố định, KHÔNG được đổi** (ScanDoc code cứng theo format này):
`{"v":1,"transfer_session_id":"<uuid>"}`. Mã ngắn 8 ký tự (vd `PJG8-PKQC`)
là tiện ích thêm từ 11/08/2026 — dùng `resolve_transfer_code()` để đổi
sang UUID thật trước khi `join_transfer_session()`.

## 3. Hạ tầng VPS: TURN relay server (mới thêm 11/08/2026)

**Vì sao cần**: STUN thôi không đủ khi 1 bên bị chặn nhận kết nối đến trực
tiếp (đã tái hiện thật: Windows Firewall coi WiFi nhà/văn phòng là "Public
network", chặn hết inbound theo mặc định). TURN chỉ cần app gọi RA (luôn
được phép), không cần ai gọi VÀO máy — né hoàn toàn vấn đề này.

**Đã triển khai:**
- Server: `coturn` (mã nguồn mở), chạy Docker container tên
  `coturn-3treader`, `--network host`, trên máy chủ `192.168.1.254`
  (LAN nội bộ văn phòng — **lưu ý: đây KHÔNG phải cloud VPS thật, mà là máy
  đặt tại chỗ, dùng chung 1 địa chỉ IP public `116.97.215.211` với các máy
  khác trong cùng mạng qua NAT của router** — xem rủi ro ở mục 3.1).
- Config: `/home/hieupt/coturn/turnserver.conf` trên server đó — `lt-cred-mech`
  (username/password tĩnh, long-term, KHÔNG phải REST API ephemeral —
  quyết định chấp nhận được vì token lộ ra cũng chỉ relay được qua đúng
  server 3T, không lộ dữ liệu người dùng nào).
- Credential: xem trực tiếp trong `_ICE_SERVERS` đầu file
  `packages/transfer/webrtc_transport.py` (đã nhúng thẳng trong code, đồng
  bộ credential y hệt phía ScanDoc Swift theo `REVIEW_SCANDOC_IOS_TRANSFER_2026-08-11.md`).
- Firewall VPS (`ufw`): đã mở `3478/udp`, `3478/tcp`,
  `49160:49200/udp` (dải port relay).
- 2 URL TURN cùng trỏ 1 server: IP public (`116.97.215.211:3478`, cho user
  ở mạng khác) + IP LAN (`192.168.1.254:3478`, riêng cho trường hợp test
  cùng mạng vật lý với server — né lỗi NAT hairpin của router khi gửi ra
  chính IP public của mạng mình đang đứng trong đó).

### 3.1. Rủi ro CHƯA giải quyết — cần biết trước khi rollout cho user thật ở mạng khác

Vì server nằm sau NAT của router văn phòng (không phải cloud VPS có IP
public riêng), **user ở mạng KHÁC (không phải văn phòng 3T) chỉ dùng được
TURN qua IP public sau khi ai đó port-forward UDP/TCP `3478` +
`49160-49200` trên chính router đó, trỏ về `192.168.1.254`** — việc này
**không làm được qua SSH**, cần vào trang quản trị router. **Chưa xác nhận
việc này đã được cấu hình hay chưa** — nếu user thật ở nhà/công ty khác báo
lỗi kết nối dù đã có TURN, đây là nghi phạm số 1 cần kiểm tra trước.

### 3.2. Windows Firewall phía client (desktop)

Máy Windows chạy 3T Reader cũng cần cho phép inbound cho chính app (dù có
TURN, kết nối trực tiếp/host-candidate vẫn được ưu tiên thử trước và
thường nhanh hơn nếu thành công). **Installer thật (`installer_script.iss`)
đã tự động thêm rule này lúc cài đặt** (silent, dùng quyền admin sẵn có của
installer) — user thật KHÔNG cần tự làm gì. Chỉ khi chạy bản dev
(`python main.py`, chưa qua installer) mới cần tự thêm rule thủ công qua
PowerShell Admin:
```
netsh advfirewall firewall add rule name="3T_Reader_dev_venv_python" dir=in action=allow program="<path>\.venv\Scripts\python.exe" enable=yes profile=any
```

## 4. Trạng thái test thật (tính đến 11/08/2026)

- **Chiều ScanDoc gửi → desktop nhận**: đã có **1 lần thành công hoàn
  chỉnh** ở tầng mạng (ICE completed, DTLS handshake OK, SCTP ESTABLISHED,
  desktop nhận đúng DCEP + manifest, gửi SACK đầy đủ) — xác nhận toàn bộ
  hạ tầng (TURN, firewall, signaling, protocol) hoạt động đúng khi cả 2
  bên hợp tác đúng cách. ScanDoc sau đó không ổn định qua nhiều lần test
  khác (xem `BUGREPORT_SCANDOC_IOS_CONNECTION_2026-08-11.md` +
  `REVIEW_SCANDOC_IOS_TRANSFER_2026-08-11.md` để biết chi tiết + fix đã áp
  dụng phía ScanDoc + kết quả tái test mới nhất — vẫn còn 1 lỗi chưa rõ
  nguyên nhân, xảy ra sau ~85 giây, nghi timeout ở bước khác).
- **Chiều desktop gửi → ScanDoc nhận**: code desktop
  (`guest_send_file_async()` + `transfer_send_dialog.py`) đã viết xong,
  **chưa từng test thật với 1 desktop + 1 ScanDoc thật** — theo
  `REVIEW_SCANDOC_IOS_TRANSFER_2026-08-11.md` mục 3.2, phía ScanDoc
  (`WebRTCReceiveService.swift`, vai NHẬN) có 1 bug thật (gửi SDP answer
  thiếu ICE candidate) đã được sửa TRƯỚC KHI 2 bên kịp test chiều này —
  nên khi test lần đầu, nếu gặp lỗi, **kiểm tra lại đúng class bug đó
  trước** (đối chiếu `_wait_ice_gathering_complete()` bên Python đã đúng
  thứ tự — đọc `pc.localDescription.sdp` SAU khi gather xong, không phải
  SDP "khung" ban đầu — làm chuẩn tham khảo nếu bên nào viết lại logic
  tương tự sau này).

## 4.1. Xác nhận theo yêu cầu team iOS: `_wait_ice_gathering_complete()` có đúng thứ tự không?

Team iOS hỏi trực tiếp: `host_receive_file_async()`/`guest_send_file_async()`
(2 hàm MỚI viết cùng ngày cho luồng đảo chiều) có gọi
`_wait_ice_gathering_complete()` TRƯỚC KHI gửi SDP không, giống lỗi 3.2 họ
vừa tìm và sửa bên `WebRTCReceiveService.swift`. Đã đọc lại chính xác từng
dòng để trả lời:

- `host_receive_file_async()` (dòng 285, `webrtc_transport.py`): chỉ gọi
  `return await receive_file(...)` — KHÔNG viết lại logic WebRTC.
- `receive_file()` (dòng 223-226): `createAnswer()` → `setLocalDescription()`
  → `_wait_ice_gathering_complete()` → **sau đó** mới đọc
  `pc.localDescription.sdp` để gửi answer. Đúng thứ tự.
- `guest_send_file_async()` (dòng 315): chỉ gọi
  `await send_file(...)` — KHÔNG viết lại logic WebRTC.
- `send_file()` (dòng 112-117): `createOffer()` → `setLocalDescription()`
  → `_wait_ice_gathering_complete()` → **sau đó** mới đọc
  `pc.localDescription.sdp` để gửi offer. Đúng thứ tự.

**Kết luận: không có bug tương tự lỗi 3.2 phía Python.** Cả 2 hàm mới đều
là wrapper mỏng (chỉ thêm bước REST tạo/join phiên), gọi lại nguyên vẹn
`send_file()`/`receive_file()` gốc — không đụng vào phần WebRTC thật.

## 5. Việc CHƯA làm / có thể cần làm tiếp

- Xác nhận port-forward router cho user ở mạng khác văn phòng (mục 3.1).
- Test thật chiều desktop gửi → ScanDoc nhận (chưa từng test).
- Cân nhắc chuyển credential TURN sang cơ chế REST API ephemeral (an toàn
  hơn long-term static) nếu sau này cần xoay vòng bí mật — hiện tại chấp
  nhận rủi ro thấp, xem lý do ở mục 3.
- Bản cài đặt 1.0.30 (bundle đầy đủ các thay đổi trong tài liệu này) đã
  build xong, sẵn sàng test/deploy khi cần.
