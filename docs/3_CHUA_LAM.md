# 3. DANH SÁCH CÁC HẠNG MỤC CHƯA LÀM (CẦN XỬ LÝ SẮP TỚI)

## 0. Việc treo sau đợt fix TC27–TC41 (06/07/2026)
- [ ] Tester retest 15 test case TC27–TC41 trên build mới theo checklist trong `docs/TESTER_BUG_REPORT_TC27_TC41.md`, cập nhật lại file `docs/Test Case 3T Reader.xlsx`.
- [ ] Deploy `vps_license_service.py` + `vps_models.py` lên VPS license để fix TC41 có hiệu lực (nhớ đặt `THREET_VPS_PASSWORD` trước khi chạy script deploy).
- [ ] Bảo mật hạ tầng còn lại (xem `BAO_CAO_BAO_MAT_HA_TANG.md`): **đổi mật khẩu VPS** (mật khẩu cũ đã từng nằm trong Git), xóa `pass.txt` khỏi lịch sử Git bằng `git filter-repo`, chuyển sang SSH key, bật host key verification trong các script deploy.
- [ ] Build bản Windows mới (installer + portable) từ nhánh này để bàn giao tester.

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
