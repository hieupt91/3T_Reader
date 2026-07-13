# Báo cáo Đánh giá Bảo mật, Hạ tầng và Triển khai (Infrastructure & Security Audit)
*Ngày tạo: 03/07/2026*

Dựa trên phân tích toàn bộ mã nguồn liên quan đến hạ tầng, build script và file cấu hình của dự án 3T Reader, dưới đây là các phát hiện nghiêm trọng về bảo mật và quy trình phát triển.

## Tóm tắt Cấp độ (Executive Summary)
Dự án có **nhiều lỗ hổng bảo mật nghiêm trọng (Critical)** chủ yếu đến từ việc hardcode mật khẩu VPS, vô hiệu hóa kiểm tra SSH Host Key và để lộ file mật khẩu trên kho lưu trữ (repository). Tổng cộng có **32 vấn đề** được phát hiện:
- **Nghiêm trọng (Critical)**: 5
- **Cao (High)**: 9
- **Trung bình (Medium)**: 12
- **Thấp (Low)**: 6

---

## 1. Các Lỗi Nghiêm Trọng (Critical)

### INFRA-001 | Hardcode mật khẩu SSH VPS trong hàng loạt script
- **Vị trí**: Gần 13 file Python (ví dụ: `deploy_final.py`, `sftp_deploy.py`, `check_vps.py`, `patch_data_sudo.py`,...).
- **Mô tả**: Mật khẩu SSH `Congnghe3t` được hardcode dạng plaintext. Bất cứ ai có quyền đọc code đều có thể truy cập root vào máy chủ VPS thực tế.
- **Khắc phục**: 
  1. Gỡ bỏ toàn bộ mật khẩu cứng khỏi mã nguồn.
  2. Sử dụng chứng chỉ SSH Key thay vì Password.
  3. Sử dụng biến môi trường (Environment Variables) hoặc `.env` để quản lý credential.
  4. **BẮT BUỘC:** Đổi ngay mật khẩu VPS hiện tại vì đã bị lộ trong lịch sử Git.

### INFRA-002 | Để lọt file chứa mật khẩu (pass.txt) trên Git
- **Vị trí**: `pass.txt` (nằm ở thư mục gốc).
- **Mô tả**: File chứa trực tiếp chuỗi mật khẩu `Congnghe3t`. Dù có thể đã đưa vào `.gitignore`, file này vẫn đang tồn tại và có thể đã lọt vào lịch sử commit.
- **Khắc phục**: Xóa file `pass.txt`, sử dụng lệnh `git filter-repo` để xóa hoàn toàn khỏi lịch sử Git.

### INFRA-005 | Mật khẩu Sudo truyền qua luồng SSH Stdin dưới dạng Plaintext
- **Vị trí**: Nhiều file deploy (ví dụ: `deploy_final.py`, `patch_data_sudo.py`).
- **Mô tả**: Các script gửi lệnh `Congnghe3t\n` trực tiếp vào luồng stdin để chạy lệnh `sudo`. Mật khẩu SSH cũng chính là mật khẩu Root.
- **Khắc phục**: Cấu hình *passwordless sudo* trên VPS cho các lệnh cụ thể dùng để deploy, tránh việc phải truyền mật khẩu qua script.

---

## 2. Các Lỗi Rủi Ro Cao (High)

### INFRA-003 | Mã băm (Hash) của Admin Password bị đẩy lên Git
- **Vị trí**: `admin-config-update.json`.
- **Mô tả**: File này chứa password hash của Admin nhưng không được liệt kê vào `.gitignore` (chỉ có `admin-config.json` được chặn). Kẻ gian có thể brute-force offline.
- **Khắc phục**: Thêm file này vào `.gitignore` và đổi mật khẩu Admin mới.

### INFRA-004 | Vô hiệu hóa kiểm tra SSH Host Key
- **Vị trí**: Mọi script deploy (`StrictHostKeyChecking=no` hoặc `paramiko.AutoAddPolicy()`).
- **Mô tả**: Việc này khiến toàn bộ luồng deploy chịu rủi ro tấn công Man-in-the-Middle (MitM).
- **Khắc phục**: Cấu hình `RejectPolicy` cùng file `known_hosts` cứng để xác thực chính xác máy chủ VPS.

### INFRA-006 | Máy chủ VPS dev bind trực tiếp vào 0.0.0.0 không có xác thực
- **Vị trí**: `vps_server_temp.py`.
- **Mô tả**: Máy chủ Flask chạy ở chế độ dev (`0.0.0.0:5000`) và trả về các API không cần xác thực (unauthenticated).
- **Khắc phục**: Sử dụng Gunicorn/Uvicorn phía sau Nginx, thiết lập Rate Limit và API Key Auth.

### INFRA-007 | Xung đột phiên bản (Version Inconsistencies)
- **Vị trí**: `pyproject.toml`, `build_mac.sh`, `installer_script.iss`, `admin-config.json` v.v.
- **Mô tả**: Có tới 8 phiên bản khác nhau rải rác trong code (1.0.17, 1.0.18, 1.0.24...). Không có Single Source of Truth.
- **Khắc phục**: Đặt phiên bản ở MỘT nơi duy nhất (ví dụ: `version.py`) và viết script để đồng bộ khi build.

### INFRA-010 | Ứng dụng không được ký mã (Code Signing)
- **Mô tả**: Toàn bộ script build đều đang comment (vô hiệu hoá) phần ký mã. App Windows sẽ bị SmartScreen cảnh báo nguy hiểm, app macOS sẽ bị block.
- **Khắc phục**: Cần mua chứng chỉ OV/EV Code Signing và tích hợp lại lệnh signtool vào quy trình build.

### INFRA-017 & INFRA-019 | Quy trình Deploy nguy hiểm, dùng pkill và không có Rollback
- **Mô tả**: Script hot-reload VPS bằng cách `pkill` server cũ rồi chạy `nohup`. Nếu quá trình upload lỗi giữa chừng, server sẽ chết hẳn mà không có cơ chế tự phục hồi (Rollback).
- **Khắc phục**: Chuyển sang Docker container hoặc Systemd service, kết hợp Blue-Green deploy.

---

## 3. Các Lỗi Trung Bình & Thấp (Medium/Low)

1. **INFRA-008:** Xung đột thư viện giữa `requirements.txt` và `pyproject.toml` (ví dụ `pyttsx3`, `numpy`). Cần quy về một mối (`pyproject.toml`).
2. **INFRA-011:** Hardcode đường dẫn tuyệt đối (Absolute Paths) của tài khoản `HieuPC` trong các script deploy, làm khó cho việc dev trên máy khác.
3. **INFRA-013:** Có 2 file Inno Setup (`installer_script.iss` và file cũ trong thư mục `installer`) bị trùng lặp, dùng 2 AppId khác nhau dễ gây lỗi xung đột khi update.
4. **INFRA-014:** Installer của Windows tự ý ghi đè file association (`HKCR\.pdf`) ép người dùng mở bằng 3T Reader. Cần làm dưới dạng tùy chọn opt-in.
5. **INFRA-027:** API Server không encode HTML cho tên khách hàng khi xuất Email, tiềm ẩn nguy cơ XSS cho Admin.

---
*Vui lòng phối hợp với team DevOps / System Admin để tiến hành khắc phục ngay các lỗi Cấp độ Critical (đặc biệt là đổi mật khẩu).*
