# Chính Sách Bảo Mật — 3T Reader

**Cập nhật lần cuối: Tháng 5 năm 2026**  
**Nhà phát triển:** 3T Company  
**Liên hệ:** hieupt.qb@gmail.com

---

## 1. Dữ liệu chúng tôi thu thập

3T Reader thu thập lượng dữ liệu tối thiểu cần thiết để vận hành tính năng cấp phép:

| Loại dữ liệu | Mục đích | Lưu trữ |
|---|---|---|
| **Device fingerprint (mã hóa)** | Xác định thiết bị được cấp phép; không chứa thông tin cá nhân | Máy chủ VPS của 3T Company |
| **Phiên bản ứng dụng** | Kiểm tra tương thích và hỗ trợ kỹ thuật | Máy chủ VPS |
| **Tên hệ điều hành** | Hỗ trợ đa nền tảng (Windows/macOS) | Máy chủ VPS |
| **Thời gian kích hoạt / heartbeat** | Theo dõi hiệu lực license | Máy chủ VPS |

---

## 2. Dữ liệu chúng tôi KHÔNG thu thập

- **Nội dung file PDF** của bạn — không bao giờ được đọc, gửi, hay lưu trữ
- Tên file, đường dẫn file
- Nội dung văn bản bạn nhập vào
- Địa chỉ IP ở dạng thô (chỉ băm mã hóa nếu cần)
- Thông tin thẻ tín dụng hay thanh toán
- Dữ liệu sinh trắc học

---

## 3. Cách chúng tôi sử dụng dữ liệu

Dữ liệu thu thập chỉ được dùng để:
- Xác minh license key hợp lệ
- Giới hạn số thiết bị được kích hoạt theo gói mua
- Phát hiện và ngăn chặn việc chia sẻ license trái phép
- Hỗ trợ kỹ thuật khi khách hàng yêu cầu

Chúng tôi **không bán, cho thuê, hay chia sẻ** dữ liệu với bên thứ ba vì mục đích thương mại.

---

## 4. Lưu trữ dữ liệu trên thiết bị

3T Reader lưu trữ thông tin license cục bộ trên máy của bạn:
- **macOS:** Keychain (mã hóa bởi hệ điều hành)
- **Windows:** Windows Credential Manager hoặc file JSON mã hóa
- Dữ liệu này chỉ chứa token license — không chứa nội dung tài liệu

---

## 5. Bảo mật

- Giao tiếp với máy chủ VPS qua HTTPS (TLS 1.2+)
- Token license được ký bằng Ed25519 — không thể giả mạo
- Device fingerprint được băm trước khi gửi — không thể truy ngược ra phần cứng gốc

---

## 6. Quyền của người dùng

Bạn có quyền:
- **Xem** dữ liệu liên kết với license key của bạn: liên hệ hieupt.qb@gmail.com
- **Xóa** dữ liệu: hủy kích hoạt license trong app (menu License → Hủy kích hoạt) hoặc liên hệ chúng tôi
- **Chuyển** license sang máy khác: hủy kích hoạt máy cũ trước, sau đó kích hoạt máy mới

---

## 7. Thay đổi chính sách

Chúng tôi có thể cập nhật chính sách này. Phiên bản mới sẽ được thông báo qua tính năng kiểm tra cập nhật trong app và ghi rõ ngày hiệu lực.

---

## 8. Liên hệ

Mọi thắc mắc về bảo mật dữ liệu:  
**Email:** hieupt.qb@gmail.com  
**Sản phẩm:** 3T Reader — 3T Company
