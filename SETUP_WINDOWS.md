# SETUP WINDOWS

Windows team chỉ cần clone repo, mở file này, rồi đi theo thứ tự dưới đây.

## 1. Clone và checkout

```powershell
git clone https://github.com/hieupt91/3T_Reader.git
cd 3T_Reader
git checkout phase1-win
```

Nếu repo đã tồn tại:

```powershell
cd D:\3T_Reader_Phase1_Win
git checkout phase1-win
git pull origin phase1-win
```

## 2. Đọc tài liệu đúng thứ tự

1. [README.md](README.md)
2. [docs/setup_windows.md](docs/setup_windows.md)
3. [docs/PHASE1_WIN_STATUS.md](docs/PHASE1_WIN_STATUS.md)
4. [docs/PHASE1_WIN_HANDOFF.md](docs/PHASE1_WIN_HANDOFF.md)

## 3. Những gì team Windows cần kiểm tra ngay

- mở PDF
- PDF.js render
- tab / recent files / thumbnail sidebar
- zoom / fit / fullscreen
- tìm kiếm
- chèn text / chèn ảnh / sửa / xóa object
- USB token / PKCS#11
- build PyInstaller
- build Inno Setup
- packaged app launch

## 4. Bộ branding / UX cần có cho stream Windows

### Logo & Branding

- `assets/logo_mark.svg`
- `assets/logo_full.svg`
- icon app trên dock/taskbar lấy từ `logo_mark.svg`

### Welcome screen

- `app/welcome_widget.py`
- hiện khi chưa mở file
- logo lớn
- feature cards
- nút `Mở tệp PDF`
- tự đổi dark/light theo theme

### About dialog

- `app/about_dialog.py`
- dialog `Giới thiệu 3T Reader`
- header gradient navy
- logo đầy đủ

### Toolbar

- logo 3T + chữ `3TReader` ở góc trái
- icon chèn text là chữ `A`
- icon chèn ảnh là khung hình
- icon SVG mới cho highlight, rotate, ký số, redact, v.v.

### Inline editor

- `app/pdf_inline_editor.py`
- chèn text/ảnh trực tiếp lên canvas PDF
- object sau khi chèn vẫn kéo được, resize được, xoay được
- không được “chết cứng” sau khi chèn

## 5. Release rule

- đừng tag `phase1-win-ready` cho tới khi token thật và signing thật đã qua
- docs phải đồng bộ với code
- UI phải trực quan, không để người dùng đoán trạng thái

## 6. File setup chi tiết

Nếu cần hướng dẫn setup/run/build/test Windows đầy đủ, mở:

- [docs/setup_windows.md](docs/setup_windows.md)

