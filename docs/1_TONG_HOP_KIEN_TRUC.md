# 1. TỔNG HỢP KIẾN TRÚC & TÌNH TRẠNG HIỆN TẠI

## Tổng quan dự án (3T Reader)
Dự án phần mềm đọc, chỉnh sửa và quản lý PDF do 3T Computer phát triển, nhắm tới việc cung cấp trải nghiệm mượt mà, chuyên nghiệp và tích hợp sẵn công nghệ AI/Ký số tiên tiến.

## Kiến trúc Core (Tech Stack)
- **Frontend (Giao diện):** PyQt5 + QWebEngine (nhúng Chromium) kết hợp với lõi PDF.js đã được tinh chỉnh sâu.
- **Backend xử lý file PDF:** `pikepdf` và `PyMuPDF` đảm nhiệm toàn bộ nghiệp vụ cắt/ghép/xoay/lưu/trích xuất trang và chữ.
- **Bảo mật & Ký số:** Sử dụng `pyHanko` để xử lý chữ ký số qua USB Token (PKCS#11) và file PFX, hỗ trợ cấp dấu thời gian (TSA) và xác thực dài hạn (LTV).
- **Hệ thống bản quyền:** Áp dụng thuật toán bất đối xứng Ed25519 bằng JWT Token. Backend FastAPI trên máy chủ (VPS) phát sinh token theo đơn hàng, client (PyQt) offline kiểm tra tính hợp lệ bằng khóa công khai.

## Điểm nhấn công nghệ đặc biệt
1. **Local HTTP Server:** Lách giới hạn bảo mật truy cập tệp nội bộ (CORS) của Chromium bằng cách dựng một HTTP Server ngầm siêu tốc trên Python để stream tệp PDF và assets trực tiếp vào WebEngine.
2. **Zero-reload Lazy Rotation:** Tận dụng `CSS Transform` để xoay giao diện PDF ngay tức thì (cả nội dung lẫn Thumbnail) trong 0 giây, đồng bộ với việc lưu đè file PDF dưới luồng chạy ngầm để bảo đảm trải nghiệm không bị đứt gãy.
3. **Chống Crash PDF.js:** Ép phẳng (flatten) các Signature Widget thành tem (Stamp Annotation) trước khi nạp vào WebEngine, giúp PDF.js không bị treo khi render các chứng thư số phức tạp.
