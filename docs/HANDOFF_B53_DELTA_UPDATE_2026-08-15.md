# B53 — Bàn giao cho team macOS: Delta Update chạy song song

Ngày: 15/08/2026. Tài liệu này chỉ nêu phần **team Mac còn thiếu cần kiểm
tra/triển khai**. Không thay thế các luồng update hiện có và không yêu cầu
đổi API v1.

## Phần Mac đã có — chỉ cần giữ và kiểm tra lại

- Commit `d187a20` đã bắt buộc kiểm tra SHA-256 và chữ ký Ed25519 trước khi
  chấp nhận tệp update. Giữ nguyên cơ chế này; không được quay lại tải thẳng
  từ `download_url` trong dialog.
- Luồng hiện tại vẫn dùng `GET /api/v1/update/check`. Luồng này đang phục vụ
  bản phát hành hiện có và **không được sửa** trong B53.
- Khi xoay khóa Ed25519, danh sách khóa tin cậy trong updater phải được cập
  nhật cùng nguồn key của license client; tuyệt đối không import tên key cũ
  đã bị bỏ.

## Hạ tầng đã sẵn sàng

Backend đã chạy thêm, song song, endpoint:

```text
GET https://reader.3tcomputer.com/api/v2/update/check
```

Tham số:

```text
platform=mac
current_version=<version app>
current_base_version=<version runtime base>
```

Response v2 có các field `update_type` (`none`, `full`, `delta`),
`base_version`, `code_package_url`, `code_package_sha256`, `code_signature`;
đồng thời luôn giữ `download_url`, `sha256`, `signature` cho fallback installer
đầy đủ.

Hiện `delta_enabled=false`. Vì vậy endpoint v2 chưa phát delta cho bất kỳ
người dùng nào; việc gọi thử v2 chỉ trả `full` hoặc `none`. API v1 không bị
ảnh hưởng.

### Schema cần đối chiếu chính xác

```json
{
  "platform": "mac",
  "current_version": "1.0.31",
  "current_base_version": "base-2.0",
  "latest_version": "1.0.32",
  "update_type": "delta",
  "download_url": "https://.../3TReader-1.0.32-mac.dmg",
  "sha256": "<64 hex>",
  "signature": "<Ed25519 base64>",
  "base_version": "base-2.0",
  "code_package_url": "https://.../3TReader-1.0.32-mac-code.zip",
  "code_package_sha256": "<64 hex>",
  "code_signature": "<Ed25519 base64>",
  "mandatory": false,
  "release_notes": "..."
}
```

- `update_type=none`: không hiện dialog update.
- `update_type=full`: dùng nguyên luồng installer/DMG v1 đã verify.
- `update_type=delta`: chỉ được dùng khi cả `base_version` phía server và
  `current_base_version` phía client khớp; thiếu bất kỳ field bảo mật nào phải
  coi là thất bại và fallback `full`.
- `download_url`/`sha256`/`signature` luôn là bộ ba cho DMG đầy đủ.
- `code_package_url`/`code_package_sha256`/`code_signature` là bộ ba riêng
  cho patch; không được hoán đổi hai bộ chữ ký.

### Canonical payload để verify code package

Team Mac phải tạo JSON không khoảng trắng, key sắp xếp tăng dần và UTF-8:

```json
{"base_version":"base-2.0","code_package_sha256":"...","code_package_url":"https://..."}
```

Sau đó verify `code_signature` Ed25519 với một trong các public key tin cậy.
Payload này khác manifest installer (`version`, `download_url`, `sha256`).

## Kiến trúc bắt buộc trước khi viết updater Mac

Delta update không phải cơ chế “tải vài file `.py` rồi copy đè”. Cần tách rõ:

```text
3T Reader.app
├── Base runtime (thay rất hiếm)
│   ├── executable / Python runtime
│   ├── Qt, OCR, native libraries
│   └── bootstrap/recovery updater bất biến
└── Code layer (được phép patch)
    ├── app code
    ├── packages code
    ├── assets thay đổi theo bản vá
    └── native module thuộc chính code layer, nếu có
```

Việc team Mac phải chứng minh trong build thử nghiệm:

1. Vị trí thực tế của từng module khi app đã đóng gói: `Contents/MacOS`,
   `Contents/Resources`, archive Python hay extension native.
2. Thành phần nào bị macOS code signing/Hardened Runtime khóa; thay một file
   bên trong `.app` có làm chữ ký bundle mất hiệu lực hay Gatekeeper từ chối
   không.
3. Nếu app bundle cần ký lại sau mỗi patch, B53 phải dùng gói patch ký bằng
   Developer ID/notarization hoặc chuyển sang kiến trúc app code ở thư mục dữ
   liệu ngoài bundle. Không được tự thay file trong `.app` rồi phát hành khi
   chưa kiểm tra Gatekeeper trên máy sạch.
4. Bootstrap/recovery không được chính code delta thay thế; nếu bootstrap có
   thay đổi thì phải phát hành DMG đầy đủ.

Nếu một trong bốn điều trên chưa chứng minh được, kết luận đúng là **chưa hỗ
trợ delta trên Mac** và chỉ dùng full installer an toàn. Đây không phải thất
bại; API v2 đã hỗ trợ `full` để Mac chuyển đổi dần.

## Việc team Mac cần làm — chưa bắt đầu code khi chưa qua bước 1

1. Kiểm tra cấu trúc build `.app` thật: xác định code ứng dụng có đang bị gom
   trong một archive hay đã là file ngoài bundle có thể thay thế độc lập.
   Không được giả định giống Windows/PyInstaller.
2. Chỉ khi có lớp code thay thế được an toàn: thêm `base_version` lưu tại
   `~/Library/Application Support/3T Reader/base_version.txt`; bản cài chưa có
   file dùng giá trị mặc định đã thống nhất với backend.
3. Thêm client v2 song song (không đổi `check_for_update()` v1): gọi endpoint
   v2, chỉ xem là delta khi `update_type == "delta"` và base version khớp.
4. Tải code package phải xác thực **cả** SHA-256 và `code_signature` trên JSON
   canonical `{base_version, code_package_url, code_package_sha256}`. Chữ ký
   full installer không được dùng thay cho chữ ký code package.
5. Giải nén vào thư mục staging; chống Zip Slip/symlink. Không ghi đè bundle
   khi app còn chạy. Cần helper process hoặc bootstrap trước khi app load code.
6. Có journal + backup + rollback: nếu mất nguồn/force quit khi đang vá, lần
   mở tiếp theo phải khôi phục bản code hoàn chỉnh cũ hoặc tự fallback sang
   installer đầy đủ — không khởi động bundle nửa cũ nửa mới.

### Format package và kiểm tra đầu vào

Đề nghị thống nhất package ZIP chỉ có dạng sau:

```text
manifest.json
payload/
  <relative path 1>
  <relative path 2>
```

`manifest.json` cần ghi version đích, base version, danh sách file và SHA-256
từng file. Client phải từ chối các trường hợp sau, dù archive đã có chữ ký:

- đường dẫn tuyệt đối, `..`, tên Windows/macOS thiết bị đặc biệt;
- symbolic link/hard link trong ZIP;
- file không nằm dưới `payload/`;
- file có hash khác manifest hoặc file manifest không liệt kê;
- cố ghi đè executable, bootstrap/recovery updater, key tin cậy hoặc config
  bảo mật; các thành phần này chỉ đổi qua full installer.

### Chuỗi trạng thái an toàn

```text
check v2 → verify archive → extract staging → verify manifest từng file
  → tạo journal “pending” + backup → thoát app
  → helper apply → journal “complete” → mở lại app
```

Nếu helper chết ở trạng thái `pending`/`applying`, bootstrap ở lần chạy sau
phải ưu tiên rollback backup trước khi load bất cứ module code nào. Không được
“cố chạy tiếp” với tập file chưa hoàn tất.

## Fallback và UX

- Lỗi v2/mạng/JSON: giữ nguyên check v1 hoặc full update, không hiện lỗi kỹ
  thuật khó hiểu cho người dùng.
- Delta sai hash/chữ ký/giải nén/apply: ghi log, xóa staging an toàn, chuyển
  sang tải DMG đầy đủ đã verify.
- Base version khác: không thử patch; chọn `full` ngay.
- Sau khi delta thành công: cập nhật version/base-version chỉ sau trạng thái
  `complete`, không cập nhật từ lúc tải xong.
- Dialog nên nói “Cập nhật nhanh” chỉ khi server trả `delta`; với `full` vẫn
  dùng nội dung “Tải bản cập nhật” hiện có.

## Điều kiện test bắt buộc trước khi đề nghị bật delta

- Update liên tiếp 2 lần bằng code package, rồi đối chiếu hash cây file với
  bản cài mới cùng version.
- Mô phỏng sai hash, sai chữ ký, ZIP chứa `../`, symlink, mất mạng và force
  quit giữa lúc apply: không được chạy code chưa xác thực hoặc để app hỏng.
- Kiểm tra fallback về full installer khi base version không khớp.
- Test Gatekeeper/codesign/notarization trên một máy Mac sạch, không dùng
  máy dev đã bỏ qua cảnh báo bảo mật.
- Test mở PDF, OCR, ký số, ScanDoc và update lại sau một delta thành công để
  xác minh runtime không bị lẫn binary cũ/mới.
- Chỉ sau toàn bộ test trên mới đề nghị VPS bật `delta_enabled=true` cho nhóm
  beta; rollout rộng phải là bước riêng.

## Mốc nguồn liên quan

- Backend API v2: nhánh `phase1-backend`, commit `e90554d`.
- Windows reference (mới có check/tải/verify, chưa phải chuẩn để copy cơ chế
  apply): nhánh `piper-vps-sync`, commit `7cbe557`.
- Kế hoạch đầy đủ đa nền tảng: `piper-vps-sync/docs/PLAN_B53_DELTA_UPDATE_2026-08-15.md`.

Mọi câu hỏi về bật cờ hoặc phát package thật cần phối hợp với team VPS; team
Mac không tự bật `delta_enabled` và không thay API v1.

## Quy trình rollout và rollback giữa Mac–VPS

1. Team Mac gửi bằng chứng build/test cho team VPS; chưa upload package thật.
2. VPS upload package vào URL mới, set hash/base version, nhưng giữ
   `delta_enabled=false`; gọi endpoint v2 bằng version thử nghiệm.
3. Team Mac cài bản beta base tương ứng, chạy toàn bộ matrix và xác nhận log.
4. VPS chỉ bật cho canary/beta theo cấu hình đã thống nhất. Nếu có lỗi, đặt
   `delta_enabled=false` ngay; mọi client quay về installer full, API v1 vẫn
   không bị ảnh hưởng.
5. Chỉ sau canary ổn định mới phát thông báo/chuyển người dùng phổ thông.
