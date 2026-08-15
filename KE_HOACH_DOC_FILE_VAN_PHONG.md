# KẾ HOẠCH PHÁT TRIỂN TÍNH NĂNG "TRÌNH ĐỌC MỞ RỘNG" (ON-DEMAND MODULES)

Mục tiêu: Cho phép 3T Reader mở và đọc nhanh các file **Hình ảnh (JPG/PNG), Word (DOCX), Excel (XLSX), Thuế (XML)** mà không làm phình to dung lượng bộ cài đặt ban đầu. Sử dụng cơ chế "Hỏi & Tải Module" từ VPS khi người dùng thao tác lần đầu tiên.

---

## 1. PHẦN VIỆC TRÊN MÁY CHỦ (VPS ADMIN)
Cần tạo một thư mục chuyên chứa các Module phụ trợ trên VPS (Ví dụ: `/downloads/modules/`) và chuẩn bị các file sau:

1. **`libreoffice_win.zip`**: Bản LibreOffice Portable rút gọn dành cho Windows (khoảng 150-200MB).
2. **`libreoffice_mac.zip`**: Bản LibreOffice Portable rút gọn dành cho macOS.
3. **`itaxviewer_installer.exe`**: File cài đặt iTaxViewer chuẩn của Tổng cục Thuế dành cho Windows.
4. **`modules_index.json`**: File cấu hình chứa link tải của các module trên. (Tương tự như danh sách giọng đọc TTS).

*Định dạng `modules_index.json` (tham khảo):*
```json
{
  "libreoffice_win": {
    "name": "Bộ xử lý Word/Excel (Windows)",
    "size": "200MB",
    "url": "libreoffice_win.zip"
  },
  "libreoffice_mac": {
    "name": "Bộ xử lý Word/Excel (macOS)",
    "size": "250MB",
    "url": "libreoffice_mac.zip"
  },
  "itaxviewer_win": {
    "name": "Bộ xử lý File Thuế XML",
    "size": "50MB",
    "url": "itaxviewer_installer.exe"
  }
}
```

---

## 2. PHẦN VIỆC CỦA TEAM MAC (TEAM HIỆN TẠI ĐANG CODE)
Team Mac sẽ chịu trách nhiệm viết toàn bộ Core Logic (Xử lý hệ thống) cho tính năng này. Cụ thể:

1. **Module Đọc Ảnh (Tích hợp sẵn, KHÔNG CẦN TẢI):** 
   - Code chức năng tự động biến file `.jpg`, `.png` thành file PDF (ẩn trong bộ nhớ) thông qua thư viện `Pillow` (đã có sẵn trong `requirements.txt`). Bấm là mở xem ngay lập tức.
2. **Xây dựng `ModuleManager`:** 
   - Code một hộp thoại (UI) hiện lên hỏi khách hàng: *"Tính năng này cần tải Module mở rộng (Dung lượng: XYZ). Bạn có muốn tải không?"*
   - Xây dựng luồng tải file `.zip` từ VPS về và tự động giải nén vào thư mục chuẩn (`bin_win` hoặc `bin_mac`).
3. **Viết trình thông dịch (Converter):** 
   - Viết hàm truyền lệnh ẩn `soffice --headless --convert-to pdf` vào LibreOffice để nặn ra file PDF khi khách kéo thả file Word/Excel.
   - Code tự động bắt file `.xml` và hiển thị gợi ý tải/cài đặt iTaxViewer.

---

## 3. PHẦN VIỆC CỦA TEAM WIN
Sau khi Team Mac code xong và đẩy lên Git, Team Win có nhiệm vụ:

1. **Đóng gói Module Windows:**
   - Cài đặt và rút gọn phần mềm LibreOffice phiên bản Windows thành một cục `libreoffice_win.zip` (Xóa bớt các mục ngôn ngữ thừa, font thừa để dung lượng nhẹ nhất có thể). Tải lên VPS.
   - Chuẩn bị file cài đặt `iTaxViewer`.
2. **Kiểm thử (Testing) trên Win:**
   - Kéo code (Pull) mới nhất từ nhánh Git về.
   - Nắm kéo một file Word thả vào 3T Reader. Kiểm tra xem hộp thoại tải Module có hiện lên không? Thanh quá trình tải có chạy mượt không?
   - Sau khi tải xong, phần mềm có tự động bung nén vào thư mục `bin_win/libreoffice` và mở file Word lên thành công hay không?

---

## 4. LUỒNG TRẢI NGHIỆM NGƯỜI DÙNG CUỐI (USER FLOW)
1. Khách hàng thả file `.docx` vào phần mềm.
2. App phát hiện đây là file Word, kiểm tra trong thư mục `bin_win` hoặc `bin_mac` chưa có LibreOffice.
3. App hiển thị bảng: *"Cần tải bộ xử lý Word/Excel (200MB)"*. Khách bấm "Tải về".
4. App hiện thanh tiến trình tải. Tải và giải nén xong.
5. App chớp nhẹ màn hình -> File Word hiển thị lên sắc nét 100% y như bản in, hỗ trợ bôi đen, dịch thuật, ký số v.v...
6. Các lần sau kéo file Word vào, App không hỏi nữa mà mở lên ngay trong 2-3 giây.
