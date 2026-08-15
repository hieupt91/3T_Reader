# 04 — Code Quality Report

## Error-handling anti-patterns

**Thống kê**: 207 khối `except Exception:` trong `app/`+`packages/`, **156/207 (75%) là `pass` im lặng** (nuốt lỗi không log, không báo user).

**Đánh giá sau khi mẫu kiểm tra kỹ** (`_pdf_save.py`, `sign.py`, `vps_client.py`, và các file khác trong audit này): phần lớn là fallback hợp lý (trả `None`/`[]`/giá trị mặc định cho thao tác không quan trọng, ví dụ đọc metadata tùy chọn) — **KHÔNG phải swallow nguy hiểm**. Không nên coi 156 con số này là "156 lỗi cần sửa" — đó sẽ là kết luận sai, phóng đại.

**Trường hợp cụ thể đã xác nhận nguy hiểm và ĐÃ SỬA trong phiên này**:
- `app/actions/auto_ocr.py:58` (cũ) — OCR nền bỏ qua lỗi từng trang hoàn toàn im lặng, không log, không báo user. **Đã sửa** (commit `c8a7c7a`): ghi audit log + báo tổng số trang lỗi qua status bar.

**Trường hợp còn tồn tại, mức độ thấp, không khẩn**:
- Lỗi `charmap codec can't encode character` (tiếng Việt) khi `print()` trên console cp1252 của Windows — cùng loại lỗi gặp lại nhiều lần trong chính phiên làm việc này (ở script deploy). Không gây crash toàn app, chỉ mất log/output tại chỗ gọi. Không ưu tiên trừ khi muốn dọn log sạch.

**Khuyến nghị**: không cần rà soát toàn bộ 156 chỗ còn lại — chi phí cao, giá trị thấp cho đa số. Nếu muốn tiếp tục, ưu tiên các `except: pass` nằm trên đường ghi dữ liệu quan trọng (save/sign) hoặc kiểm tra bảo mật (license validation) — các đường này đã được audit riêng và xác nhận sạch (xem `07_Security_Report.md`).

## Duplicate code

| Trùng lặp | File | Trạng thái |
|---|---|---|
| `class DownloadThread(QThread)` định nghĩa 2 lần độc lập, logic cancel/threading khác nhau | `document_converter.py`, `piper_tts_manager.py` | **Đã sửa 1 phần**: `document_converter.py` đã sửa cả 2 chỗ dùng (LibreOffice + iTaxViewer, commit `75ead6b`, `af91ad6`). `piper_tts_manager.py:322`'s `DownloadThread` **chưa rà** — nghi vấn tương tự A3 (nút "Đóng" không disable lúc đang tải) chưa xác nhận được là bug thật, để nguyên theo đúng quy tắc "không suy đoán sửa". |
| Logic gộp/xoay/tách PDF trùng giữa `annotate.py` và `pages.py`, 2 engine khác nhau | `app/actions/annotate.py`, `app/actions/pages.py` | Chưa sửa — xem `03_Architecture_Report.md` |
| 7 dialog AI/OCR/license/audit-log tự hard-code ~30-50 dòng QSS màu riêng thay vì lấy từ `styles/theme.py` | `ai_chat_dialog.py`, `ai_search_dialog.py`, `ai_summarize_dialog.py`, `ai_actions.py`, `audit_log_dialog.py`, `license_dialog.py`, `ocr_dialog.py` | Chưa sửa. **3/7 file có bug hiển thị thật** (xem `05_UI_UX_Report.md` §1), 4/7 còn lại chỉ là trùng lặp code không có tác động UX. |
| 2 stack HTTP client song song cho cùng loại việc (tải file) | `urllib.request` (`document_converter.py`) vs `requests` (`license_client/`, `updater/`) | Trùng lặp nhẹ, không phải bug — `requests` đã là dependency bắt buộc nên không có lý do dependency-footprint để giữ 2 stack. |

## Unused / dead code

Xem chi tiết đầy đủ ở `08_Dependency_Report.md` (phần dead-code gộp chung với dependency audit vì cùng 1 đợt điều tra). Tóm tắt:
- **Không tìm thấy** chỗ nào bypass helper ghi file chung `_pdf_save.py` bằng `os.replace()`/`shutil.move()` thô — tin tốt, xác nhận việc trung tâm hóa ghi file (fix A1 phiên này) không có lỗ hổng.
- **8 file asset SVG khả năng không dùng** (Medium confidence) — `delete.svg`, `image_insert.svg`, `redo.svg`, `sidebar_hide.svg`, `sidebar_show.svg`, `text_insert.svg`, `theme_dark.svg`, `theme_light.svg` trong `assets/`.
- Việc rà unused function một cách hệ thống trên 5 file lớn nhất **chưa hoàn thành** trong thời gian audit — không báo cáo kết quả "sạch" giả, để trống có chủ đích.

## Magic numbers / hardcoded strings

Không có audit hệ thống riêng cho mục này (ngoài phạm vi thời gian). Quan sát rải rác trong lúc đọc code cho các phần khác: timeout, TTL, kích thước batch đều là hằng số có tên rõ ràng ở đầu hàm/class (ví dụ `_tokens_cache_ttl_seconds`, `STALE_TEMP_MAX_AGE_SECONDS`) — không thấy pattern số ma thuật rải rác không tên, đây là điểm code quality tốt, không phải vấn đề.

Chuỗi tiếng Việt hardcode trực tiếp trong code (không qua `language_manager.py`) khá phổ biến trong các dialog/thông báo lỗi — đây là **có chủ đích**, không phải lỗi: nhiều thông báo lỗi kỹ thuật không cần đa ngôn ngữ hóa đầy đủ. Không đánh giá là code smell trong ngữ cảnh app này.

## Naming / encapsulation

Quy ước đặt tên nhất quán trong toàn bộ codebase: `_` prefix cho private, `snake_case` cho hàm/biến, `PascalCase` cho class — không phát hiện vi phạm đáng kể qua các file đã đọc trong toàn bộ audit này.

## Kết luận

Code quality tổng thể **khá tốt cho quy mô dự án** — vấn đề thật sự đáng kể nhất (silent OCR failure) đã được sửa trong phiên này. Nợ kỹ thuật còn lại (duplication, QSS lặp) là có thật nhưng không khẩn cấp, phù hợp đưa vào `13_Refactoring_Plan.md` cho đợt dọn dẹp có kế hoạch.
