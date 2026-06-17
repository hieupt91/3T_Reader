# BẢN MÔ TẢ PHẦN MỀM (SOFTWARE DESCRIPTION DOCUMENT)
*(Tài liệu đính kèm Hồ sơ đăng ký bản quyền tác giả)*

## 1. THÔNG TIN CHUNG
- **Tên phần mềm:** 3T Reader
- **Phiên bản:** 1.0.7
- **Tác giả / Chủ sở hữu:** Công nghệ 3T (3T Computer)
- **Nền tảng hỗ trợ:** Windows & macOS (Đa nền tảng)
- **Ngôn ngữ lập trình:** Python (PyQt5/PySide6)
- **Mục đích:** Đọc, chỉnh sửa, Ký số điện tử bảo mật (USB Token/PKCS#11) và tích hợp Trợ lý AI OCR cho tài liệu PDF.

## 2. KIẾN TRÚC VÀ CÔNG NGHỆ CỐT LÕI
Phần mềm được thiết kế theo kiến trúc Modular, tách biệt giao diện và lõi xử lý:
- **Giao diện người dùng (UI/UX):** Sử dụng hệ thống giao diện Ribbon kiểu mới (giống Microsoft Office) kết hợp công nghệ QtWebEngineCore, đem lại trải nghiệm mượt mà, hỗ trợ Dark/Light Theme đồng bộ với Hệ điều hành.
- **Lõi xử lý PDF (Core Engine):** Sử dụng PyPDFium2 và PikePDF để thao tác nhanh gọn trên các file PDF dung lượng lớn (render tốc độ cao, trích xuất, ghép/xoá trang).
- **Module Ký số Điện tử (PKCS#11):** Giao tiếp trực tiếp với các trình điều khiển phần cứng USB Token, cho phép ký số pháp lý e-Sign có hiển thị con dấu (Timestamp, LTV) một cách an toàn nhất.
- **Module Trợ lý AI & OCR:** Tích hợp mô hình AI LLM tiên tiến để nhận diện ký tự quang học (OCR) thông minh, hỗ trợ dịch thuật và tóm tắt văn bản.

## 3. CÁC TÍNH NĂNG CHÍNH ĐƯỢC BẢO HỘ
**3.1. Tính năng Đọc & Xem tài liệu (Viewer)**
- Hiển thị mượt mà các file PDF với dung lượng lớn.
- Khung nhìn đa cửa sổ (Tabbed View), giao diện Ribbon trực quan.
- Chế độ đọc Night Mode / Light Mode, hiển thị Thumbnail thu nhỏ.

**3.2. Tính năng Chỉnh sửa & Chú thích (Annotation & Editing)**
- Xoay trang (Rotate CW/CCW) và lưu giữ vị trí chuẩn xác kể cả sau khi thao tác.
- Chèn trang trắng (Insert blank page), xóa trang (Delete page).
- Highlight văn bản, gạch chân (Underline), gạch ngang (Strikeout), vẽ tự do, chèn hình khối (Polygon/Measure).

**3.3. Tính năng Ký số Bảo mật (Digital e-Signature)**
- Đây là tính năng độc quyền cho phép phần mềm giao tiếp với USB Token và PKCS#11 driver trên cả Windows và macOS.
- Cho phép người dùng dán ảnh con dấu, tự động lấy chứng thư số từ thiết bị phần cứng để ký điện tử hợp pháp lên tài liệu PDF.
- Hiển thị đầy đủ thông tin Certificate (Valid, Revoked, Timestamp).

**3.4. Tính năng Quản trị Bản quyền (License Management)**
- Giao tiếp bảo mật với hệ thống máy chủ VPS để xác thực khóa bản quyền (License Key).
- Cơ chế chống dịch ngược (Obfuscation) kết hợp luồng khóa đa luồng (Multi-threading).
- Tự động nhận diện bản cập nhật và tải ngầm (Silent Update) từ server.

## 4. HƯỚNG DẪN SỬ DỤNG CƠ BẢN
1. **Khởi động:** Nháy đúp biểu tượng `3T Reader` trên màn hình. App sẽ tự động kiểm tra giấy phép qua Server VPS.
2. **Mở file:** Kéo thả file hoặc chọn File -> Open. Có thể đặt làm ứng dụng mặc định (Default App) để mở trực tiếp.
3. **Ký số:** Chuyển sang Tab "Bảo mật", cắm USB Token vào máy, chọn "Ký số PDF", vẽ vùng cần ký, nhập mã PIN và xác nhận.
4. **Trợ lý AI:** Bấm vào nút AI bên góc phải, quét khối văn bản cần OCR hoặc Tóm tắt, Trợ lý sẽ hiển thị kết quả ngay trên màn hình.

---
*Cam kết: Mã nguồn phần mềm này hoàn toàn do đội ngũ Công nghệ 3T (3T Computer) tự phát triển và sở hữu hợp pháp.*
