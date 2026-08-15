# Bàn giao cập nhật — Tính năng truyền tài liệu P2P (desktop Win) — 14/08/2026

**Đọc trước:** `docs/HANDOFF_TRANSFER_WIN_VPS_2026-08-11.md` (bản gốc, vẫn đúng
kiến trúc/luồng/format QR) — file này chỉ ghi phần **thay đổi/làm rõ thêm**
kể từ 11/08/2026, không lặp lại nội dung đã có.

## 1. Fix mới: dialog lỗi trắng không chữ khi DataChannel không mở được

**Vấn đề đã sửa** (`packages/transfer/webrtc_transport.py`, commit `fe9f2c8`):
khi 2 bên trao đổi xong SDP/ICE nhưng kết nối P2P thật sự **không thiết lập
được** (ICE connectivity check thất bại — ví dụ TURN không tới được), code cũ
chờ bằng `asyncio.wait_for(done, timeout=30)` mà không bắt riêng
`asyncio.TimeoutError`. Loại exception này mặc định `str()` **rỗng**, nên
người dùng thấy dialog lỗi trống trơn không có chữ nào thay vì biết chuyện gì
xảy ra.

Đã sửa cả 2 phía (`send_file()` lẫn `receive_file()`): bắt riêng
`asyncio.TimeoutError` tại đúng điểm chờ DataChannel mở, hiện message tiếng
Việt cụ thể: *"Không thiết lập được kết nối trực tiếp với thiết bị (có thể do
tường lửa/mạng chặn). Hãy thử lại khi 2 thiết bị cùng WiFi, hoặc kiểm tra kết
nối mạng."*

**Liên quan trực tiếp tới team iOS:** nếu `WebRTCReceiveService.swift` /
`WebRTCSendService.swift` có cùng pattern (`await` một Task/Continuation với
timeout, không bắt riêng lỗi timeout để hiện message rõ ràng cho user), nên
rà soát tương tự — đây là lớp lỗi rất dễ xảy ra thật khi TURN chưa vào được từ
mạng ngoài (xem mục 2 dưới).

Test: `tests/test_transfer_webrtc.py` (2 test, fake `RTCPeerConnection`,
không cần mạng thật, chạy <1s) — mô phỏng đúng kịch bản DataChannel không bao
giờ bắn event "open", xác nhận exception raise ra là `TransferError` có
message khác rỗng, không phải `asyncio.TimeoutError` trần trụi.

## 2. Làm rõ QUAN TRỌNG: chỉ có 1 máy chủ, không phải 2 máy tách biệt

Tài liệu 11/08/2026 (mục 3) mô tả `coturn-3treader` chạy trên "máy chủ
192.168.1.254 — LAN nội bộ văn phòng" như thể tách biệt với VPS chạy
`transfer-gateway`/`reader.3tcomputer.com`. **Đã xác minh lại bằng SSH thật
14/08/2026: đây là CÙNG MỘT máy vật lý** (`hostname: 3tserver`, cùng IP public
`116.97.215.211`), truy cập được bằng 2 đường khác nhau:
- `ssh.3tcomputer.com` qua Cloudflare Tunnel (dùng cho HTTP/WSS —
  `transfer-gateway`, `license-api`).
- `192.168.1.254:2222` qua LAN trực tiếp (chỉ dùng được khi đứng trong mạng
  văn phòng).

**Không có "cloud VPS thật" nào khác để chuyển TURN sang** — máy duy nhất này
đã đóng vai trò VPS cho toàn bộ hệ thống. Vấn đề "TURN không tới được từ mạng
ngoài văn phòng" (mục 3.1 tài liệu gốc) **vẫn treo y như cũ**, chưa xử lý được
qua SSH — cần port-forward UDP/TCP `3478` + dải `49160-49200` trên router văn
phòng trỏ về `192.168.1.254`, việc này chỉ làm được qua trang quản trị router.
**Đã yêu cầu người phụ trách hạ tầng xử lý trực tiếp trên router — chưa xác
nhận đã xong tại thời điểm viết tài liệu này.**

**Ảnh hưởng cho team iOS:** cho tới khi port-forward xong, TURN
(`turn:116.97.215.211:3478`) **chỉ hoạt động khi ScanDoc test đang đứng cùng
mạng WiFi văn phòng** — nếu test từ 4G/5G hoặc WiFi nhà, kết nối P2P nhiều khả
năng fail ở đúng bước ICE connectivity (bây giờ sẽ hiện message lỗi rõ ràng
nhờ mục 1, thay vì treo im lặng/lỗi trắng) — **đây không phải bug ở code, là
giới hạn hạ tầng đã biết, đừng tốn thời gian debug thêm ở phía app khi gặp
đúng triệu chứng này ngoài mạng văn phòng.**

## 3. Trạng thái hiện tại (14/08/2026)

- Desktop (Win): đã rà soát lại toàn bộ 3 dialog liên quan
  (`transfer_receive_dialog.py`, `transfer_send_dialog.py`,
  `transfer_pairing_dialog.py`) — xử lý lỗi mạng/timeout/license đều đã có
  message rõ ràng, không còn lớp lỗi "trắng không chữ" nào khác được tìm thấy.
- Hạ tầng TURN: vẫn giới hạn trong mạng văn phòng, chờ port-forward router
  (mục 2).
- Test thật ScanDoc ↔ desktop: theo tài liệu 11/08/2026 — 1 lần thành công
  hoàn chỉnh chiều ScanDoc gửi → desktop nhận; chiều desktop gửi → ScanDoc
  nhận (code đã có, `guest_send_file_async()`) **vẫn chưa từng test với 1
  ScanDoc thật.**

## 4. Việc cần team iOS làm tiếp

1. Rà soát code Swift cho lớp lỗi mục 1 (timeout không có message).
2. Khi test, ưu tiên test trong mạng WiFi văn phòng cho tới khi có xác nhận
   port-forward TURN xong (mục 2) — tránh nhầm lẫn giới hạn hạ tầng thành bug.
3. Phối hợp test chiều desktop gửi → ScanDoc nhận (chưa từng test thật).
