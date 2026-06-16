# 2. DANH SÁCH CÁC HẠNG MỤC ĐÃ HOÀN THÀNH (ĐẾN THỜI ĐIỂM HIỆN TẠI)

## 1. Giao diện & Trải nghiệm (UI/UX)
- [x] Tích hợp bộ Giao diện Sáng/Tối (Light/Dark Mode) đồng bộ với hệ thống.
- [x] Tạo thanh công cụ Ribbon chuyên nghiệp mô phỏng MS Office.
- [x] Tính năng "Zero-reload Rotation": Xoay trang PDF lập tức bằng CSS Transform mà không bị khựng hình (Đã fix lỗi đồng bộ cho cả Thumbnail bên cột trái).
- [x] Xóa bỏ lỗi viền trắng dọc mép giấy khi cuộn PDF trong chế độ Dark mode.
- [x] Tháo gỡ các khóa tính năng ảo (Freemium bypass) giúp mọi nút bấm hoạt động thông suốt.

## 2. Tính năng Nâng cao (Advanced Features)
- [x] **Trợ lý AI:** Tích hợp AI Chat với PDF, Dịch thuật, Tóm tắt toàn bộ tài liệu, Tìm kiếm ngữ nghĩa (Semantic Search).
- [x] **Nhận dạng văn bản (OCR):** Tích hợp engine Tesseract OCR, hỗ trợ tự động tải engine chạy ngầm mà không cần cài đặt bằng tay.
- [x] **Ký số toàn diện:**
  - Ký bằng USB Token qua thư viện chuẩn PKCS#11 (Dành riêng cho máy Windows).
  - Ký bằng file chứng thư số `.pfx`.
  - Ký tay và chèn con dấu công ty.
  - Tích hợp chuẩn LTV (Long-Term Validation) và TSA (Time-Stamping Authority).
  - Khắc phục triệt để lỗi crash giao diện PDF.js khi load các file chứa chữ ký số phức tạp (Bằng cách chuyển Widget thành Stamp).
- [x] **Ký lô (Batch Sign):** Tự động ký hàng trăm file PDF cùng lúc trong một thư mục.

## 3. Hệ thống máy chủ & Dữ liệu (Backend & Infra)
- [x] **API Cấp Key:** Code chuẩn FastAPI trên VPS. Logic tự động phát sinh mã đơn hàng (ORD-xxx) và cấp Key theo từng gói (3TR-E, 3TR-P, 3TR-B).
- [x] **Hệ thống check Update:** Cập nhật ngầm (Silent check update) và tự động tải file thực thi để nâng cấp phiên bản.
- [x] **Hệ thống gửi Email:** Tự động gửi Email cấp Key bản quyền cho khách hàng và thông báo cho Admin khi có đơn hàng mới.
- [x] Đã hoàn thiện script cài đặt và release bản build Windows `.exe`.
