# Cập nhật P2P Transfer + Kích hoạt key doanh nghiệp — 10/08/2026

Tổng hợp toàn bộ thay đổi trong đợt này, chia theo 3 hệ thống. Dành cho team
Win/Mac/VPS tham khảo khi cập nhật đồng bộ.

## Tóm tắt nhanh

- **Lỗi nặng nhất đã sửa:** gửi tài liệu từ ScanDoc lên 3TReader trước đây
  không dùng được trong thực tế — app tạo mã phiên truyền nhưng không hiển
  thị ra màn hình, nên phía desktop không có gì để dán/nhận.
- **Bug đã sửa:** "Huỷ ghép nối" trên ScanDoc trước đây xoá luôn key kích
  hoạt, bắt gõ lại từ đầu. Giờ tách biệt: key vẫn còn hiệu lực, tự kích hoạt
  lại không cần gõ tay.
- **Bug đã sửa:** 3TReader nhận file xong không có cảnh báo popup, dễ bỏ lỡ
  nếu cửa sổ không đang mở trước mắt.
- Thêm: thời hạn mã gửi tài liệu tuỳ chỉnh (mặc định 1h, trước là 5 phút cố
  định), tự dọn mã hết hạn không dùng tới, màn hình xem danh sách thiết bị
  đã ghép nối cùng key.

---

## 1. Backend VPS (`transfer-gateway`)

Repo `3T_Reader`, nhánh `phase1-backend`, commit `ee19c28` → `b7fc693` →
`7612164`. Đã build lại Docker image và deploy lên VPS (container
`transfer-gateway-transfer-gateway-1`).

### `POST /api/v2/devices/self/revoke` (đã deploy trước đợt này)
Cho phép companion (điện thoại) tự thu hồi chính mình bằng device_token của
nó — trước chỉ desktop mới revoke được thiết bị khác qua `desktop_auth`.
Thiếu route này là lý do "Huỷ ghép nối" trước đây chỉ xoá token cục bộ mà
không giải phóng slot `mobile_companion_limit` trên server.

### `POST /api/v2/transfer-sessions` — TTL tuỳ chỉnh
- Request thêm field `ttl_seconds` (tuỳ chọn, kẹp trong `[60, 86400]`).
- Mặc định server tăng từ `300` (5 phút) lên `3600` (1 giờ) — biến môi
  trường `TRANSFER_TICKET_TTL` (đổi giá trị trên `.env` nếu muốn khác).
- Thêm biến `TRANSFER_TICKET_TTL_MIN` / `TRANSFER_TICKET_TTL_MAX` để chỉnh
  khoảng cho phép, `TRANSFER_SESSION_RETENTION` (mặc định 24h) cho phần dọn
  rác bên dưới.

### Dọn mã rác tự động (`transfer_sessions` + `pairing_sessions`)
Cả 2 bảng giờ tự xoá các row hết hạn quá `retention` (mặc định 24h) — chạy
tranh thủ mỗi lần tạo session/mã mới, không cần thêm cron/scheduler riêng.
Trước đây row hết hạn không ai dùng tới vẫn nằm lại DB vĩnh viễn.

### `GET /api/v2/business/devices` — mở quyền cho companion
Trước chỉ `desktop_auth` gọi được. Đổi sang `any_device_auth` nên điện
thoại (ScanDoc) cũng tự xem được danh sách thiết bị companion cùng key.
Response không đổi (chỉ field công khai: device_id/type/display_name/
last_seen_at/revoked_at — không có token hay license key).

**File đã sửa:** `server/transfer-gateway/app/{config,main,schemas}.py`,
`server/transfer-gateway/app/services/{transfer_session_service,pairing_service}.py`.

---

## 2. ScanDoc App Business (iOS)

Repo `scandocapp-business`, nhánh `main`, commit `600903c` → `cc57189` →
`1d3995c` → `54a7029`. Đã build local thành công (BUILD SUCCEEDED), đã push
— Xcode Cloud tự chạy nếu đã cấu hình auto-start trên `main`.

### `SendToDesktopView.swift` — hiện mã/QR khi gửi (fix lỗi chính)
Trước: server trả về `transfer_session_id` nhưng app chỉ lưu vào biến nội
bộ, không hiển thị gì — người dùng không có mã để dán sang 3TReader, gửi
tài liệu không hoàn tất được trong thực tế dù code không báo lỗi.

Giờ: hiện mã (text lớn, chọn/copy được) + nút "Sao chép mã" + hạn dùng
("Hết hạn lúc HH:mm") ngay sau khi server tạo phiên. Thêm Picker chọn thời
hạn mã (15 phút / 30 phút / 1 giờ / 2 giờ / 4 giờ, mặc định 1 giờ) trước
khi bấm "Bắt đầu gửi" — truyền xuống `ttl_seconds` cho backend.

### `PairedDevicesView.swift` (mới) — danh sách thiết bị đã ghép nối
Vào từ "Thiết bị đã ghép nối" trong màn kích hoạt (chỉ hiện khi đã activate).
Đọc `GET /api/v2/business/devices`, liệt kê tên/loại thiết bị/trạng thái
Đang hoạt động hoặc Đã thu hồi. Chỉ xem — thu hồi thiết bị KHÁC vẫn phải làm
trên 3TReader (như cũ). Kéo xuống để làm mới (không có đồng bộ realtime).

### `CompanionAuthStore.swift` + `CompanionActivationView.swift` — key bền theo thiết bị
Trước: "kích hoạt key" và "phiên/token hiện tại" là MỘT trạng thái duy nhất
— bấm "Huỷ ghép nối" xoá luôn cả key, bắt gõ lại `3TR-E-XXXX-XXXX-XXXX` từ
đầu mỗi lần.

Giờ: khi kích hoạt bằng "Nhập key" (`claimByKey`), app lưu thêm chính key đó
vào Keychain (`saved_license_key`, tách riêng khỏi `device_token`). "Huỷ
ghép nối" (`deactivate()`) KHÔNG còn xoá key đã lưu — chỉ thu hồi phiên hiện
tại trên server rồi xoá token cục bộ. Mỗi lần mở màn kích hoạt mà chưa
activated nhưng còn key đã lưu, app tự gọi lại `claimByKey` bằng đúng key
đó — không cần người dùng gõ tay. Key chỉ thật sự mất khi server từ chối
thật (bị đơn vị thu hồi hoặc hết hạn) — đúng như cách 3TReader desktop hoạt
động.

Lưu ý: cách này chỉ áp dụng cho luồng "Nhập key" — luồng "Kết nối" bằng QR
không có raw key để lưu lại (QR chỉ mang `pairing_session_id` + mã 8 ký
tự), nên sau khi huỷ ghép nối từ đường QR, vẫn cần quét lại QR mới hoặc gõ
tay key nếu người dùng còn nhớ.

### Các fix khác (đợt trước, cùng nằm trong các commit này)
- Splash logo "3T" bị cắt ở màn chờ (do `scaleAspectFill` crop sát mép) —
  đã dịch logo + patch nền, sửa luôn `Contents.json` thiếu `filename` cho
  slot 1x/2x.
- Tab "Kết nối" trong màn kích hoạt bị chặn bằng alert nếu bấm vào khi chưa
  kích hoạt key — tự chuyển về tab "Nhập key".
- Bỏ ô "dán mã phiên thủ công" — quét QR đã tự điền cả `pairing_session_id`
  lẫn mã 8 ký tự.

**File đã sửa/thêm:** `Shared/Transfer/{CompanionAuthStore,
CompanionActivationView, SendToDesktopView, WebRTCSendService,
TransferGatewayClient, TransferModels, PairedDevicesView}.swift`,
`Resources/Assets.xcassets/bg_home.imageset/*`, `ScanDocApp.xcodeproj/project.pbxproj`.

---

## 3. 3T Reader Desktop (Windows/Mac)

Repo `3T_Reader`, nhánh `phase1-mac`, commit `83a0b2b` → `e33ac32`. **Team
Windows cần merge/cherry-pick nhánh này** nếu build Windows tách nhánh
riêng — cùng codebase Python/PySide6 nên áp dụng được trực tiếp.

### `transfer_receive_dialog.py` — popup khi nhận file xong
Trước: `_on_done()` chỉ đổi text 1 label nhỏ bên trong dialog ("✓ Đã nhận
xong: ..."). Nếu cửa sổ "Nhận tài liệu" không đang là cửa sổ active (người
dùng đang làm việc khác), sẽ không biết file đã nhận xong.

Giờ: thêm `QMessageBox.information(...)` bật lên ngay khi nhận xong, cùng
phong cách các popup cảnh báo khác trong `window.py`.

**File đã sửa:** `app/transfer_receive_dialog.py`.

---

## Việc còn tồn đọng (chưa làm trong đợt này)

- **Đồng bộ realtime danh sách thiết bị:** khi 1 phía thu hồi thiết bị, phía
  kia chỉ biết khi gọi API tiếp theo bị 401/403 — chưa có push/polling định
  kỳ. `PairedDevicesView` trên điện thoại phải kéo tay để làm mới.
  desktop 3TReader.

## Cách deploy backend (tham khảo cho lần sau)

```bash
scp server/transfer-gateway/app/<file đã sửa> hieupt:/home/hieupt/projects/3T_Reader/phase1-backend/server/transfer-gateway/app/<cùng path>
ssh hieupt "cd /home/hieupt/projects/3T_Reader/phase1-backend/infra/transfer-gateway && docker compose build transfer-gateway && docker compose up -d transfer-gateway"
```

Lưu ý: thư mục `server/transfer-gateway/` trên VPS **chưa được git-track**
đồng bộ với repo (khác với `server/license-api/` đang bị drift từ trước,
không đụng vào) — nên luôn `diff` file trên VPS với git trước khi ghi đè để
tránh mất thay đổi thủ công nào đó chưa commit.
