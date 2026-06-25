# HƯỚNG DẪN SỬ DỤNG CHI TIẾT PHẦN MỀM 3T READER
*(Tài liệu đính kèm nộp Hồ sơ Bản quyền tác giả)*

## 1. GIỚI THIỆU PHẦN MỀM
**3T Reader** là phần mềm đọc, chỉnh sửa và ký số tài liệu PDF bảo mật đa nền tảng, được tích hợp trí tuệ nhân tạo (AI OCR) để nhận diện và xử lý văn bản tiếng Việt.

## 2. HƯỚNG DẪN CÀI ĐẶT
1. **Windows:** Chạy file `Setup_3T_Reader.exe` từ đĩa CD/USB hoặc tải từ trang chủ. Nhấn Next cho đến khi hoàn thành.
2. **macOS:** Mở file `3TReader.dmg`, kéo thả biểu tượng 3T Reader vào thư mục Applications.
3. **Kích hoạt:** Lần đầu mở phần mềm, hệ thống sẽ kết nối ngầm với Server VPS để xác thực bản quyền (Silent Authentication). Quá trình này diễn ra hoàn toàn tự động.

## 3. CÁC TÍNH NĂNG CƠ BẢN (VIEWER)
- **Mở tài liệu:** Kéo thả trực tiếp file PDF vào giao diện phần mềm, hoặc bấm tab **Home -> Open**.
- **Chế độ xem:** Sử dụng các nút trên thanh Ribbon để phóng to (Zoom In), thu nhỏ (Zoom Out), vừa màn hình (Fit Page).
- **Giao diện:** Bấm nút **Giao diện (Theme)** để chuyển đổi giữa chế độ Sáng (Light) và Tối (Dark mode).

## 4. CHỈNH SỬA VÀ CHÚ THÍCH (ANNOTATION & EDITING)
- **Công cụ chú thích:** Chọn tab **Công cụ (Tools)**, tại đây bạn có thể dùng Bút Highlight (bôi vàng chữ), Gạch chân (Underline), Gạch ngang chữ (Strikeout).
- **Thao tác trang:** Bấm chuột phải vào biểu tượng thu nhỏ (Thumbnail) bên trái để Xoay trang, Xoá trang hoặc Chèn trang trắng mới.
- **Sửa chữ trực tiếp (Edit Text):** 
  1. Bôi đen đoạn chữ cần sửa trên tài liệu.
  2. Bấm nút **"Sửa text gốc"** trên thanh công cụ.
  3. Một hộp thoại sẽ hiện ra cho phép bạn gõ chữ mới. Phần mềm sẽ tự động xóa chữ cũ và chèn chữ mới với font Unicode tương thích.

## 5. TÍNH NĂNG KÝ SỐ ĐIỆN TỬ BẢO MẬT (e-SIGN)
*(Lưu ý: Bạn cần cắm thiết bị USB Token chứa chứng thư số vào máy tính trước khi thực hiện).*
1. Chuyển sang tab **Bảo mật (Security)**.
2. Bấm nút **Ký số PDF (Sign)**.
3. Dùng chuột quét/kéo một hình chữ nhật trên tài liệu để chọn vị trí đặt con dấu/chữ ký.
4. Một cửa sổ kết nối PKCS#11 sẽ bật lên, chọn Chứng thư số của bạn.
5. Nhập mã PIN của USB Token và bấm xác nhận.
6. Hệ thống sẽ áp dụng chữ ký kèm Timestamp (dấu thời gian pháp lý) lên tài liệu và tự động lưu file.

## 6. SỬ DỤNG TRỢ LÝ AI (OCR VÀ DỊCH THUẬT)
1. Bấm vào nút **AI Assistant** ở góc phải màn hình.
2. Bấm **Chụp vùng OCR**, sau đó dùng chuột quét chọn một khu vực hình ảnh chứa chữ trên tài liệu PDF.
3. AI sẽ tự động phân tích (OCR) và trích xuất chữ viết trong hình ảnh ra dạng văn bản.
4. Bạn có thể ra lệnh cho Trợ lý AI: *"Dịch đoạn này sang tiếng Việt"* hoặc *"Tóm tắt nội dung này"*. Trợ lý sẽ phản hồi lại ngay lập tức.

## 7. ĐỌC VĂN BẢN THÀNH GIỌNG NÓI (TTS)
1. Bôi đen văn bản cần đọc.
2. Bấm nút **Phát âm thanh (Play)**.
3. Engine Piper tích hợp sẵn sẽ đọc văn bản bằng giọng nói tiếng Việt tự nhiên mà không cần kết nối Internet.

---
*Tài liệu này được soạn thảo bởi Phạm Trung Hiếu - Tác giả phần mềm 3T Reader.*
