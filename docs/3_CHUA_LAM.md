# 3. DANH SÁCH CÁC HẠNG MỤC CHƯA LÀM (CẦN XỬ LÝ SẮP TỚI)

## 1. Về mặt Giao diện (Frontend)
- [ ] Tính năng "Khởi tạo nhanh ngầm" (Warm Standby): Tạm thời đã revert (bỏ qua) để giữ sự biệt lập và an toàn (1 tab - 1 tiến trình), nhưng về lâu dài có thể cần cân nhắc nghiên cứu lại để giảm thời gian load 1s lúc mở tệp mới.
- [ ] Hoàn thiện các công cụ Annotate phức tạp như: Polygon, Cloud, Đo lường khoảng cách (Measure tools) nếu khách hàng yêu cầu sâu.
- [ ] Rà soát lại việc khóa các tính năng UI (Freemium gating) cho chính xác theo chiến lược kinh doanh (Hiện tại app đang "mở toang" toàn bộ cho bản Free).

## 2. Về mặt Backend (Lõi Engine)
- [ ] Quản lý bộ nhớ tối ưu hơn cho các thiết bị RAM yếu khi người dùng mở nhiều Tab hoặc file quá lớn (> 500MB). Cần cân nhắc giải phóng resource thông minh (Garbage Collection).
- [ ] Kiểm tra tính đa nền tảng toàn diện: Hệ thống Windows đã hoàn thiện cực kỳ tốt, cần phía team MacOS kiểm chứng và đồng bộ độ mượt mà.

## 3. Hệ thống Cấp phép & VPS
- [ ] Trang Dashboard trên nền Web (Admin Panel) để quản trị viên (Admin) dễ dàng click chuột sinh Key, Duyệt đơn hàng thay vì dùng Script thủ công (Hiện logic backend đã có, chỉ thiếu Web Frontend Admin).
- [ ] Bảo mật chống decompile (chống dịch ngược mã nguồn Python) bằng các công cụ Obfuscation (như Cython, Nuitka, PyArmor) trước khi xuất file cài đặt (.exe) ra thị trường.
