# BÁO CÁO ĐÁNH GIÁ KỸ THUẬT VÀ SỞ HỮU TRÍ TUỆ DỰ ÁN "3T READER"
*(Tài liệu phục vụ công tác làm Hồ sơ xin cấp bản quyền phần mềm và Đăng ký Nhãn hiệu)*

## I. THÔNG TIN TỔNG QUAN
- **Tên phần mềm / Nhãn hiệu đăng ký:** 3T Reader
- **Phiên bản hiện tại:** 1.1.0 (Cập nhật đa nền tảng Windows & macOS)
- **Tác giả / Chủ sở hữu:** Cá nhân Phạm Trung Hiếu
- **Nền tảng mục tiêu:** Đa nền tảng (Windows & macOS)
- **Ngôn ngữ và Công nghệ lõi:** Python, C++ (thông qua thư viện lõi), JavaScript/HTML/CSS (WebEngine)
- **Framework giao diện:** PyQt5 / PySide6 (Qt WebEngine)

## II. ĐÁNH GIÁ TÍNH ĐỘC SÁNG VÀ ĐẶC TRƯNG SỞ HỮU TRÍ TUỆ (USP)
Dự án "3T Reader" không chỉ là một ứng dụng đọc PDF thông thường mà là một hệ sinh thái xử lý tài liệu số toàn diện. Các yếu tố độc quyền và sáng tạo cấu thành nên quyền sở hữu trí tuệ bao gồm:

### 1. Kiến trúc Hybrid (Desktop - WebEngine) độc quyền
- **Cơ chế:** Kết hợp sức mạnh xử lý file nội bộ của Python/C++ (sử dụng `PyMuPDF`, `PyPDFium2`, `pikepdf`) và khả năng hiển thị UI siêu tốc của `PDF.js` thông qua cầu nối QWebChannel.
- **Tính độc sáng:** Tự động tiêm (inject) các mã JavaScript (`pdfjs_ui_hooks.js`) vào mã nguồn PDF.js để thay đổi hành vi mặc định, hỗ trợ cache vùng bôi đen (selection), nhận diện click vào đối tượng/văn bản và truyền dữ liệu real-time về lõi Python mà không làm nghẽn luồng giao diện.

### 2. Hệ thống Chỉnh sửa Văn bản Trực tiếp (Direct Text & Object Editing)
- **Cơ chế:** Sử dụng giải pháp "Redact & Insert" cực kỳ sáng tạo. Thay vì phải build lại toàn bộ cấu trúc CMap phức tạp của PDF, phần mềm trích xuất chính xác tọa độ, kích thước, font chữ, màu sắc của vùng chọn (Phase 7 - Selection payload timeout sync).
- **Tính độc sáng:** Xóa (redact) chính xác vùng text/object cũ, và sử dụng công nghệ chèn Text/Font Unicode tự động tương thích. Giữ nguyên độ mượt mà của thanh cuộn thông qua kỹ thuật `soft_reload`. Khả năng trích xuất PDF sang Word tự động thông qua Document Core Converter.

### 3. Trợ lý AI và Nhận diện Quang học (OCR AI)
- **Cơ chế:** Tích hợp mô hình ngôn ngữ lớn (LLM) và AI vào xử lý tài liệu.
- **Tính độc sáng:** Khả năng OCR chính xác dựa trên baseline AI mới nhất. Cho phép khoanh vùng text trong PDF hoặc ảnh chụp, sau đó AI tự động nhận diện chữ, tóm tắt, và dịch thuật thông minh ngay trong ứng dụng, biến 3T Reader thành một "trợ lý tài liệu" đúng nghĩa.

### 4. Đọc văn bản bằng Giọng nói (Text-To-Speech / TTS) với Piper
- **Tính độc sáng:** Không phụ thuộc hoàn toàn vào API bên thứ ba, tích hợp engine `piper-tts` chạy mượt mà trên cả máy tính Windows và macOS (Apple Silicon). Đọc tài liệu offline tự nhiên với các model âm thanh độc quyền hoặc tinh chỉnh.

### 5. Module Ký số Điện tử pháp lý (PKCS#11 / USB Token)
- **Tính độc sáng:** Tương tác trực tiếp ở tầng thấp với thiết bị phần cứng USB Token, trích xuất Chứng thư số (Certificate), hiển thị LTV (Long-Term Validation) và đóng dấu thời gian (Timestamp). Tính năng này là cốt lõi để cạnh tranh trực tiếp với khối doanh nghiệp và nhà nước tại Việt Nam.

### 6. Quản trị Bản quyền, Cập nhật ngầm (Silent Update) và Bảo mật (Obfuscation)
- **Tính độc sáng:** 
  - Toàn bộ mã nguồn quan trọng đều được mã hóa và chống dịch ngược (Obfuscate).
  - Kết nối bảo mật chuẩn xác với máy chủ VPS độc quyền (`admin-config.json`, hệ thống `vps_license_service`, `vps_order_service`).
  - Hệ thống tự động tải bản vá lỗi mới nhất và cập nhật ngầm mà không cần người dùng cài đặt lại (Auto Deploy & CI/CD workflow).

## III. TÍNH CHẤT ĐỦ ĐIỀU KIỆN ĐĂNG KÝ BẢN QUYỀN
**Để làm thủ tục cấp Giấy chứng nhận Đăng ký Quyền tác giả phần mềm, hồ sơ của 3T Reader đã đáp ứng đầy đủ:**
1. **Tính nguyên gốc:** Toàn bộ flow xử lý, cầu nối `ExistingTextBridge` / Payload sync, thuật toán phân tích Bounding Box (`app/pdf_text_editor.py`), engine PyMuPDF tùy biến (`packages/pdf_engine/pymupdf_engine.py`) và module chuyển đổi Office (`packages/document_core`) đều là kết quả lao động trí tuệ của cá nhân Phạm Trung Hiếu.
2. **Tính cố định:** Source code đã được định hình, xuất bản thành phiên bản thương mại `1.1.0` hoàn chỉnh.
3. **Phạm vi bảo hộ đề xuất:**
   - Bảo hộ mã nguồn (Source code) và thuật toán tích hợp lai (Hybrid Bridge).
   - Bảo hộ Giao diện người dùng (UI/UX Design) với hệ thống Ribbon và chế độ Dark/Light mode tự động đồng bộ hệ thống.
   - Bảo hộ quy trình Ký số và thuật toán Redact/Chỉnh sửa PDF thời gian thực.

## IV. TÍNH CHẤT ĐỦ ĐIỀU KIỆN ĐĂNG KÝ THƯƠNG HIỆU (NHÃN HIỆU)
- **Tên nhãn hiệu đề xuất:** `3T READER` (hoặc `3T Reader`)
- **Nhóm sản phẩm/dịch vụ (Nhóm 09 theo bảng phân loại Nice):** Phần mềm máy tính tải xuống được; phần mềm ứng dụng dùng cho máy tính; phần mềm xử lý, chỉnh sửa tài liệu PDF; phần mềm tích hợp trí tuệ nhân tạo (AI); phần mềm đọc văn bản (TTS).
- **Yếu tố phân biệt:** Khác biệt so với các phần mềm ngoại nhập (Foxit, Adobe) nhờ việc tùy biến sâu phù hợp cho thị trường Việt Nam (tích hợp USB Token tương thích hệ thống Thuế/Hải quan Việt Nam, đọc tiếng Việt tự nhiên bằng Piper, OCR tiếng Việt).

## V. KIẾN NGHỊ VÀ CÁC BƯỚC TIẾP THEO
1. **Hoàn thiện Hồ sơ:** In file Báo cáo này kẹp cùng tờ khai. Xuất thêm mã nguồn đại diện (50 trang đầu và 50 trang cuối của code) vào file `SOURCE_CODE_COPYRIGHT.txt`.
2. **Ảnh chụp Giao diện:** Cần chụp các màn hình:
   - Giao diện chính (Đọc PDF với Ribbon).
   - Giao diện thao tác Ký số (Nhập mã PIN USB Token).
   - Giao diện Trợ lý AI (OCR và Chat).
   - Giao diện Chỉnh sửa Văn bản trực tiếp.
3. **Pháp lý Nhãn hiệu:** Chuẩn bị Logo "3T Reader" rõ nét, kiểm tra tính trùng lặp trên thư viện tra cứu của Cục Sở hữu trí tuệ để nộp mẫu nhãn hiệu.
