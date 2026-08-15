# 05 — UI/UX Report

## N/A cho app desktop (điều chỉnh từ checklist gốc viết cho mobile/Flutter)

| Mục checklist gốc | Lý do N/A |
|---|---|
| Tablet issues | Không có khái niệm tablet cho app desktop Windows |
| Landscape issues | Không có khái niệm xoay màn hình |
| Touch targets | App điều khiển bằng chuột/bàn phím, không phải cảm ứng |
| Mobile gesture | Không áp dụng |

## Phát hiện

### [High] [Confidence: High] 3 dialog hard-code màu dark-mode, KHÔNG có nhánh light-mode — lỗi hiển thị thật

**File**: `app/license_dialog.py`, `app/ocr_dialog.py`, `app/audit_log_dialog.py` (xác nhận qua grep: 0 lần gọi `is_dark()` trong cả 3 file).

**Cơ chế lỗi**: cả 3 gọi `setStyleSheet()` không điều kiện với `QDialog { background: #16162A; }` + màu chữ sáng kiểu `#E8EEFF` — đúng bảng màu dark-mode dùng ở nơi khác trong app. So sánh với `app/ai_search_dialog.py:15` (`_build_style(dark: bool)`) — file này CÓ nhánh đúng cho cả 2 chế độ với cùng bảng màu gốc, cho thấy 3 file trên là copy-paste thiếu nửa sáng.

**Triệu chứng cụ thể user thấy được**: khi app đang ở Light mode (`styles/theme.py::apply_theme("light")`), mở 1 trong 3 dialog (License, OCR, Nhật ký hoạt động) sẽ hiện 1 bảng màu tối navy giữa giao diện sáng — lệch tông rõ rệt, trông như lỗi hiển thị, không chỉ là code trùng lặp.

**Phân biệt với phát hiện trùng lặp QSS khác**: đây là tập con (3/7) của phát hiện "7 dialog tự hard-code QSS thay vì dùng `styles/theme.py`" (xem `04_Code_Quality_Report.md`) — nhưng chỉ 3/7 này thực sự gây bug hiển thị, 4/7 còn lại chỉ là trùng lặp code không ảnh hưởng UX vì chúng CÓ nhánh dark/light đúng (dù code lặp).

### [Medium] [Confidence: Medium] `license_dialog.py:169` dialog kích thước cố định, rủi ro cắt nội dung lỗi động

**Bằng chứng**: `self.setFixedSize(480, 340 + extra_h)` — chiều rộng luôn 480px, chiều cao chỉ tăng cho vài trường hợp UI trial đã biết trước, không tăng theo độ dài text trạng thái. `self._status` (dòng 219-221) có `setWordWrap(True)` nhưng dialog không resize được — thông báo lỗi mạng/server dài, xuống dòng 3+ dòng ở độ rộng 480px có thể vượt chiều cao cố định, bị cắt, không có scroll dự phòng.

**Chưa xác minh trực quan** — cần trigger 1 thông báo lỗi dài thật và chạy app để xác nhận 100%.

### [Low] [Confidence: High] Không dùng Qt Accessibility API

**Bằng chứng**: `grep -rn "setAccessibleName|setAccessibleDescription"` trên `app/` + `packages/` → **0 kết quả**. 26 file dùng `setToolTip` (chỉ hỗ trợ 1 phần cho người dùng chuột nhìn thấy, không thay thế được screen reader). Không tìm thấy mnemonic bàn phím (`&` trước ký tự trong label menu) trong `addMenu`/`addAction` của `app/window.py`.

**Tác động**: người dùng dùng screen reader không nhận được tên có ý nghĩa cho các widget tùy chỉnh. Mức độ ưu tiên thấp cho sản phẩm hiện tại (thị trường VN, chưa có yêu cầu compliance accessibility rõ ràng được biết đến) nhưng đáng ghi nhận nếu có kế hoạch mở rộng thị trường sau này.

### [Informational — không phải bug] DPI scaling xử lý đúng phạm vi cần thiết

Chỉ có 1 chỗ custom-pixel-rendering trong toàn bộ codebase (`app/sidebar.py:131`, render thumbnail) và chỗ đó dùng đúng `devicePixelRatioF()`. Không tìm thấy `QPainter`/`QPixmap` vẽ tùy chỉnh nào khác cần tự xử lý DPI thủ công — Qt6/PySide6 tự scale widget chuẩn theo mặc định. **Mục này sạch, không cần đầu tư sửa.**

### [Informational] Hệ thống icon nhất quán

`assets/` + `styles/icon_colors.py` (module tô màu icon theo theme) cho thấy hệ thống icon có chủ đích, được bảo trì — không có bằng chứng lẫn lộn nhiều bộ icon khác phong cách.

### [Low] [Confidence: Low — cần kiểm tra runtime] `assets/js/pdfjs_ui_hooks.js` dựa nhiều vào `setTimeout` polling

12 lần gọi `setTimeout` trong 699 dòng, cộng 12 lần override CSS bằng `!important` — dấu hiệu điển hình của cách né race-condition DOM-readiness thay vì hook đúng sự kiện PDF.js. Chưa đọc sâu (giới hạn thời gian) — chỉ ghi nhận pattern, không khẳng định bug cụ thể.

### Không đánh giá được (cần chạy app + chụp màn hình, ngoài khả năng audit đọc code)

Overflow/cắt nội dung thực tế ở cửa sổ nhỏ, độ tương phản màu thật trong dark/light mode, độ mượt animation, màn hình empty-state thực tế — các mục này cần chạy app và quan sát trực quan. Ghi nhận là "chưa kiểm chứng" thay vì mặc định coi là ổn.

## Tổng kết

| Mức độ | Số lượng |
|---|---|
| High | 1 (3 dialog light-mode bug) |
| Medium | 1 (dialog fixed-size clip risk) |
| Low | 2 (accessibility, pdfjs_ui_hooks pattern) |
| Informational (đã kiểm tra, sạch) | 2 (DPI, icon system) |
| Không đánh giá được (cần runtime) | 4 mục |
