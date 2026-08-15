# 07 — Security Report

## Đã sửa trong phiên làm việc này

| # | Phát hiện | Mức độ | Trạng thái |
|---|---|---|---|
| M1 | Bộ cài iTaxViewer tải về chạy ngầm không kiểm tra checksum/chữ ký (khác với cơ chế tự-update chính của app vốn bắt buộc SHA256+chữ ký) | Medium | ✅ Đã sửa (commit `8c53523`) — kiểm tra sidecar `.sha256` nếu server có publish; hiện server production chưa có nên chưa thực sự kích hoạt bảo vệ, cần VPS admin tự thêm file `.sha256` sau |
| M2 | API key AI mã hóa bằng key suy ra từ MachineGuid+USERNAME — process khác cùng user Windows tự tính lại được | Medium | ✅ Đã sửa (commit `d73ba0d`) — chuyển sang Windows Credential Manager, tương thích ngược đầy đủ |
| L3 | `QThread.terminate()` trùng lỗi A2 ở luồng tải iTaxViewer | Low | ✅ Đã sửa (commit `af91ad6`) |

## Vấn đề pháp lý/tuân thủ nghiêm trọng (phát hiện mới trong đợt audit này)

### [Critical] PyMuPDF (AGPL-3.0) vẫn được đóng gói và sử dụng thật trong bản build đã deploy

**Đã xác nhận 100%** (không phải suy đoán):
- `dist/3T_Reader_Secure/_internal/pymupdf/` **có mặt thật** trong bản build `1.0.27` vừa deploy sáng nay.
- `app/actions/edit.py:2356,2570` có `import fitz` (tên import PyMuPDF) và **dùng thật** (`fitz.open(...)`) trong tính năng "Sửa text gốc" (phát hiện trang scan `_page_is_scan_text`, tìm vùng text `_find_pdf_span`).
- Đây là vấn đề **có sẵn từ trước phiên này** — xác nhận qua `git blame`, code tồn tại ít nhất từ commit `099e983` (2026-07-07), không phải regression do các fix hôm nay gây ra.

**Vì sao nghiêm trọng**: dự án tự ghi nhận trong tài liệu nội bộ đã "gỡ PyMuPDF/fitz vì lý do AGPL" (chỉ còn 1 ngoại lệ đã biết ở `sign_handwritten`) — nhưng thực tế còn ít nhất 2 điểm dùng nữa chưa gỡ. PyMuPDF là AGPL-3.0 (hoặc cần mua license thương mại từ Artifex) — dùng trong phần mềm thương mại đóng nguồn mà không có 1 trong 2 điều kiện đó là vi phạm giấy phép thật, không phải rủi ro lý thuyết.

**Trạng thái xử lý**: đã báo cho chủ dự án, **được yêu cầu ghi nhận vào báo cáo, chưa xử lý vội** (quyết định pháp lý/kinh doanh, không phải quyết định kỹ thuật đơn thuần — không tự ý sửa/gỡ tính năng).

**Hướng xử lý khả dĩ** (không tự ý chọn thay chủ dự án):
1. Mua license thương mại PyMuPDF/Artifex.
2. Thay `_find_pdf_span`/`_page_is_scan_text` bằng `pypdfium2`/`pikepdf` (đã dùng ở phần lớn app) — cần đánh giá kỹ liệu 2 hàm này có API tương đương ở pypdfium2/pikepdf không, chưa điều tra sâu.

Xem thêm `08_Dependency_Report.md` §C1 cho chi tiết kỹ thuật đầy đủ.

## Kết quả audit bảo mật tổng quát (đã kiểm tra kỹ, KHÔNG có vấn đề)

- **License verification** (`packages/license_client/token_verifier.py`): xác minh Ed25519 đúng chuẩn với public key nhúng sẵn, không phụ thuộc pubkey token tự khai — thiết kế đúng. Modified binary bypass là giới hạn cố hữu của mọi kiểm tra phía client, không phải bug riêng.
- **Self-updater** (`packages/updater/update_client.py`): bắt buộc cả SHA256 lẫn chữ ký trước khi chấp nhận bản tải về — triển khai tốt.
- **Local HTTP server** (`app/local_server.py`, đọc toàn bộ 1729 dòng): chỉ bind `127.0.0.1`, có kiểm tra chống path-traversal thật (cả `/pdf` lẫn static file), whitelist đuôi file tĩnh, `Access-Control-Allow-Origin` giới hạn đúng `http://127.0.0.1` (không phải `*`). Không có auth token trên endpoint — về lý thuyết process local khác có thể truy cập PDF đang mở, nhưng tác động thấp (cần đã có code execution local sẵn, chỉ giới hạn ở file user tự mở).
- **`admin-config.json`/`admin-config-update.json`**: xác nhận qua `git log --all` — chưa từng bị commit, đúng gitignore, không lộ vào git history.
- **Backend `main_api.py`**: endpoint admin có rate-limiting + bearer token TTL hợp lý cho quy mô dịch vụ này.
- **PIN/payload ký số** (`sign.py:334,2763`): truyền qua stdin của subprocess, không qua argv/shell string — tránh đúng lỗi kinh điển "lộ mật khẩu qua process list".
- **PFX password prompt**: dùng `QLineEdit.EchoMode.Password` đúng chuẩn.
- **Không tìm thấy** cơ chế tự động thực thi URI/JavaScript nhúng trong PDF ở `packages/pdf_engine/pdfium_engine.py`/`app/pdf_viewer.py`.
- **Temp file Windows**: rủi ro "process user khác đọc trộm file tạm" thấp hơn nhận định ban đầu — `tempfile.gettempdir()` trên Windows trả về thư mục temp riêng của user hiện tại (NTFS giới hạn quyền theo user mặc định), không phải `/tmp` dùng chung như POSIX.

## Chưa xác minh — ghi nhận thay vì đoán

- Chưa rà toàn bộ endpoint `main_api.py` cho IDOR (license_key/device_id/order_id có đoán được không) — mới đọc tầng auth + danh sách endpoint, chưa đọc từng handler.
- Chưa xác nhận endpoint upload/xóa release admin có chống path-traversal trên tham số filename hay không — đọc danh sách endpoint, chưa đọc hết từng hàm xử lý.
- Chưa xác nhận runtime việc port HTTP local server có bị user Windows khác trên cùng máy nhìn thấy được hay không (phụ thuộc cấu hình firewall/session isolation, không xác định được chỉ bằng đọc code).

## Tổng kết mức độ

| Mức độ | Số lượng | Trạng thái |
|---|---|---|
| Critical | 1 (PyMuPDF/AGPL) | Ghi nhận, chờ quyết định |
| Medium | 2 | ✅ Đã sửa |
| Low | 1 | ✅ Đã sửa |
| Đã kiểm tra sạch | 8 khu vực | — |
| Chưa xác minh | 3 mục | Cần điều tra thêm nếu muốn |
