# 06 — Performance Report

## Đã sửa trong phiên làm việc này (không liệt kê lại là "cần sửa")

| Vấn đề | File | Commit |
|---|---|---|
| Quét PKCS11 đồng bộ trên UI thread mỗi lần ký số/mở file có ô ký số — mỗi driver ứng viên relaunch lại toàn bộ file .exe đã đóng gói làm subprocess | `packages/signing/windows_provider.py` | `6cd087f` (tăng cache TTL khớp chu kỳ quét nền 15s) |
| Đọc outline PDF đệ quy đồng bộ trên UI thread mỗi lần mở file có mục lục lớn | `app/sidebar.py` | `425a6d3` (chuyển sang thread nền) |
| Thêm watermark nhiều trang chặn UI thread, không progress feedback | `app/actions/document_ops.py` | `b90ff2f` |

## Đã kiểm tra kỹ, KHÔNG phải bug (kết luận từ audit trước, xác nhận lại)

**Khởi động app (`main.py` → `PDFReaderApp.__init__`)**: license check, load config AI, check update, theo dõi USB token — tất cả đã `QTimer.singleShot`/QThread đúng cách, không chặn UI lúc mở app. Không có thư viện nặng (`openai`, `pyhanko`, `pdf2docx`...) import ngay từ đầu module. Chi phí lớn nhất, không tránh được, là khởi tạo `QWebEngineView` (Chromium nhúng chạy PDF.js) — thuộc về kiến trúc, không phải bug.

## Phát hiện MỚI (chưa xử lý)

### [Medium] [Confidence: Medium-High] Không có timeout ở vòng lặp chờ cài đặt iTaxViewer

**File**: `app/actions/document_converter.py:1004-1039` (`_run_itax_installer_silent`)

`progress.setCancelButton(None)` loại bỏ hẳn nút hủy; `while proc.poll() is None: QApplication.processEvents()` không có timeout. Nếu bộ cài iTaxViewer (bên thứ 3) treo vì bất kỳ lý do gì (antivirus can thiệp, disk đầy, prompt ẩn dù `/VERYSILENT`), vòng lặp này quay vô hạn — UI vẫn "sống" (event được pump) nhưng cửa sổ bị khóa window-modal, không có nút/timeout/lối thoát nào trong app ngoài việc kill process qua Task Manager.

Đây cũng là 1 bug (không chỉ hiệu năng) — xem chi tiết đầy đủ ở `10_Bug_List.md` §3.

### [Low] Cache token PKCS11 là singleton không khóa

Rủi ro hiệu năng nhẹ: nếu UI thread và worker nền `_TokenPresenceWorker` (chạy mỗi 15s) cùng thấy cache hết hạn tại đúng 1 thời điểm, cả 2 sẽ chạy song song 1 lượt quét PKCS11 đầy đủ (tốn kém) thay vì 1 lượt — lãng phí, không phải crash. Chi tiết đầy đủ (bao gồm khía cạnh an toàn dữ liệu) ở `10_Bug_List.md` §2.

## Không đánh giá được / ngoài phạm vi

Frame drops/jank thực tế, thời gian khởi động đo bằng số (ms) thực — cần chạy app + profiling công cụ (không nằm trong phạm vi "chỉ đọc code" của audit này). Rebuild frequency kiểu Flutter/React không áp dụng cho Qt widget model (Qt không có khái niệm "rebuild" như framework declarative UI).

## Tổng kết

Hiệu năng tổng thể đã được cải thiện đáng kể trong chính phiên làm việc này (3 vấn đề chặn UI thread nghiêm trọng đã sửa). Vấn đề còn lại (timeout cài iTaxViewer, race nhẹ ở cache token) ở mức Medium/Low, không khẩn cấp.
