# Fix Rules

Quy ước khi xử lý từng lỗi trong giai đoạn này:

- Chỉ sửa đúng lỗi đang được báo.
- Không làm ảnh hưởng các tính năng khác.
- Không tự ý thêm cải tiến ngoài phạm vi lỗi, trừ khi bắt buộc để sửa tận gốc.
- Ưu tiên đọc kỹ đúng luồng code liên quan trước khi sửa.
- Khi xong phải báo rõ:
  - đã sửa file nào
  - phạm vi ảnh hưởng là gì
  - đã kiểm tra gì
- Mặc định không commit.
- Chỉ commit khi người dùng ghi rõ: `Xong lỗi này thì commit riêng.`

Mẫu nhắn ngắn cho mỗi lỗi:

`Lỗi số X: [mô tả lỗi]. Đọc FIX_RULES.md và làm theo.`
