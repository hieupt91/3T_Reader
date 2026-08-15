# HƯỚNG DẪN ĐỒNG BỘ VÀ PHÁT TRIỂN CHÉO (WIN & MAC)

Tài liệu này quy định các tiêu chuẩn kỹ thuật để đảm bảo Team Windows và Team macOS (Mac) có thể phát triển chung trên một cơ sở mã nguồn (codebase) mà không gây lỗi chéo, không làm hỏng môi trường của nhau, và tối ưu hóa việc sử dụng chung tài nguyên trên máy chủ (VPS).

---

## 1. NGUYÊN TẮC SỬ DỤNG TÀI NGUYÊN CHUNG TRÊN VPS

Những tài nguyên nào mang tính chất **Dữ liệu (Data)** hoặc **Cấu hình độc lập hệ điều hành** thì bắt buộc **DÙNG CHUNG** trên VPS để giảm tải dung lượng và dễ bảo trì:

✅ **Các tài nguyên dùng chung trên VPS:**
- **Gói ngôn ngữ (Language Packs):** Các file `.json` dịch thuật giao diện (UI) và menu.
- **Từ điển Offline:** Database `.json` dùng cho việc nhận diện từ vựng.
- **Mô hình AI / TTS (Text-to-Speech):** File cấu hình giọng nói (`index.json`) và các database mô hình trí tuệ nhân tạo dùng chung (ví dụ: `vivos.onnx.json`).

⚠️ **Quy tắc khi cung cấp link tải từ VPS:**
- **Không bao giờ dùng hardcode Localhost/IP nội bộ** (ví dụ: `http://127.0.0.1:8080/file.json`) trên file cấu hình của server.
- Đường dẫn (URL) lưu trên VPS nên dùng **Relative Path (Đường dẫn tương đối)** để Client tự ghép với `VPS_LICENSE_BASE_URL` của nó.
- Nếu phải dùng Absolute Path (Đường dẫn tuyệt đối), bắt buộc phải dùng domain chính thức (ví dụ: `https://reader.3tcomputer.com/downloads/...`).

---

## 2. NGUYÊN TẮC TÁCH BIỆT THƯ MỤC & BINARY (WIN vs MAC)

Những tài nguyên nào phụ thuộc chặt chẽ vào hệ điều hành (chứa file thực thi `.exe`, `.app`, file `.dylib` của Mac hay `.dll` của Win) thì bắt buộc phải **CHIA RIÊNG FOLDER** để tránh xung đột.

### A. Công cụ bên thứ ba (Third-party Binaries)
Bất kỳ bộ xử lý nào cần file thực thi (ví dụ: Piper TTS, Tesseract OCR), cần tuân thủ cấu trúc thư mục sau trong dự án:

```text
3T_Reader/
├── ...
├── bin_win/                 # CHỈ chứa file .exe, .dll cho Windows
│   ├── tesseract/
│   └── piper_bin/
├── bin_mac/                 # CHỈ chứa file thực thi, .dylib cho macOS
│   ├── tesseract/
│   └── piper_bin/
└── ...
```

**Cách gọi trong Code (Python):**
```python
import sys
import os
from pathlib import Path

def get_binary_path(tool_name: str) -> Path:
    base_dir = Path(os.getcwd())
    if sys.platform == "darwin":  # Nếu là Mac
        return base_dir / "bin_mac" / tool_name
    elif os.name == "nt":         # Nếu là Windows
        return base_dir / "bin_win" / tool_name
    else:
        return base_dir / tool_name
```

### B. Module mã nguồn đặc thù (Platform-specific Code)
Nếu có tính năng nào gọi quá sâu vào API của Hệ điều hành (ví dụ: Đọc file Registry trên Win, hoặc gọi AppleScript trên Mac), hãy tạo file riêng biệt thay vì dùng dồn dập các lệnh `if/else` trong một file duy nhất:

```text
app/
├── actions/
│   ├── system_utils_win.py  # Chứa code đặc thù Windows (ví dụ gọi pywin32)
│   ├── system_utils_mac.py  # Chứa code đặc thù macOS
│   └── system_utils.py      # Import các hàm từ win/mac tùy theo sys.platform
```

---

## 3. QUY TẮC XỬ LÝ ĐƯỜNG DẪN FILE (PATHING)

**Nghiêm cấm** việc cộng chuỗi đường dẫn thủ công bằng dấu `/` hoặc `\` vì Windows dùng dấu `\` trong khi Mac dùng `/`.

❌ **SAI (Sẽ gây lỗi gãy đường dẫn khi đổi OS):**
```python
# Sai hoàn toàn trên Windows
file_path = current_dir + "/static/dicts/vi_en.json" 

# Sai hoàn toàn trên Mac
file_path = current_dir + "\\static\\dicts\\vi_en.json"
```

✅ **ĐÚNG (Chạy mượt trên mọi hệ điều hành):**
Luôn sử dụng thư viện `pathlib` hoặc `os.path.join`.
```python
from pathlib import Path

# Cách 1 (Khuyên dùng):
file_path = Path(current_dir) / "static" / "dicts" / "vi_en.json"

# Cách 2:
import os
file_path = os.path.join(current_dir, "static", "dicts", "vi_en.json")
```

---

## 4. QUY TẮC CÀI ĐẶT THƯ VIỆN (DEPENDENCIES)

Cả hai Team sử dụng chung `requirements.txt`.
Tuy nhiên, một số thư viện chỉ cài được trên hệ điều hành này mà lỗi ở hệ điều hành kia.

**Giải pháp:** Sử dụng **Environment Markers** trong `requirements.txt`.

Ví dụ nội dung `requirements.txt`:
```text
PySide6==6.7.0
requests==2.31.0
pdfplumber==0.11.0

# Chỉ cài pywin32 nếu hệ điều hành là Windows
pywin32==306 ; sys_platform == 'win32'

# Chỉ cài thư viện x nếu hệ điều hành là macOS
pyobjc-core==10.2 ; sys_platform == 'darwin'
```

---

## TỔNG KẾT

1. **Dùng chung trên VPS:** Data, File dịch, Tệp cấu hình JSON, Database, Model AI.
2. **Chia riêng trong Code:** File Binary (`.exe`, `.dll`, `.dylib`), Code gọi API lõi của hệ thống.
3. **Mã nguồn (Code):** Viết duy nhất một source, dùng `pathlib` cho đường dẫn file và `sys.platform` để chia luồng nếu tính năng đó chạy khác nhau giữa Win và Mac.

Đề nghị các thành viên Team Win & Mac đọc kỹ và review code lẫn nhau dựa trên bộ tiêu chuẩn này!
