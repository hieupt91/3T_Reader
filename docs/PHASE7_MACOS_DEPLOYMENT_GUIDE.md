# Hướng dẫn Triển khai Phase 7 (macOS Parity)

Tài liệu này tổng hợp toàn bộ các thay đổi kiến trúc và luồng xử lý đã được triển khai trên bản Windows cho **Phase 7: Export PDF sang Word** và **Sửa chữ/ảnh gốc trên PDF**. Team macOS vui lòng đối chiếu và cập nhật các thành phần tương ứng để đạt tính năng tương đương.

---

## 1. Tính năng Export PDF sang Word (.docx)

### Luồng Xử lý Backend (Python)
- **Thư viện lõi**: Sử dụng thư viện `pdf2docx` (lớp `Converter`).
- **Xử lý đa luồng (Background Processing)**:
  - Để tránh treo UI trong lúc export (quá trình convert thường mất thời gian), bản Win sử dụng `QThread`.
  - Tệp: `packages/document_core/export_runner.py`
  - Lớp `PdfToWordExportRunner(QThread)`: 
    - Khởi tạo với đường dẫn `pdf_path` và `docx_path`.
    - Phát ra các tín hiệu: `progress(int, str)` (tiến độ), `finished(str)` (hoàn thành), `error(str)` (lỗi).
    - Bên trong `run()`: Khởi tạo `cv = Converter(pdf_path)`, gọi `cv.convert(docx_path)` và sau đó `cv.close()`.

### Tích hợp UI
- **Menu/Nút Export**: Tệp `app/actions/export.py` bắt sự kiện click.
- Hiển thị hộp thoại `QFileDialog` để người dùng chọn nơi lưu file Word.
- Hiển thị hộp thoại `QProgressDialog` (Progress Bar) lắng nghe tín hiệu `progress` từ luồng chạy nền, tự động đóng khi nhận được tín hiệu `finished`.

**Nhiệm vụ cho macOS**:
- Kiểm tra xem app macOS đã có lớp chạy nền `ExportRunner` (sử dụng GCD hoặc `NSThread`) tương tự chưa.
- Tích hợp gọi lệnh `pdf2docx` chạy ngầm, cập nhật thanh tiến trình lên UI macOS.

---

## 2. Tính năng Chỉnh sửa Nội dung Gốc (Existing Text/Object Editor)

Tính năng này cho phép người dùng click trực tiếp vào văn bản gốc của file PDF để chỉnh sửa (xóa/sửa chữ, giữ nguyên font, cỡ chữ).

### 2.1. Cầu nối Javascript (PDF.js) -> Python
Khi người dùng bấm nút "Sửa nội dung gốc":
1. Bật chế độ `window.__3tExistingTextMode = true` trên JS.
2. Tại `assets/js/pdfjs_ui_hooks.js`, thêm sự kiện `pointerdown` toàn cục để bắt sự kiện click vào các thẻ `span` thuộc class `.textLayer`.
3. **Lấy Tọa độ (CRITICAL)**:
   - Dùng `getBoundingClientRect()` của thẻ `span` và trang (page container).
   - Lấy `scale` hiện tại của PDF.js (`window.PDFViewerApplication.pdfViewer.currentScale`).
   - Tọa độ gửi đi: `vx = (spanRect.left - pageRect.left) / scale`.
   - Trục Y lấy từ mép trên xuống: `vy = (spanRect.top - pageRect.top) / scale`.
   - *Lưu ý*: Vì PDF.js đã điều chỉnh tỉ lệ từ 72dpi sang CSS pixels (thông qua scale), `vx` và `vy` trả về **chính là tọa độ PDF points (72dpi)** tại gốc tọa độ top-left. Không được nhân thêm bất kỳ scale factor nào (như 72/96).
4. **Lấy Thuộc tính Font**:
   - Dùng `window.getComputedStyle(span)` để lấy `fontFamily`, `fontSize`, `fontWeight`, và `color`.
   - Đóng gói thành chuỗi JSON `styleJson` và gửi qua Bridge: `reportExistingTextClick(pageNum, vx, vy, vw, vh, text, styleJson)`.

### 2.2. Xử lý Bridge và UI trên Python
- Tệp `app/webchannel.py` và `app/actions/edit.py` đăng ký Object `ExistingTextBridge` nhận tín hiệu.
- Ngay khi nhận được `reportExistingTextClick`:
  1. Parse `styleJson` để lấy font size, color. *Lưu ý*: JS thường trả về `rgb(X, Y, Z)`, cần chuẩn hóa màu thành tuple float từ `0.0 - 1.0` (VD: `R/255.0`).
  2. Bật hộp thoại `QInputDialog` để người dùng nhập text mới thay thế (hoặc để trống nếu muốn xóa dòng).

### 2.3. Logic Redaction (Xóa dòng cũ)
- Tệp: `app/pdf_text_editor.py` -> hàm `true_redact_area`.
- **Luồng xử lý**:
  - Nhận tọa độ `bbox = (left, top, right, bottom)` theo chuẩn PyMuPDF (top-left origin, điểm pt).
  - Khai báo `rect = fitz.Rect(*bbox)`.
  - **Mở rộng box (Fix lỗi xóa sót)**: `rect = rect + (-2, -2, 2, 2)` để quét dư 2 point mỗi viền, đảm bảo đè trúng hoàn toàn chữ gốc bị sai lệch bounding box tí xíu.
  - Áp dụng xóa: `page.add_redact_annot(rect, fill=(1,1,1))` và `page.apply_redactions()`.
  - Cập nhật trực tiếp lên file `base_snapshot`.

### 2.4. Render chèn chữ mới (PyMuPDF Engine)
- Tệp: `packages/pdf_engine/pymupdf_engine.py`
- Do `base_snapshot` đã bị thủng 1 lỗ (bởi hàm Redaction), ta cần chèn text mới đè lên lỗ đó và ghi vào `working_file`.
- **Font Unicode (Fix cho PyMuPDF 1.24+)**:
  - Tuyệt đối không truyền trực tiếp `fontfile=...` vào hàm `insert_text` vì PyMuPDF sẽ rơi chữ tiếng Việt (ra lỗi Mojibake/ô vuông).
  - **Bắt buộc** gọi `page.insert_font(fontname=font_hash, fontfile=font_path)` trước để nạp map Unicode CID.
  - Đưa tên `font_hash` vào `font_kwargs = {"fontname": font_hash}`.
- **Xử lý nền & vẽ chữ**:
  - Ước tính chiều rộng dòng chữ mới: `width = len(text) * (fontsize * 0.55)`. Vẽ đè hộp `draw_rect` màu nền lên để đảm bảo phủ hết tàn tích.
  - Chèn chữ: Gọi `rc = page.insert_textbox(rect, text, ...)`.
  - **Fallback Cực kỳ Quan trọng**: Nếu chiều cao của `rect` quá hẹp (không chứa đủ line height), `insert_textbox` sẽ trả về giá trị `< 0` (Thất bại âm thầm). Nếu xảy ra, phải fallback bằng:
    ```python
    page.insert_text(fitz.Point(rect.x0, rect.y1), text, ...) # Y1 là điểm baseline (cạnh dưới của box)
    ```
- **Force Reload Viewer**: Sau khi render xong `working_file`, gọi hàm ép PDF.js load lại file đó `reload_document(..., temp_path=working_file)`.

---

## 3. Các Lỗi Dễ Gặp & Cách Khắc phục (Troubleshooting)

1. **Lỗi "Tọa độ redact lệch, xóa không trúng chữ"**:
   - *Nguyên nhân*: Nhân thừa tỉ lệ. Javascript đã chia cho `currentScale` nên đã là tọa độ 72dpi. Đừng nhân thêm tỉ lệ màn hình ở backend.
   - *Fix*: Nhận `vx, vy, width, height` và dùng thẳng làm PyMuPDF Box.
   
2. **Lỗi "Gõ xong chữ biến mất hoàn toàn"**:
   - *Nguyên nhân 1*: Mã màu truyền vào PyMuPDF là số nguyên `(0, 0, 0)` hoặc `(255, 255, 255)`. PyMuPDF yêu cầu float `0.0 -> 1.0`. Nếu truyền Int, PyMuPDF văng Exception ngầm và không render chữ.
   - *Nguyên nhân 2*: Khung bao chữ (`bbox` lấy từ JS) quá dẹp. `insert_textbox` bị lỗi `-3`. Bắt buộc phải có luồng fallback sang `insert_text(Point)`.
   - *Nguyên nhân 3*: Font tiếng Việt không được Embed bằng `insert_font`, dẫn đến chữ có dấu bị loại bỏ, text chuỗi trắng không in ra.

Team macOS vui lòng đối chiếu luồng và các logic biên (edge cases) cực kỳ phức tạp này để đảm bảo MacOS tương đồng 100% với Window. Cảm ơn!
