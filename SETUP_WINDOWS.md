# Hướng dẫn cài đặt 3T Reader trên Windows

> **Dành cho:** Đội phát triển Windows  
> **Nhánh:** `phase1-mac`  
> **Yêu cầu:** Windows 10/11 (64-bit)

---

## 1. Cài đặt phần mềm cần thiết

### 1.1 Python 3.11 hoặc 3.12 (bắt buộc)

> ⚠️ **Không dùng Python 3.13 hoặc 3.14** — PySide6 6.11.0 và một số thư viện chưa hỗ trợ.

1. Tải Python 3.11.x từ: https://www.python.org/downloads/release/python-3119/  
   → Chọn **Windows installer (64-bit)**
2. Khi cài đặt, **tick vào ô "Add Python to PATH"** trước khi nhấn Install Now.
3. Kiểm tra:
   ```cmd
   python --version
   ```
   Kết quả phải hiện `Python 3.11.x` hoặc `Python 3.12.x`.

### 1.2 Git

1. Tải Git từ: https://git-scm.com/download/win
2. Cài với tùy chọn mặc định (Git Bash + Git CMD).
3. Kiểm tra:
   ```cmd
   git --version
   ```

### 1.3 Visual C++ Redistributable (nếu thiếu)

Một số thư viện như `python-pkcs11` và `pikepdf` cần MSVC runtime:

- Tải và cài: https://aka.ms/vs/17/release/vc_redist.x64.exe

### 1.4 Microsoft Visual C++ Build Tools (chỉ cần khi build từ source)

Nếu gặp lỗi "Microsoft Visual C++ 14.0 or greater is required" khi pip install:

1. Tải Build Tools tại: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Chọn **"Desktop development with C++"**
3. Cài và khởi động lại máy

---

## 2. Clone repository

Mở **Command Prompt** hoặc **Git Bash**, chạy:

```cmd
cd C:\
git clone https://github.com/hieupt91/3T_Reader.git
cd 3T_Reader
git checkout phase1-mac
```

Kiểm tra đang ở đúng nhánh:

```cmd
git branch
```

Phải thấy `* phase1-mac`.

---

## 3. Tạo môi trường ảo (Virtual Environment)

```cmd
cd C:\3T_Reader
python -m venv .venv
```

Kích hoạt môi trường ảo:

```cmd
.venv\Scripts\activate
```

Dấu nhắc sẽ thay đổi thành `(.venv) C:\3T_Reader>`.

> 💡 **Lưu ý:** Mỗi lần mở terminal mới phải chạy lại `.venv\Scripts\activate`.

---

## 4. Nâng cấp pip

```cmd
python -m pip install --upgrade pip
```

---

## 5. Cài đặt thư viện

### 5.1 Cài các thư viện chính

```cmd
pip install PySide6==6.11.0
pip install pyqtdarktheme==0.1.7
pip install pypdfium2==5.7.0
pip install pikepdf==10.5.1
pip install reportlab==4.4.5
pip install pyHanko==0.34.1
pip install python-pkcs11==0.9.4
pip install cryptography==46.0.7
pip install Pillow==12.2.0
pip install requests==2.33.1
```

Hoặc cài tất cả một lần từ `requirements.txt`:

```cmd
pip install -r requirements.txt
```

### 5.2 Cài thư viện xuất Word/Excel và chỉnh sửa PDF

Tất cả thư viện cần thiết đã có trong `requirements.txt` (pikepdf, pdfplumber, pdf2docx, openpyxl...).  
Chạy lệnh `pip install -r requirements.txt` ở bước trên là đủ.

Kiểm tra nhanh:

```cmd
python -c "import pikepdf, pdfplumber, pdf2docx, openpyxl; print('OK')"
```

> **Lưu ý:** App **không dùng PyMuPDF/fitz** (thư viện AGPL). Tất cả thao tác PDF đều dùng `pikepdf` + `pypdfium2` + `pdfplumber`.

### 5.3 Cài PyKCS11 (tùy chọn — chỉ cần cho USB Token)

```cmd
pip install PyKCS11==1.5.18
```

---

## 6. Cài đặt package nội bộ (core & packages)

Dự án có các package riêng trong thư mục `packages/` và `core/`. Cài chúng theo cách editable:

```cmd
pip install -e .
```

Nếu lệnh trên báo lỗi thiếu `build`, thử:

```cmd
pip install build
pip install -e .
```

---

## 7. Chạy ứng dụng

```cmd
python main.py
```

Ứng dụng sẽ khởi động với cửa sổ chào mừng 3T Reader.

---

## 8. Cấu trúc thư mục quan trọng

```
3T_Reader/
├── main.py                  # Điểm khởi chạy
├── app/
│   ├── window.py            # Cửa sổ chính
│   ├── pdf_viewer.py        # Trình xem PDF (PDF.js + WebEngine)
│   ├── pdf_inline_editor.py # Chèn text/ảnh inline kiểu Foxit
│   ├── actions/
│   │   ├── edit.py          # Hành động chèn text, ảnh, vẽ
│   │   └── sign.py          # Hành động ký số
│   ├── welcome_widget.py    # Màn hình chào mừng
│   └── about_dialog.py      # Hộp thoại giới thiệu
├── assets/
│   ├── logo_mark.svg        # Logo icon 3T Reader
│   ├── logo_full.svg        # Logo đầy đủ
│   └── icons/               # Biểu tượng toolbar
├── core/                    # Module xử lý lõi
├── packages/                # Package nội bộ
│   └── qt_compat/           # Lớp tương thích PySide6
├── styles/                  # CSS/QSS giao diện
└── pyproject.toml           # Cấu hình dự án
```

---

## 9. Xử lý lỗi thường gặp

### Lỗi: `No module named 'pikepdf'` hoặc `No module named 'pdfplumber'`

Chưa cài đủ thư viện. Chạy:

```cmd
pip install -r requirements.txt
```

### Lỗi: `No module named 'PySide6'`

Chưa kích hoạt virtual environment. Chạy:

```cmd
.venv\Scripts\activate
```

### Lỗi: `qt.webenginecontext` / WebEngine không khởi động

Một số máy Windows cần cài thêm:

```cmd
pip install --upgrade PySide6-WebEngine
```

Hoặc kiểm tra `QtWebEngineWidgets` đã có trong PySide6 package chưa:

```cmd
python -c "from PySide6.QtWebEngineWidgets import QWebEngineView; print('OK')"
```

### Lỗi: `error: Microsoft Visual C++ 14.0 or greater is required`

Cài Microsoft C++ Build Tools (xem mục 1.4).

### Lỗi: `DLL load failed` khi import pikepdf hoặc cryptography

Cài Visual C++ Redistributable (xem mục 1.3).

### Lỗi: `No module named 'pkcs11'` (python-pkcs11)

`python-pkcs11` trên Windows có thể cần compile. Nếu gặp lỗi, cài từ wheel:

```cmd
pip install python-pkcs11==0.9.4 --only-binary :all:
```

Nếu không có wheel, có thể tạm bỏ qua nếu chưa cần tính năng USB Token.

### Lỗi: `No module named 'qdarktheme'`

```cmd
pip install pyqtdarktheme==0.1.7
```

### Màn hình trắng / PDF không hiển thị

WebEngine cần `QTWEBENGINE_DISABLE_SANDBOX=1` trên một số máy:

```cmd
set QTWEBENGINE_DISABLE_SANDBOX=1
python main.py
```

Để cố định, thêm vào đầu `main.py`:

```python
import os
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
```

---

## 10. Cấu hình USB Token (ký số)

### Yêu cầu

- Driver của nhà cung cấp USB Token (VD: SafeNet, VNPT-CA, Viettel-CA)
- File `.dll` của PKCS#11 (thường là `eTPKCS11.dll` hoặc `vnpt_pkcs11.dll`)

### Cấu hình đường dẫn PKCS#11

Trong file `config.json` (tạo nếu chưa có tại thư mục gốc):

```json
{
  "pkcs11_lib": "C:\\Windows\\System32\\eTPKCS11.dll"
}
```

Hoặc set biến môi trường:

```cmd
set PKCS11_LIB=C:\Windows\System32\eTPKCS11.dll
```

---

## 11. Cập nhật code từ Mac team

Khi Mac team push code mới lên `phase1-mac`:

```cmd
git fetch origin
git pull origin phase1-mac
```

Nếu có thư viện mới được thêm vào `pyproject.toml`:

```cmd
pip install -r requirements.txt
```

---

## 12. Liên hệ & báo lỗi

- **Repository:** https://github.com/hieupt91/3T_Reader
- **Nhánh chính:** `phase1-mac`
- **Email:** hieupt.qb@gmail.com

---

*Cập nhật lần cuối: 2026-05-21 | Nhánh: phase1-mac*
