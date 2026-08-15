# Báo cáo Phân tích Lỗi và Đề xuất Khắc phục Dự án 3T Reader
*Ngày tạo: 03/07/2026*

Dựa trên quá trình đánh giá mã nguồn dự án `3T_Reader_Phase1_Win` và file test case `Test Case 3T Reader.xlsx`, dưới đây là báo cáo phân tích chi tiết các lỗi đang tồn tại (trạng thái Fail) và đề xuất phương án kỹ thuật để khắc phục.

---

## 1. Nhóm Lỗi Giao Diện & Trải Nghiệm Người Dùng (UI/UX)

### Lỗi TC27: Thiếu nút xóa các nét annotation bôi vẽ (High)
* **Mô tả:** Người dùng không có cách dễ dàng (nút bấm trực quan) để xóa các nét tô sáng, gạch dưới, gạch ngang trên giao diện.
* **Nguyên nhân cốt lõi:** Hiện tại trên UI (PDF.js webview) thiếu sự kiện xử lý khi user click vào một annotation để bật popup/context menu hoặc nút Delete.
* **Đề xuất khắc phục:** 
  1. Thêm event listener vào layer chứa annotation trong PDF.js. 
  2. Khi người dùng click hoặc select annotation, hiển thị một `floating button` (biểu tượng thùng rác).
  3. Gắn callback cho button này gọi về backend Python thông qua WebChannel (ví dụ: `window.backend.deleteAnnotation(annotId)`).
  4. Backend xử lý xóa annotation trong core `pymupdf` và gửi lệnh re-render lại vùng đó.

### Lỗi TC28: Lỗi giữ màu bôi sáng khi tắt thanh tìm kiếm (Medium)
* **Mô tả:** Highlight tìm kiếm (Ctrl+F) không biến mất khi đã đóng thanh tìm kiếm hoặc xóa text.
* **Nguyên nhân cốt lõi:** Sự kiện đóng search panel không gọi API xóa các highlight spans trong DOM hoặc không gọi lệnh clear tìm kiếm của PDF.js.
* **Đề xuất khắc phục:** Trong sự kiện `close` của `search_panel.py` hoặc UI search box, cần gọi hàm JavaScript xóa highlight. Ví dụ: `web_view.page().runJavaScript("if (window.PDFViewerApplication) window.PDFViewerApplication.findController.executeCommand('find', {query: ''});")` để reset highlight.

### Lỗi TC29: Thiếu dấu hiệu nhận biết vùng ghi chú khi hover (Low)
* **Mô tả:** Rê chuột vào vùng ghi chú không có hiệu ứng nhận biết.
* **Nguyên nhân cốt lõi:** Thiếu CSS hover state cho lớp `.annotationLayer .textAnnotation` (hoặc tương tự).
* **Đề xuất khắc phục:** Bổ sung CSS vào file styles hoặc chèn trực tiếp qua Javascript. Ví dụ:
  ```css
  .annotationLayer section:hover {
      outline: 2px dashed #0078D7;
      cursor: pointer;
  }
  ```

---

## 2. Nhóm Lỗi Xử Lý Dữ Liệu & Hiệu Năng (Core/Performance)

### Lỗi TC30: Lỗi sửa text gốc hoạt động chập chờn (High)
* **Mô tả:** Tính năng sửa text có sẵn trong PDF hoạt động không ổn định.
* **Nguyên nhân cốt lõi:** Thuật toán nhận diện bounding box text (OCR hoặc PyMuPDF block parser) không ổn định trên các layout phức tạp, dẫn đến tính sai toạ độ và nội dung.
* **Đề xuất khắc phục:** 
  1. Tối ưu parser trong module `pdf_text_editor.py` hoặc `edit.py`. 
  2. Cần nhóm các ký tự (characters) thành từ (words) và dòng (lines) chính xác hơn dựa trên dung sai toạ độ y (y-tolerance).

### Lỗi TC31: Lỗi preview font chữ và in nghiêng (Medium)
* **Mô tả:** Chèn chữ bị mặc định in nghiêng, đổi font không tác dụng ngay ở bước preview.
* **Nguyên nhân cốt lõi:** Lỗi khởi tạo default style state trên Javascript (đang bị set italic = true) và lỗi binding sự kiện thay đổi font.
* **Đề xuất khắc phục:** Sửa logic frontend trong file JS quản lý text overlay. Khi user chọn font/style, phải update style `.fontFamily` và `.fontStyle` của đối tượng HTML preview ngay lập tức.

### Lỗi TC32: Lỗi đơ lag khi Undo nhiều nét vẽ (High)
* **Mô tả:** Hoàn tác nhiều nét vẽ liên tục gây đơ màn hình.
* **Nguyên nhân cốt lõi:** Mỗi lệnh Undo gọi API render lại toàn bộ trang PDF chất lượng cao, gây thắt nút cổ chai (bottleneck) tại luồng chính.
* **Đề xuất khắc phục:**
  1. Áp dụng kỹ thuật `Debounce` (chờ ~300ms) trước khi render lại trang.
  2. Nếu có thể, chỉ xóa đối tượng vẽ trên lớp canvas overlay thay vì render lại toàn trang từ backend, sau khi save mới apply thay đổi vật lý.

---

## 3. Nhóm Lỗi Quản Lý Trạng Thái & File (State/File Handling)

### Lỗi TC33 & TC34: Mất thumbnail và màn hình đen sau khi thao tác mật khẩu (Critical)
* **Mô tả:** Đặt mật khẩu làm biến mất thumbnail; Xóa mật khẩu gây màn hình đen.
* **Nguyên nhân cốt lõi:** Quá trình lưu file với encryption (mã hóa/giải mã) sinh ra file temp mới nhưng state của `PDFViewerWidget` chưa được cấp lại luồng file path mới hoặc không gọi `reload()`.
* **Đề xuất khắc phục:** Tại file xử lý mật khẩu (`document_ops.py`), sau khi tạo file temp và lưu thành công, phải gọi:
  ```python
  window.viewer.load_document(new_decrypted_path)
  window.sidebar.reload_thumbnails()
  ```

### Lỗi TC35: Tự động nén file ZIP khi xuất nhiều ảnh (Low)
* **Mô tả:** Xuất PDF sang ảnh sinh ra nhiều file lẻ tẻ.
* **Nguyên nhân cốt lõi:** Hàm xuất ảnh hiện đang vòng lặp và ghi file trực tiếp.
* **Đề xuất khắc phục:** Trong `export_pages_to_images` (`document_ops.py`), thêm logic đếm số lượng trang. Nếu `> 1`, sử dụng thư viện `zipfile` của Python gói các ảnh vào chung một file `.zip` rồi xóa các ảnh tạm.

### Lỗi TC37: Lỗi tắt chế độ luôn nổi (Float) mất lịch sử Chat PDF (Critical)
* **Mô tả:** Bật rồi tắt chế độ luôn nổi khiến nút tắt đơ và xóa lịch sử.
* **Nguyên nhân cốt lõi:** Chế độ luôn nổi (Float) thường destroy và recreate panel/window hoặc trigger reload iframe. Khi destroy, state không được lưu trữ.
* **Đề xuất khắc phục:** 
  1. Tách biệt State (lịch sử chat) khỏi View. Lưu context chat trong Python Backend (`packages/ai/chat_pdf.py`).
  2. Khi re-init window nổi hoặc panel, gửi lịch sử từ Backend lên Frontend để vẽ lại DOM.

### Lỗi TC38: Không tự động chạy OCR trước khi tóm tắt file ảnh (Critical)
* **Mô tả:** Báo lỗi không tìm thấy văn bản khi tóm tắt file scan.
* **Nguyên nhân cốt lõi:** Tính năng summarize chỉ lấy text layer. Nếu file scan, text layer trống rỗng.
* **Đề xuất khắc phục:** Trong luồng summarize (`ai_actions.py`), kiểm tra độ dài text lấy được. Nếu `< 50` ký tự (hoặc rỗng), bật cờ cảnh báo, hiển thị prompt hỏi user có muốn chạy OCR, hoặc auto gọi hàm OCR ngầm trước khi nạp vào AI.

---

## 4. Nhóm Lỗi Hiển Thị In Ấn & Nhận Diện Ký Tự

### Lỗi TC39 & TC40: Lỗi preview và chuyển trang trong giao diện In (Medium)
* **Mô tả:** Không chuyển được trang nếu xem 2 trang, preview in trang ngang không đổi hình ảnh.
* **Nguyên nhân cốt lõi:** Lỗi tính index trang hiện tại (lên +1 thay vì +2) trong chế độ dual-page. Không bắt sự kiện orientation change để cập nhật aspect ratio của preview box.
* **Đề xuất khắc phục:**
  1. Update hàm `next_page()` của trình in: `currentIndex += (isDualPage ? 2 : 1)`.
  2. Lắng nghe event thay đổi layout `Portrait/Landscape` trên UI, gửi tín hiệu reload preview với page transform xoay 90 độ hoặc request ảnh preview từ PyMuPDF ở chế độ ngang.

### Lỗi TC36: Thuật toán OCR nhận diện kém font phức tạp (Medium)
* **Mô tả:** Lỗi font khi nhận diện tài liệu có font lạ.
* **Nguyên nhân cốt lõi:** Tesseract mặc định gặp khó với nhiễu ảnh và font lạ.
* **Đề xuất khắc phục:**
  1. Nâng cấp bộ pre-processing ảnh trước khi OCR (chuyển Grayscale, tăng Contrast, Thresholding/Binarization bằng OpenCV).
  2. Đảm bảo model tiếng Việt `vie.traineddata` là phiên bản best/mới nhất của Tesseract.

---

## 5. Nhóm Lỗi Hệ Thống & License (Backend)

### Lỗi TC41: Lỗi sai lệch ngày kích hoạt License khi cài lại app (High)
* **Mô tả:** Gỡ cài đặt và active lại làm sai lệch ngày bản quyền so với quá khứ.
* **Nguyên nhân cốt lõi:** License server cấp phát ngày dựa trên "Ngày nhận request activate mới nhất" thay vì "Ngày kích hoạt lần đầu tiên" của key đó.
* **Đề xuất khắc phục:** Tại server (`main_api.py`, hàm `activate`), khi xử lý device mới, phải giữ nguyên trường `issued_at` của thiết bị đầu tiên kích hoạt gói hoặc lưu `first_activated_at` riêng cho key đó để dùng làm mốc tính `expires_at`.

---
*Báo cáo được tự động tạo dựa trên việc tổng hợp file test case và mã nguồn hệ thống.*
