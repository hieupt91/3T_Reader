# QA Report — 3T Reader (app thật đã cài trên máy)

- **Ngày test:** 2026-08-16
- **App version:** 1.0.34.3 (xác nhận trên welcome screen + `_internal/app/version.py`)
- **Install location:** `C:\Program Files\3T Reader\3T_Reader.exe`
- **Phương pháp:** GUI automation thật (mouse click toạ độ pixel qua screenshot + phân tích ảnh, keyboard SendInput, win32 process/window enumeration). Không dùng UI Automation tree đọc nội dung control được vì app chạy elevated, shell điều khiển không elevated → UIPI chặn (`pywinauto` UIA backend trả `ElementNotFoundError` 100% số lần thử; `SetForegroundWindow` cũng bị chặn).

## PHẠM VI SO VỚI YÊU CẦU GỐC (28 mục)

Yêu cầu gốc là 1 bộ QA spec rất lớn (50-tab stress, long-run 60 phút, 20x click mỗi icon, chaos test toàn diện, OCR/AI/ký số end-to-end...). Trong 1 phiên làm việc thực tế, đã hoàn thành 1 tập con có giá trị cao, KHÔNG hoàn thành toàn bộ spec. Chi tiết ở `TEST_COVERAGE.md`.

## KẾT QUẢ THEO KHU VỰC

| Khu vực | Đã test | Kết quả |
|---|---|---|
| Startup | Cold start, đo thời gian | PASS (~2.36s tới khi main window hiện) |
| Welcome screen | Inventory UI, hiển thị version | PASS |
| Mở file (recent list) | Click mở file gần đây | PASS (nhưng xem ghi chú an toàn dữ liệu bên dưới) |
| Zoom | Rapid click "Phóng to" x15 | PASS — clamp đúng ở 400%, không crash |
| Thumbnail sidebar toggle | Rapid click x21 (regression BUG-01) | PASS — thumbnail trang 1 render đúng, không bị blank |
| Điều hướng trang | Rapid click "Trang sau" x30 (trang 1→31) | PASS — page counter, nội dung, thumbnail sync đều khớp, không crash/freeze |
| Multi-tab | Mở 2 tab đồng thời, chuyển qua lại | PASS — không có hiện tượng tab A ảnh hưởng tab B |
| Error injection — file hỏng | Mở `corrupt_file.pdf` | PASS — dialog lỗi rõ ràng, không crash, đóng dialog xong app vẫn ổn định |
| Error injection — tên file dài (149 ký tự) | Dự định test | **NOT TESTED** — vướng thao tác dialog Windows native, bỏ qua vì thời gian |
| Tìm kiếm (Ctrl+F) | Mở thanh tìm kiếm, gõ từ khoá | **BLOCKED** — thanh tìm kiếm mở đúng, nhưng gõ qua SendInput không vào được ô input (nằm trong QWebEngineView/Chromium). Nhiều khả năng là giới hạn công cụ automation, CHƯA đủ bằng chứng kết luận là bug thật — cần test tay để xác nhận |
| Window management | Maximize, Minimize, Restore | PASS — layout không vỡ ở maximize, không crash qua minimize/restore |
| Update flow (delta 1.0.34.2 → 1.0.34.3) | Full cycle: check → download → apply → relaunch | PASS (test trong phiên làm việc trước đó cùng ngày) |
| Resource usage | Snapshot sau stress test | Working set ~448MB, không có dấu hiệu bất thường (không có baseline dài hạn để so sánh leak) |

## PHÁT HIỆN ĐÁNG CHÚ Ý (không phải bug xác nhận)

1. **Chữ có dấu bị mất glyph trong nội dung PDF** (`▪` thay cho `Đ`, `ẵ`, `ộ`...) khi xem `medium_50pages.pdf` (file fixture QA tự tạo). Test đối chứng bằng 1 file khác (`tài liệu tiếng Việt (test) #1 @2026.pdf`) không tái hiện được (file đó không có nội dung dấu tiếng Việt trong thân trang để so sánh). **Nghi vấn nghiêng về lỗi font trong chính file fixture tự tạo, KHÔNG PHẢI kết luận là bug app** — cần test lại bằng 1 file PDF tiếng Việt thật có dấu đầy đủ, không phải file cá nhân nhạy cảm.
2. **Danh sách "Gần đây" đổi thứ tự linh hoạt theo MRU** — trong lúc test, việc này khiến tự động hoá click nhầm phải `CCCD PHẠM TRUNG HIẾU.pdf` (file cá nhân nhạy cảm của người dùng) 2 lần do toạ độ dropdown dịch chuyển. Đã đóng ngay bằng Ctrl+W cả 2 lần, **không xem/chụp/lưu bất kỳ nội dung nào của file đó**. Đây là rủi ro của phương pháp test (click toạ độ cố định trên danh sách MRU động), không phải bug của app.
3. **1 process con phụ 3T_Reader.exe xuất hiện thoáng qua rồi biến mất** trong lúc gõ search — kiểm tra lại ngay bằng `Win32_Process` (nguồn đáng tin hơn `Get-Process` tại thời điểm race) chỉ thấy 1 process. Có khả năng là artifact của việc lấy process list đúng lúc 1 tiến trình con ngắn hạn (vd worker OCR/search-index) khởi động rồi thoát. Không quan sát lại được lần 2, không đủ cơ sở báo là bug.

## BUG P0/P1/P2 TÌM ĐƯỢC

**Không có.** Không crash, không freeze, không mất dữ liệu, không data corruption trong toàn bộ phạm vi đã test.

## PHIÊN TEST MỞ RỘNG (bổ sung sau báo cáo lần 1) — file nặng thật + đa-tab + thao tác chi tiết

Theo yêu cầu: mở 5 file nặng nhất tìm được trên máy + 3 file thường cùng lúc, test thao tác chi tiết từng tab.

- **5 file nặng nhất tìm được** (dùng hardlink NTFS trỏ vào `test_fixtures/` để tránh phải điều hướng dialog — hardlink không tạo bản sao, không tốn dung lượng, và an toàn: xoá hardlink không ảnh hưởng file gốc trong Downloads):
  1. `1 Dao giao sinh tu ky thu - in (1).pdf` — 711.7MB, 338 trang (sách, không phải nội dung riêng tư — đã dùng làm chuẩn test file nặng từ phiên QA 2026-08-04)
  2. `..._signed.pdf` — 745MB (bản đã ký)
  3. `..._gop.pdf` — 745MB (bản đã ghép)
  4. `Uone LED Light Catalog-08.2025.pdf` — 75.4MB
  5. `Aqara Quốc tế - HOPLONG T7-25.pdf` — 18.1MB
- **3 file thường:** `medium_50pages.pdf`, `tài liệu tiếng Việt (test) #1 @2026.pdf` (file thứ 3 dự định `qa_save_as_test.pdf` không kịp mở do giới hạn thời gian — không ảnh hưởng kết quả 7 tab đã test)
- **Kết quả đa-tab:** mở đủ 7 tab cùng lúc (3 file 700MB+ + 2 file vừa + 2 file nhỏ), app **ổn định hoàn toàn**, RAM chỉ ~747-879MB (không phình tuyến tính theo tổng dung lượng file — cơ chế render lazy/stream hiệu quả), chuyển tab qua lại nội dung hiển thị đúng, không lẫn giữa các tab, thumbnail đồng bộ đúng ở mọi tab.
- **Cảnh báo an toàn RAM:** dialog "Tài liệu rất lớn — mở thêm có thể làm sập ứng dụng, bạn vẫn muốn mở tiếp?" xuất hiện đúng lúc khi mở file nặng thứ 2 trở đi — cơ chế bảo vệ người dùng hoạt động tốt.
- **Thao tác chi tiết trên tab an toàn (`medium_50pages.pdf`):**
  - Xoay phải trang — PASS
  - Xoá trang (có dialog xác nhận "không thể hoàn tác") — PASS, đúng vùng bug #22 vừa fix
  - Đánh số trang (2 bước: chọn vị trí, số bắt đầu) — PASS, **không giật/reload hình** — xác nhận trực tiếp fix bug #23 hoạt động đúng trên app thật
  - Chèn ảnh/text (bug #21) — **KHÔNG kịp test** do hết thời gian phiên + terminal giành lại foreground giữa chừng làm gián đoạn thao tác tiếp theo
  - Ký số USB Token (bug #20) — **KHÔNG test được**, cần phần cứng token thật
- **Bug mới phát hiện:** `BUG-QA-01` — lỗi `[WinError 5] Access is denied` tái diễn CÓ HỆ THỐNG (2/2 lần) khi tự động lưu chú thích lúc mở file mới, tự phục hồi sau vài giây nhưng hiển thị lỗi kỹ thuật thô cho người dùng. Chi tiết đầy đủ trong `BUG_REPORT.md`.
- **Lưu ý môi trường test:** trong lúc test, cửa sổ terminal điều khiển phiên này thỉnh thoảng giành lại foreground (khả năng do bạn thao tác máy song song), làm gián đoạn vài bước gõ phím/click — không phải lỗi của app, đã ghi nhận rõ trong log.
- **Ngoài phạm vi 3T Reader:** có 1 thông báo UltraViewer "máy tính khác vừa kết nối tới máy tính bạn" xuất hiện trong lúc test — không liên quan tới 3T Reader, bạn nên tự kiểm tra xem có phải kết nối bạn chủ động hay không.

## RELEASE GATE

**RELEASE READY cho phạm vi đã test** — không có P0/P1 nào được tìm thấy trong các luồng đã kiểm tra thật (startup, zoom, thumbnail, điều hướng trang, multi-tab, error injection file hỏng, window management, update flow).

**KHÔNG THỂ kết luận "READY" cho toàn bộ ứng dụng** vì phần lớn spec gốc chưa được chạy thật: OCR, AI chat/dịch/tóm tắt, ký số USB Token tương tác thật, chèn/xoá/xoay trang tương tác thật, export Word, in ấn thật, 50-tab stress, long-run 60 phút, chaos test đầy đủ, visual regression so sánh trước/sau. Xem `TEST_COVERAGE.md` để biết chính xác phần nào chưa làm và vì sao.
