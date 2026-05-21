# Hướng dẫn Build & Triển khai Windows — 3T Reader

## Yêu cầu môi trường

| Phần mềm | Phiên bản | Ghi chú |
|---|---|---|
| Python | 3.11 – 3.13 | Khuyến nghị 3.12. **Không dùng Python từ Microsoft Store** |
| Git | bất kỳ | Clone repo |
| Tesseract OCR | 5.x | Cài từ UB-Mannheim, thêm vào PATH |
| Visual C++ Runtime | 2015–2022 | Thường đã có; nếu thiếu tải từ Microsoft |
| Inno Setup | 6.x | Chỉ cần khi đóng gói `.exe` installer |

---

## Bước 1: Cài Python và môi trường ảo

```bat
# Tải Python 3.12 từ python.org (bản x64, Windows installer)
# Khi cài: TÍCH "Add Python to PATH"

python -m venv .venv
.venv\Scripts\activate
```

## Bước 2: Cài dependencies

```bat
pip install -r requirements.txt
# Hoặc dùng pyproject.toml:
pip install -e ".[build]"
```

> Lưu ý: `python-pkcs11` trên Windows cần `libpkcs11.dll` từ nhà sản xuất USB token (Safe**Net**, Vân tay...).  
> Nếu chưa có token, bỏ qua lỗi import — tính năng ký số sẽ ẩn tự động.

## Bước 3: Cài Tesseract OCR (tiếng Việt)

1. Tải installer từ: https://github.com/UB-Mannheim/tesseract/wiki  
   Chọn bản `tesseract-ocr-w64-setup-5.x.x.exe`
2. Khi cài, chọn thêm **"Vietnamese"** trong danh sách ngôn ngữ
3. Thêm vào PATH: `C:\Program Files\Tesseract-OCR`
4. Kiểm tra:
   ```bat
   tesseract --list-langs
   # Phải thấy: vie
   ```

## Bước 4: Chạy thử (dev)

```bat
.venv\Scripts\activate
python main.py
```

App sẽ mở với 30-day trial hoặc yêu cầu license key.

---

## Bước 5: Build file thực thi với PyInstaller

```bat
.venv\Scripts\activate

# Build cơ bản (thư mục dist\3T_Reader\)
pyinstaller 3T_Reader.spec --distpath dist\win --workpath build\win --noconfirm
```

Kết quả: `dist\win\3T_Reader\3T_Reader.exe` + toàn bộ dependencies.

### Spec file có sẵn

File `3T_Reader.spec` ở thư mục gốc đã cấu hình:
- `assets/` — icon, logo
- `third_party/pdfjs/` — PDF.js viewer
- Hidden imports: `pypdfium2`, `pikepdf`, `PySide6.QtPrintSupport`, `PySide6.QtWebEngineWidgets`

### Thêm Tesseract vào build (bundle không cần cài trên máy user)

Thêm vào `3T_Reader.spec` phần `datas`:

```python
import os, shutil

# Tìm tessdata trên máy build
TESS_DATA = r"C:\Program Files\Tesseract-OCR\tessdata"
datas += [(TESS_DATA, "tessdata")]

# Thêm tesseract.exe vào binaries (tùy chọn)
TESS_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
binaries += [(TESS_EXE, ".")]
```

Và trong `packages/ocr/engine.py`, đường dẫn tessdata sẽ tự phát hiện qua biến môi trường hoặc `sys._MEIPASS`.

---

## Bước 6: Đóng gói Installer với Inno Setup

1. Cài Inno Setup 6: https://jrsoftware.org/isdl.php
2. Tạo file `installer/windows/3T_Reader_Setup.iss`:

```iss
[Setup]
AppName=3T Reader
AppVersion=1.0.2
AppPublisher=3T Company
DefaultDirName={autopf}\3T Reader
DefaultGroupName=3T Reader
OutputDir=dist\win
OutputBaseFilename=3T_Reader_Setup_1.0.2
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "dist\win\3T_Reader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\3T Reader"; Filename: "{app}\3T_Reader.exe"
Name: "{commondesktop}\3T Reader"; Filename: "{app}\3T_Reader.exe"

[Run]
Filename: "{app}\3T_Reader.exe"; Description: "Mở 3T Reader"; Flags: nowait postinstall skipifsilent
```

3. Build installer:
```bat
iscc installer\windows\3T_Reader_Setup.iss
```

Kết quả: `dist\win\3T_Reader_Setup_1.0.2.exe`

---

## Bước 7: Ký số installer (tùy chọn)

Nếu có code signing certificate (`.pfx`):

```bat
signtool sign /f cert.pfx /p PASSWORD /fd sha256 /tr http://timestamp.digicert.com /td sha256 dist\win\3T_Reader_Setup_1.0.2.exe
```

---

## Cấu hình License Server

File cấu hình URL backend: trong `app/config.py` (hoặc env var `READER_LICENSE_URL`).

URL mặc định của VPS: cấu hình trong `packages/license_client/__init__.py`.

Để thay đổi cho build Windows:
```python
# app/config.py
LICENSE_API_URL = "https://your-vps-domain.com"
```

---

## Kiểm tra sau build

```bat
# Chạy thử trên máy sạch (không có Python)
dist\win\3T_Reader\3T_Reader.exe

# Kiểm tra license activation
# Nhập key: 3TR-E-XXXX-XXXX-XXXX
# App phải kết nối được VPS và activate thành công
```

---

## Checklist trước khi ship

- [ ] `python main.py` chạy OK trên Windows
- [ ] OCR tiếng Việt hoạt động (menu OCR → OCR trang hiện tại)
- [ ] License activation thành công với key thật
- [ ] PyInstaller build không lỗi missing module
- [ ] Installer `.exe` test trên máy Windows sạch
- [ ] Tesseract bundled hoặc hướng dẫn user cài riêng
- [ ] USB token ký số test (nếu tính năng ký số được bật)
