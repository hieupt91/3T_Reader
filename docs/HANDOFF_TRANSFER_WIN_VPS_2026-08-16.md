# Bàn giao cập nhật — Test thật build 20 (auto-reconnect) vẫn lỗi — 16/08/2026

**Đọc trước:** `docs/HANDOFF_TRANSFER_WIN_VPS_2026-08-11.md`, `...-08-14.md`,
và `docs/HANDOFF_TRANSFER_IOS_2026-08-16.md` (nhánh `phase1-backend` —
chẩn đoán root cause cloudflared QUIC + fix auto-reconnect commit `d45d5cd`).

**Tóm tắt:** đã test thật build 20 (bản TestFlight có auto-reconnect) cùng
ngày tài liệu iOS trên được viết — **vẫn lỗi**, nhưng bằng chứng log thu
được **không khớp với chẩn đoán cloudflared QUIC rớt định kỳ** đã nêu.
Ghi lại đầy đủ ở đây để team iOS điều tra tiếp đúng hướng.

---

## 1. Môi trường test

- Desktop: 3T Reader 1.0.34.4 (bản cài thật, không phải dev), dialog "Nhận
  tài liệu" (vai NHẬN/answerer).
- Điện thoại: ScanDoc build 20 (theo xác nhận trực tiếp từ người test —
  bản do team iOS build sau commit `d45d5cd`).
- Mạng: 4G/5G di động (không phải WiFi văn phòng) — đã loại trừ nguyên
  nhân TURN/NAT mạng văn phòng.
- Giữ nguyên màn hình ScanDoc suốt quá trình test — đã loại trừ nguyên
  nhân app bị iOS đưa xuống nền.

## 2. Log server (`transfer-gateway`) — reconnect CÓ chạy nhưng vẫn thất bại

Phiên `912b1bef-9d35-4a56-b13d-fd531137e7ef`:

```
04:43:39.517  WebSocket điện thoại mở
04:43:42.837  WebSocket đóng (~3.3s)
04:43:43.678  → TỰ RECONNECT (đúng cơ chế mới, xác nhận build có fix)
04:43:46.907  WebSocket đóng lại (~3.2s)
04:43:47.361  → TỰ RECONNECT lần 2
04:43:50.747  WebSocket đóng lại (~3.4s)
04:43:51.051  → TỰ RECONNECT lần 3
04:43:54.236  WebSocket đóng lại (~3.2s)
04:43:57.418  → TỰ RECONNECT lần 4
04:43:58.277  Bỏ cuộc, gọi /complete (failed)
```

Ngay sau đó, phiên MỚI hoàn toàn (`7bd9ceb3-3717-452a-a997-f921e2ecb717`):

```
04:44:00.817  Desktop tạo phiên mới
04:44:01.376  Desktop mở WebSocket
04:44:02.820  Điện thoại join — 200 OK
04:44:05.978  Điện thoại mở WebSocket
04:44:21.672  WebSocket đóng (~15.7s) — lần này KHÔNG reconnect
04:44:22.381  /complete (failed)
```

**Nhận xét:** cơ chế `SignalingChannel.reconnect()` chạy đúng như thiết kế
(xác nhận qua 4 lần reconnect liên tiếp ở phiên đầu) — nhưng mỗi kết nối
mới cũng chỉ sống được **~3 giây** trước khi tự đóng lại, nhanh hơn nhiều
so với đợt đo trước (10-16s trên 5G, ~78-85s trên WiFi văn phòng).

## 3. Bằng chứng ngược lại chẩn đoán "cloudflared QUIC rớt định kỳ"

Kiểm tra trực tiếp `journalctl -u cloudflared` trên VPS (cùng lệnh đội iOS
dùng ở vòng điều tra 5):

```
$ sudo journalctl -u cloudflared -n 100 --no-pager | tail -40
...
Aug 12 20:34:03  Registered tunnel connection ... (lần cuối tunnel có sự cố + tự phục hồi)
Aug 13 09:54:20  WRN Your version 2026.5.0 is outdated...
Aug 14 09:54:21  WRN Your version 2026.5.0 is outdated...
Aug 15 09:54:21  WRN Your version 2026.5.0 is outdated...
Aug 15 12:01:58  ERR Unable to reach the origin service... (license-api, không liên quan transfer)
Aug 16 09:54:20  WRN Your version 2026.5.0 is outdated...
```

**Không có bất kỳ dòng log nào kiểu `"no recent network activity"` /
`Connection terminated` / `Retrying connection` trong ngày 16/08** — lần
cuối cùng cloudflared thật sự rớt kết nối QUIC là **12/08**, 4 ngày trước
lần test này. Tunnel hoàn toàn ổn định trong suốt cửa sổ thời gian test
(04:43–04:45).

**Kết luận:** lỗi lần này **nhiều khả năng KHÔNG phải cùng nguyên nhân**
với chẩn đoán vòng 5 (cloudflared QUIC). Hạ tầng phía server đang bình
thường lúc test.

## 4. Nghi vấn mới — hướng điều tra đề xuất cho team iOS

Vì đã loại trừ được: mạng di động, app-background, và (lần này) cả
cloudflared, nghi vấn dồn vào **chính logic mới thêm**:

- `SignalingChannel.reconnect()` — kết nối mới mở ra chỉ sống đúng ~3
  giây rồi tự đóng, đều đặn qua 4 lần liên tiếp. Kiểm tra xem có đường
  code nào trong hoặc ngay sau `reconnect()` vô tình gọi `cancel()`/`close()`
  trên chính kết nối mới vừa mở (ví dụ dọn dẹp task cũ nhưng chưa phân
  biệt đúng task mới vs cũ, hoặc 1 Task nền cũ chưa bị huỷ đúng vẫn tiếp
  tục chạy và đóng kết nối theo lịch cũ).
- Có giới hạn số lần reconnect tối đa không (quan sát được đúng 4 lần rồi
  dừng)? Nếu có, giá trị đó có phù hợp không khi mỗi lần chỉ được ~3s để
  hoàn tất bắt tay?
- Phiên thứ 2 (session hoàn toàn mới) sống được 15.7s và **không hề
  reconnect lần nào** — khác hẳn hành vi của phiên đầu (reconnect 4 lần
  liên tục). Sự khác biệt này gợi ý reconnect có thể phụ thuộc trạng thái
  nào đó không nhất quán giữa các lần thử.

## 5. Việc cần team iOS làm tiếp

1. Rà lại `SignalingChannel.reconnect()` + code gọi nó — tìm đường nào có
   thể tự đóng kết nối mới ngay sau khi mở.
2. Thêm log chi tiết (lý do đóng WebSocket: do server, do timeout cục bộ,
   hay do chính code Swift chủ động gọi `close()`) để lần sau không phải
   suy luận qua log server.
3. Xác nhận lại có đúng đang test build đã build sau commit `d45d5cd`
   không (đối chiếu build number/commit hash trong app, tránh trường hợp
   TestFlight chưa cập nhật bản mới nhất).
