# Windows Setup

Tài liệu này dành cho người mới vào `phase1-win` hoặc người cần dựng lại môi trường Windows để chạy, test, build và bàn giao nhanh.

Nếu bạn chỉ cần một điểm vào ngắn, mở [../SETUP_WINDOWS.md](../SETUP_WINDOWS.md) trước, rồi quay lại tài liệu này để xem chi tiết setup/build/test.

## 1. Mục tiêu của Windows stream

Windows stream hiện đã vượt mức prototype. Mục tiêu thực tế của nhánh này là:

- chạy app ổn định trên Windows
- mở / xem / tìm kiếm / in PDF
- hỗ trợ tab, recent files, thumbnail sidebar
- PDF rendering qua PDF.js trong local HTTP server
- build được PyInstaller và Inno Setup
- detect USB token / PKCS#11
- ký số với token thật khi có middleware nhà cung cấp
- giữ UI đủ trực quan để người dùng thao tác thật

## 2. Tính năng hiện có

### Viewer

- Mở PDF
- Tab nhiều tài liệu
- Recent files
- Sidebar thumbnail trang
- Ẩn/hiện cột trang
- Đi tới trang, trang trước/sau
- Zoom in/out
- Reset zoom về `100%`
- Vừa trang
- Fullscreen
- Tìm kiếm văn bản trong PDF.js
- Thông tin tệp

### Chèn / Sửa

- Chèn text
- Chèn ảnh
- Chọn/Sửa object đã chèn
- Xóa object đã chèn
- Hoàn tác / Làm lại
- Chỉnh vị trí, kích thước, xoay
- Text hỗ trợ tiếng Việt, in đậm, gạch chân
- Ảnh được stage tạm để không phụ thuộc path gốc
- Object đã chèn vẫn còn chọn được sau khi rebuild / zoom / reload

### Ký số

- Detect USB token
- PKCS#11 scan theo thư mục phổ biến trên Windows
- Hỗ trợ override bằng `THREET_READER_WINDOWS_PKCS11_PATHS`

### Build / Packaging

- PyInstaller onedir output ở `dist\3T_Reader`
- Inno Setup output ở `build\installer`
- Installer dùng mutex `Local\3T_Reader_SingleInstance_v1`

## 3. Yêu cầu môi trường

- Windows 10/11
- Python 3.12
- Git
- PyInstaller
- Inno Setup Compiler
- Nếu test ký số thật: middleware của USB token

## 4. Lấy code

Nếu chưa có repo:

```powershell
git clone https://github.com/hieupt91/3T_Reader.git
cd 3T_Reader
git checkout phase1-win
```

Nếu đã có repo:

```powershell
cd D:\3T_Reader_Phase1_Win
git checkout phase1-win
git pull origin phase1-win
```

## 5. Cài dependency

Khuyến nghị dùng Python 3.12:

```powershell
py -3.12 -m pip install -U pip
py -3.12 -m pip install -e .
py -3.12 -m pip install -e .[build]
```

Nếu repo không dùng extras build trên máy của bạn, cài theo `requirements.txt` hoặc `pyproject.toml` tương ứng.

## 6. Chạy app từ source

```powershell
cd D:\3T_Reader_Phase1_Win
& "C:\Users\3T COMPANY\AppData\Local\Programs\Python\Python312\python.exe" .\main.py
```

Hoặc nếu đang ở `cmd`:

```cmd
cd /d D:\3T_Reader_Phase1_Win
"C:\Users\3T COMPANY\AppData\Local\Programs\Python\Python312\python.exe" .\main.py
```

## 7. Kiểm tra nhanh trong app

- `Tệp > Mở tệp`
- `Xem > Giao diện > Theo hệ thống / Sáng / Tối`
- `Xem > Cột trang`
- `Công cụ > Tìm kiếm`
- `Công cụ > Chèn text`
- `Công cụ > Chèn ảnh`
- `Công cụ > Chọn/Sửa`
- `Công cụ > Xóa nội dung`

## 8. Ký số trên Windows

Để app tìm được DLL vendor:

```powershell
set THREET_READER_WINDOWS_PKCS11_PATHS=D:\Tokens\vendor.dll;E:\CA\PKCS11
```

Gợi ý:

- ưu tiên để app tự scan mặc định trước
- chỉ dùng biến môi trường khi cần ép đường dẫn vendor DLL
- test thực tế trên máy có middleware thật của nhà cung cấp

## 9. Smoke test

```powershell
py -3.12 -m pytest -q tests/test_smoke_platform.py
```

Kết quả hiện tại trên máy này:

- `26 passed, 1 skipped`

## 10. Build Windows

### PyInstaller

```powershell
py -3.12 -m PyInstaller 3T_Reader.spec
```

### Inno Setup

```powershell
ISCC installer_script.iss
```

Output dự kiến:

- `dist\3T_Reader`
- `build\installer\Setup_3T_Reader_v1.0.2.exe`

## 11. Release checklist

Trước khi coi Windows stream xong:

- smoke test pass
- packaged app mở được
- installer build pass
- token thật đã test
- signing flow đã đi qua máy Windows thật
- UI edit không còn gây hiểu nhầm ở toolbar

## 12. Files nên đọc tiếp

- [PHASE1_WIN_STATUS.md](PHASE1_WIN_STATUS.md)
- [PHASE1_WIN_HANDOFF.md](PHASE1_WIN_HANDOFF.md)
- [WORKFLOW_CONVENTION.md](WORKFLOW_CONVENTION.md)
- [README.md](../README.md)
