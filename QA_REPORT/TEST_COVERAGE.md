# Test Coverage — đối chiếu với spec gốc (28 mục)

Ký hiệu: DONE (đã test thật) / PARTIAL (test rút gọn quy mô) / BLOCKED (thử nhưng không xác nhận được do giới hạn công cụ) / NOT TESTED (chưa làm, có lý do)

| # | Mục trong spec gốc | Trạng thái | Ghi chú |
|---|---|---|---|
| 4 | Tự phát hiện app đã cài | DONE | Tìm thấy `C:\Program Files\3T Reader\3T_Reader.exe`, version 1.0.34.3 |
| 5 | Full GUI discovery | PARTIAL | Đã inventory ribbon/toolbar welcome screen + view tài liệu; chưa quét hết toàn bộ menu con (Bảo mật, Chữ ký số, OCR, AI, License...) |
| 6-7 | Test mỗi control 10 kiểu, icon stress 20 lần | PARTIAL | Chỉ làm sâu cho: Zoom (15x), Thumbnail toggle (21x), Trang sau (30x). Các icon khác (Lưu, Xoá trang, Rotate, Export, In...) CHƯA test lặp |
| 8 | Multi-tab extreme (5→50 tab) | PARTIAL | Chỉ mở tới 2 tab. Không mở rộng lên 10/20/30/50 vì rủi ro tiếp tục đụng phải "Gần đây" MRU list chứa file cá nhân nhạy cảm khi cần nhiều file nguồn hơn |
| 9 | Heavy document test | NOT TESTED | Chưa tìm/tạo file PDF thật sự nặng (nhiều trăm trang / nhiều ảnh lớn) trong phiên này |
| 10 | Random real-user simulation | NOT TESTED | Chưa chạy — ưu tiên thời gian cho systematic test trước |
| 11 | Chaos test (click khi loading, đóng dialog giữa thao tác...) | PARTIAL | Chỉ có 1 case tự nhiên: gõ search ngay sau khi mở thanh tìm kiếm |
| 12 | Long-run test (T+10m/30m/60m) | NOT TESTED | Không đủ thời gian phiên làm việc để chạy 60 phút theo dõi liên tục |
| 13 | Visual regression before/after | PARTIAL | Có chụp trước/sau cho zoom, thumbnail, page nav, maximize nhưng không có bước so sánh pixel-diff chính thức, chỉ quan sát bằng mắt |
| 14 | Window stress | PARTIAL | Đã test Maximize, Minimize, Restore. CHƯA test resize kéo tay nhỏ/lớn, fullscreen |
| 15 | Keyboard test | PARTIAL | Đã test Ctrl+F (mở đúng, gõ bị BLOCKED), Ctrl+O, Ctrl+W, Esc. CHƯA test Ctrl+P, Ctrl+S, Ctrl+Z, Tab/Shift+Tab, Arrow keys, Ctrl+A/C/V |
| 16 | Error injection | PARTIAL | Đã test file hỏng (`corrupt_file.pdf`) — PASS. CHƯA test: file không tồn tại, input rỗng/quá dài trong các form khác, ký tự đặc biệt trong search |
| 17-18 | Crash detection + reproduction | N/A | Không gặp crash nào trong phiên test để phải reproduce |
| 20 | Performance baseline | PARTIAL | Có đo startup time (~2.36s) và 1 snapshot resource sau stress (~448MB RAM). Không có đủ mốc trước/sau để tính degradation |
| 21 | Regression sau stress (restart + chạy lại workflow) | NOT TESTED | Chưa restart lại app sau stress để chạy lại full regression |

## Các luồng nghiệp vụ lớn CHƯA test tương tác thật trong phiên này

- OCR (chọn vùng, nhận diện)
- AI chat / tóm tắt / dịch thuật trong app
- Ký số USB Token thực tế (nhập PIN, chọn token) — vùng này vừa fix bug #20, khuyến nghị test tay ưu tiên cao
- Chèn ảnh/text, xoay, xoá trang qua GUI thực tế (vừa fix bug #21/#22) — khuyến nghị test tay ưu tiên cao
- Đánh số trang qua GUI thực tế (vừa fix bug #23) — khuyến nghị test tay ưu tiên cao
- Export sang Word, In thật (không chỉ mở dialog)
- License activation flow

**Lý do chung cho các mục NOT TESTED/PARTIAL:** phạm vi spec gốc quá lớn so với 1 phiên làm việc thực tế (được nêu rõ với người dùng trước khi bắt đầu), và giới hạn công cụ automation (không có UI Automation tree do elevation, phải click theo toạ độ pixel từ screenshot — chậm và cần xác minh lại toạ độ liên tục khi layout đổi).

**Khuyến nghị:** 4 bug vừa fix (token USB, chèn ảnh, xoá trang, đánh số trang) nằm đúng trong nhóm "chưa test tương tác thật" ở trên — nên ưu tiên test tay các luồng này trước khi coi là release-ready toàn diện, vì đây chính là vùng vừa sửa code.
