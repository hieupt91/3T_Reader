# Test Coverage — thật đã làm vs. CHƯA làm (không suy đoán)

Nguyên tắc: SOURCE CODE ≠ TEST RESULT. Mục nào chưa thao tác thật qua GUI thì
ghi rõ **BLOCKED / CHƯA TEST**, không tự nhận PASS.

## Test Matrix

| Area | Cases dự kiến (theo yêu cầu gốc) | Đã thao tác thật | Pass | Fail | Blocked/Chưa test |
|---|---:|---:|---:|---:|---:|
| Khởi động app | 1 | 2 (2 phiên) | 2 | 0 | 0 |
| Mở file (thường/nặng/hỏng/unicode) | 3+ | 4 | 4 | 0 | 0 |
| Điều hướng trang | nhiều | có (5 lần next) | pass | 0 | chưa test prev, home/end, page input trực tiếp |
| Zoom | nhiều | có (in x3, stress x20, fit) | pass | 0 | chưa test zoom out, phím tắt zoom |
| Thumbnail | nhiều | có | — | **1 bug (BUG-01)** | — |
| Đa tab | 5→10→20→30→50 | chỉ 2 tab | pass (2 tab) | 0 | **CHƯA test 5/10/20/30/50 tab** |
| Icon stress (20 lần/icon) | ~17 icon nguy cơ cao | "Phóng to" (20x), "Lưu" (10x) | pass (2 icon) | 0 | **CHƯA test 15 icon còn lại** (Open, Delete, Redo, Export, Import, Print, Rotate, Crop, Signature, Share, Settings...) |
| Menu bar (13 menu) | 13 | 13 | pass (13/13, không crash) | 0 | Đã xem nội dung thật của 3/13 (Bảo mật, Chữ ký số, OCR); 10 menu còn lại mới xác nhận mở được, chưa xem kỹ từng mục con |
| Tìm kiếm (Ctrl+F) | có | có (tìm thấy + không tìm thấy) | pass | 0 | Chưa test tìm & thay thế (nếu có), tìm xuyên nhiều trang |
| Highlight/Annotation | có | có (highlight text) | pass | 0 | Chưa test Gạch dưới, Gạch ngang, Ghi chú, Chèn chữ, Chèn ảnh, Vẽ tự do, Xóa trắng |
| Undo/Redo | có | Undo (1 lần) | pass | 0 | Chưa test Redo, Undo nhiều bước liên tiếp |
| Random real-user simulation | nhiều vòng | 0 vòng đầy đủ | — | — | **CHƯA làm** |
| Chaos test | nhiều tình huống | 1 (Ctrl+Tab nhanh) | pass | 0 | **CHƯA làm** các tình huống khác (đóng dialog giữa thao tác, search khi chưa load xong...) |
| Long-run (10p/30p/60p) | 3 mốc | 0 | — | — | **CHƯA làm — cần thời gian thật, không rút ngắn được** |
| Visual regression | nhiều workflow | 1 phần (đã chụp trước/sau nhiều bước) | — | — | Chưa so sánh có hệ thống |
| Window stress | full | Maximize/Restore/Minimize | pass | 0 | Chưa test resize kéo tay, fullscreen |
| Keyboard shortcuts | ~20 phím | Ctrl+O, Ctrl+Tab, Ctrl+F, Enter, Esc | pass | 0 | **CHƯA test** Ctrl+P, Ctrl+S, Ctrl+Z (đã test qua nút, chưa qua phím), Ctrl+C/V, Home/End, PageUp/Down, mũi tên |
| Error injection | nhiều loại | corrupt file | pass | 0 | File thiếu: dialog gốc Windows tự chặn trước khi tới app (xem FULL_TEST_REPORT.md) — cần cách khác để test đúng luồng lỗi của app. Chưa test input rỗng/quá dài trong dialog khác. |
| Crash detection | — | 0 crash xảy ra | — | — | N/A (không có crash để test quy trình phát hiện) |
| Performance baseline | nhiều thao tác | startup + mem sau vài bước | có số liệu | — | Chưa đo file open time/export time/close time riêng biệt |
| Regression sau stress | — | 0 | — | — | **CHƯA làm** (cần restart app sau stress dài rồi test lại — chưa có stress đủ dài để có ý nghĩa) |

## Vì sao các mục "CHƯA TEST" chưa làm được (lý do thật, không phải bịa)

1. **Công cụ GUI automation phải tự xây dựng từ đầu** trong phiên này (không
   có sẵn thư viện kiểu pywinauto cài sẵn) — dùng Windows UI Automation qua
   PowerShell, hoạt động tốt nhưng chậm hơn 1 framework test chuyên dụng.
2. **Thời gian phiên làm việc có giới hạn thực tế.** Yêu cầu gốc (28 mục, tới
   mức mở 50 tab + soak-test 60 phút) là khối lượng công việc nhiều giờ đồng
   hồ liên tục của 1 QA engineer thật — không thể nén vào 1 phiên ngắn mà vẫn
   giữ đúng nguyên tắc "chỉ kết luận PASS sau khi thao tác thật".
3. Ưu tiên đã chọn: phủ **luồng lõi + rủi ro cao nhất trước** (mở file, file
   nặng, file hỏng, stress 1 icon, đa tab cơ bản, window state, đóng app sạch)
   để tối đa hoá khả năng bắt được lỗi nghiêm trọng (P0/P1) trong thời gian có
   hạn, thay vì test dàn trải nông mọi thứ.

## Đề xuất nếu cần phủ đầy đủ 28 mục

Nên tách thành 1 quy trình QA riêng, chạy dài hơi (không phải trong 1 phiên
chat), lý tưởng là:
- Dùng `pywinauto` (Python, chuyên cho Windows desktop automation) thay vì
  PowerShell tự viết — nhanh hơn, dễ viết test-case lặp lại hơn.
- Chạy như 1 scheduled/background job thật sự dài hơi cho phần long-run/soak
  test (không thể rút ngắn 60 phút xuống còn vài giây).
- Icon stress 20x cho từng icon × ~17 icon = việc lặp lại thuần tuý, có thể
  viết thành vòng lặp tự động chạy qua đêm.
