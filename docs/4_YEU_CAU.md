# 4. DANH SÁCH YÊU CẦU CHO TƯƠNG LAI (BACKLOG & REQUIREMENTS)

## 1. Yêu cầu Kinh doanh (Business Requirements)
1. **Phát hành (Commercial Release):** Xây dựng trang web Landing Page thương mại (ví dụ `reader.3tcomputer.com`) để người dùng tự do truy cập, tham khảo bảng giá và tải phần mềm tự động.
2. **Khảo sát phản hồi khách hàng (Feedback Loop):** Tích hợp nút Góp ý trực tiếp trên phần mềm để người dùng có thể gửi report về hòm mail hỗ trợ kỹ thuật của team.
3. **Chính sách phân phối gói Doanh Nghiệp (B2B):** Thiết lập kịch bản cung cấp Key có seat_limit = 100+ cho các tổng công ty, và hướng dẫn họ cách thức kích hoạt.

## 2. Yêu cầu Kỹ thuật (Technical Requirements)
1. **Hoàn thiện Web Admin Portal:** Code thêm một trang giao diện trên VPS để giúp kỹ thuật viên của công ty không cần dùng lệnh Python mà vẫn xem được danh sách đơn hàng và thông số máy tính của khách hàng.
2. **Bảo mật phần mềm (Anti-piracy):**
   - Rút gọn file thực thi `.exe` và sử dụng PyInstaller mã hóa để chống dịch ngược mã nguồn.
   - Kiểm tra mã băm bảo mật SHA-256 thường xuyên sau mỗi lần tung bản cập nhật mới.
3. **Mở rộng Đa ngôn ngữ (i18n):** Mặc dù app đã hỗ trợ API nạp ngôn ngữ qua VPS (`LANGUAGE_PACK_BASE_URL`), cần thiết kế thêm các gói ngôn ngữ (Tiếng Nhật, Tiếng Hàn) theo chiến lược mở rộng thị trường.
4. **Hệ thống Plugin AI Tùy chọn:** Người dùng có thể trả thêm phí để nhúng OpenAI (GPT-4) hoặc các mô hình nội bộ tùy theo mức độ riêng tư của dữ liệu (thay đổi cấu hình API token).
