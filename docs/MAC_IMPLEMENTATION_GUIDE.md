# Tổng hợp Dự án 3T Reader - Phase 1 (Bản Windows sang Mac)

## 1. Giới thiệu chung
Dự án 3T Reader (Phase 1) là một ứng dụng đọc và xử lý tài liệu PDF đa năng, hỗ trợ ký số điện tử, ký số USB Token chuẩn LTV, OCR, trợ lý AI và cơ chế tự động cập nhật (OTA Update).
Tài liệu này đóng vai trò hướng dẫn chi tiết dành cho **Team Mac** để đảm bảo bản Mac khi triển khai sẽ có **đầy đủ 100% tính năng và trải nghiệm tương đồng với bản Windows** hiện tại.

## 2. Kiến trúc và Giao diện UI
- **Framework cốt lõi**: Sử dụng **PySide6** (Qt6) làm engine render giao diện. Cần thiết kế thanh Ribbon (Tab bar) phía trên cùng giống hệt bản Win để tạo sự đồng nhất về mặt thương hiệu.
- **Theme**: Hỗ trợ giao diện sáng/tối tự động (Dark/Light Mode) thông qua thư viện `pyqtdarktheme` hoặc CSS/QSS tuỳ chỉnh.

## 3. Các chức năng chính cần đảm bảo trên Mac

### 3.1. Xem và thao tác tài liệu
- **PDF Viewer Engine**: Sử dụng thư viện `pypdfium2` (và `pikepdf`) để render các trang PDF mượt mà lên màn hình (Canvas). Cần hỗ trợ thu phóng (zoom), chuyển trang, hiển thị thumbnail.
- **Office Viewer**: Hỗ trợ người dùng mở xem trực tiếp các file `.docx` và `.xlsx`. Giải pháp: dùng `pdf2docx` / `openpyxl` để phân tích dữ liệu, sau đó kết xuất HTML và hiển thị qua `PySide6.QtWebEngineWidgets`.

### 3.2. Tính năng Ký số (Digital Signature)
Đây là module cốt lõi cực kỳ quan trọng, team Mac cần lưu ý thực hiện chính xác:
- **Ký bằng file mềm (PFX/P12)**: Sử dụng `pyHanko` để tạo chữ ký PAdES lên file PDF.
- **Ký bằng USB Token / Smartcard**: 
  - Bản Windows đang dùng Certificate Store mặc định qua CryptoAPI/SignerSignEx.
  - **Trên Mac**: Yêu cầu team Mac sử dụng thư viện `python-pkcs11` kết hợp module chia sẻ PKCS#11 (.dylib) của macOS Keychain, hoặc thư viện API native của macOS để có thể gọi chứng thư số từ thiết bị USB Token.
- **Tính năng LTV (Long-Term Validation) và TSA (Time-Stamping Authority)**:
  - Cho phép tích hợp Timestamp khi ký (thông qua TSA URL người dùng cấp).
  - Tích hợp bằng chứng thu hồi (CRL/OCSP response) vào bên trong file PDF để xác thực LTV.
  - Sử dụng module `pyhanko.sign.validation` và `pyhanko.network.requests` (Phải nạp đầy đủ trong file build để tránh lỗi `ModuleNotFoundError`).
- **Tuỳ chỉnh nhận diện chữ ký**: Hiển thị hình vẽ/logo con dấu, vùng kéo thả chữ ký, thông tin ngày giờ, lý do ký.
- **Ký hàng loạt (Batch Signing)**: Ký tự động danh sách nhiều file PDF tại một thư mục (cần xử lý đa luồng tốt trên Mac).

### 3.3. Tính năng In ấn ảo (Virtual Printing)
- Gọi hộp thoại máy in hệ thống.
- Cần có ProgressBar hiển thị tiến trình (Đang in trang 1 / N...). 
- Lệnh in xong (truyền tệp vào bộ đệm của CUPS thành công) phải tự động xoá hoàn toàn ProgressBar để tránh treo app. Trên Mac sử dụng module `QtPrintSupport` của PySide6.

### 3.4. Tính năng Nhận dạng ký tự quang học (OCR)
- Dùng `pytesseract` (trình bao bọc cho Tesseract OCR engine).
- **Yêu cầu trên macOS**: Yêu cầu người dùng hoặc trình cài đặt cung cấp gói `tesseract` và `tesseract-lang` (thường cài qua Homebrew `brew install tesseract tesseract-lang`). Trong bản build cuối, team Mac nên đóng gói thẳng các thư viện nhị phân (binary) tesseract vào trong lõi App Bundle để người dùng tải về là dùng được luôn không cần gõ lệnh cấu hình phức tạp.

### 3.5. Trợ lý Trí tuệ Nhân tạo (AI Assistant)
- Hỗ trợ trò chuyện đa nền tảng API: OpenAI (ChatGPT), Anthropic (Claude), Google (Gemini).
- App sẽ đọc văn bản trong PDF bằng `pdfplumber` hoặc `pypdfium2`, sau đó truyền ngữ cảnh cho AI để thực hiện lệnh: tóm tắt, dịch thuật, giải nghĩa...

### 3.6. Cơ chế tự động cập nhật (OTA Update)
- App tự động gọi đến file JSON từ backend server để kiểm tra bản mới.
- Format server cho Mac:
  ```json
  "update": {
    "mac_version": "1.0.0",
    "mac_url": "https://reader.3tcomputer.com/downloads/3T_Reader_v1.0.0.dmg",
    "mac_sha256": "...",
    "release_notes": "..."
  }
  ```
- **Xử lý lưu file log/download**: Khi tải file bản cập nhật hoặc ghi file log lỗi (`error_log.txt`), **tuyệt đối không ghi cứng (hardcode) vào thư mục Application**. Thay vào đó phải dùng thư mục Temp cục bộ an toàn `os.path.join(tempfile.gettempdir(), "tên_file")` để không bị macOS chặn quyền (PermissionError).

## 4. Danh sách Thư viện lõi (Dependencies)
Team Mac cần dùng file `requirements.txt` sau làm cơ sở chuẩn để đồng bộ thư viện:
- `PySide6==6.11.0`
- `pyqtdarktheme==0.1.7`
- `pypdfium2==5.7.0`
- `pikepdf==10.5.1`
- `pyHanko==0.34.1`
- `python-pkcs11==0.9.4`
- `cryptography==46.0.7`
- `Pillow==12.2.0`
- `requests==2.33.1`
- `pytesseract==0.3.13`
- `pdf2docx==0.5.13`
- `pdfplumber==0.11.9`
- `openpyxl==3.1.5`
- Các gói AI: `openai`, `anthropic`, `google-genai`, `keyring` (quản lý khoá bảo mật Keychain trên Mac).

## 5. Chú ý đặc biệt khi Đóng gói (PyInstaller / py2app)
Khi đóng gói thành ứng dụng macOS (`.app` rồi chuyển sang `.dmg`), team Mac cần cấu hình cẩn thận các import ẩn (hidden imports). Nếu thiếu, ứng dụng sẽ chạy lỗi trên máy khách:
- `pypdfium2`, `pikepdf`, `pyhanko`
- `pyhanko.network`, `pyhanko.network.requests`
- `PySide6.QtPrintSupport`, `PySide6.QtWebEngineWidgets`

*(Vui lòng tham khảo tệp `3T_Reader.spec` tại nhánh chính làm cơ sở cấu hình PyInstaller).*

---
**Chúc Team Mac hoàn thành việc chuyển đổi xuất sắc!** Mọi thắc mắc hãy tham khảo mã nguồn trực tiếp trong kho lưu trữ (Repository) này.
