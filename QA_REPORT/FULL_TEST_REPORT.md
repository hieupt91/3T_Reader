# 3T Reader — Báo cáo QA thật (GUI Automation)

**Ngày test:** 15/08/2026
**Bản test:** 1.0.33 (cài thật tại `C:\Program Files\3T Reader\3T_Reader.exe`)
**Phương pháp:** Windows UI Automation (System.Windows.Automation) qua PowerShell
— click bằng InvokePattern thật trên control thật lấy từ accessibility tree,
KHÔNG click toạ độ mù, KHÔNG giả lập, KHÔNG suy đoán từ source code. Mọi kết
luận PASS dưới đây đều dựa trên quan sát thật (screenshot + trạng thái process
+ accessibility tree) sau khi thao tác thật.

**⚠️ QUAN TRỌNG — phạm vi đã test so với yêu cầu gốc:** Yêu cầu QA gốc rất lớn
(28 mục, gồm cả stress 50 tab, soak-test 60 phút, lặp mỗi icon 20 lần, chaos
test toàn diện). Trong phiên này em đã thực sự thao tác và quan sát các phần
**cốt lõi** (xem TEST_COVERAGE.md để biết chính xác đã làm gì / chưa làm gì) -
KHÔNG tự nhận đã hoàn thành toàn bộ 28 mục. Phần chưa làm được đánh dấu rõ
**BLOCKED / CHƯA TEST**, không suy đoán là PASS.

---

## Tóm tắt kết quả

| Hạng mục | Kết quả |
|---|---|
| Khởi động app | ✅ PASS — 3.29s tới lúc main window sẵn sàng |
| Mở file PDF thường (50 trang) | ✅ PASS |
| Mở file PDF rất nặng (711MB / 336 trang) | ✅ PASS — không treo, không crash, mở trong tab mới |
| Điều hướng trang (Trang trước/sau) | ✅ PASS |
| Zoom (phóng to/thu nhỏ, cap 400%) | ✅ PASS |
| Stress click zoom 20 lần liên tục | ✅ PASS — không crash, không treo |
| Thumbnail sidebar | ⚠️ **BUG-01 tìm thấy** (xem BUG_REPORT.md) |
| Đa tab (2 tab) + chuyển tab nhanh (Ctrl+Tab x6) | ✅ PASS |
| Mở file PDF hỏng (corrupt) | ✅ PASS — báo lỗi tiếng Việt rõ ràng, không crash |
| Cửa sổ: Maximize/Restore/Minimize/Restore | ✅ PASS |
| Đóng app | ✅ PASS — thoát sạch, không zombie process (đóng 2 lần, sau 2 phiên test) |
| App log / crash log | ✅ Không có file app_log.txt nào được tạo trong suốt phiên test → không có exception/crash nào xảy ra |
| **Vòng 2 — mở rộng phạm vi** | |
| Mở tất cả 13 menu top-level (Tệp, Điều hướng, Xem, Công cụ, Tab, Trang, Bảo mật, Chữ ký số, OCR, AI, License, Ngôn ngữ, Trợ giúp) | ✅ PASS — không crash, đã xem nội dung thật của menu Bảo mật, Chữ ký số, OCR |
| Tìm kiếm trong tài liệu (Ctrl+F) | ✅ PASS — tìm thấy đúng, highlight đúng vị trí; báo "không tìm thấy" đúng khi không khớp |
| Highlight văn bản (chọn text + Tô sáng) | ✅ PASS — áp dụng đúng, tự động lưu chú thích |
| Hoàn tác (Undo) sau khi highlight | ✅ PASS — gỡ đúng highlight vừa thêm |
| Stress "Lưu" 10 lần liên tục | ✅ PASS — không crash (lần đầu test nhầm tab, đã tìm ra nguyên nhân là lỗi thao tác test chứ không phải app) |
| Mở file tên Unicode + ký tự đặc biệt (`tài liệu tiếng Việt (test) #1 @2026.pdf`) | ✅ PASS — tab title, window title hiện đúng, không lỗi encoding |
| Mở file không tồn tại | ⚠️ Dialog chọn file gốc của Windows tự chặn trước (native "File not found") — CHƯA test được đúng luồng xử lý lỗi RIÊNG của app cho path không tồn tại (cần truyền path qua command-line/drag-drop để bỏ qua dialog gốc) |

## Ảnh chụp thật

Xem `screenshots/visual/`, `screenshots/stress/`, `screenshots/bugs/` — mỗi
bước quan trọng đều có ảnh chụp màn hình thật kèm theo, không phải ảnh minh
hoạ.

## Baseline hiệu năng đo được

| Chỉ số | Giá trị |
|---|---|
| Thời gian khởi động tới main window | 3.29 giây |
| RAM sau khi mở 1 file 50 trang | ~380 MB |
| RAM sau stress zoom 20 lần (zoom 100%→400%) | ~525 MB (+144MB, hợp lý vì render bitmap lớn hơn ở zoom cao, không có dấu hiệu leak — cần theo dõi thêm nếu lặp lại nhiều vòng) |
| RAM sau khi mở thêm file 711MB (336 trang) | ~530 MB |

Không đủ dữ liệu dài hạn (10p/30p/60p) để kết luận có memory leak thật hay
không — xem TEST_COVERAGE.md mục "chưa test".
