# Windows Deployment Guide Phase 2

## Muc tieu

Ban Windows khong dong goi LibreOffice hoac iTaxViewer vao PyInstaller. App se tu tai module khi nguoi dung mo Word, Excel hoac XML lan dau.

## File module tren VPS

Thu muc public:

```text
https://reader.3tcomputer.com/downloads/modules/
```

File can co:

```text
modules_index.json
libreoffice_win.zip
itaxviewer_installer.exe
```

`modules_index.json` dang tro toi:

```json
{
  "libreoffice_win": {
    "name": "Bo xu ly Word/Excel (Windows)",
    "size": "200MB",
    "url": "libreoffice_win.zip"
  },
  "itaxviewer_win": {
    "name": "Bo xu ly File Thue XML",
    "size": "50MB",
    "url": "itaxviewer_installer.exe"
  }
}
```

## Yeu cau file libreoffice_win.zip

Sau khi giai nen, mot trong cac duong dan sau phai ton tai:

```text
program/soffice.exe
App/libreoffice/program/soffice.exe
```

Khong nen nen boc them thu muc cha ben ngoai. Code hien tai co fallback tim `soffice.exe` ben trong module, nhung cau truc phang van la chuan nhat.

## Noi cai module tren may khach

Windows:

```text
%APPDATA%\3T Reader\modules\libreoffice\
%APPDATA%\3T Reader\modules\itaxviewer\itaxviewer_installer.exe
```

File tam tai ve:

```text
%TEMP%\libreoffice_win.zip
```

Cach nay tranh loi duong dan co dau tieng Viet trong thu muc project hoac Desktop.

## Build PyInstaller

Khong them `libreoffice_win.zip`, `itaxviewer_installer.exe`, hoac thu muc `build_modules/` vao file `.spec`.

Build exe nhe nhu binh thuong:

```powershell
.\.venv313\Scripts\python.exe -m PyInstaller -y 3T_Reader.spec
```

## Checklist test Windows

1. Xoa module cu neu muon test lan dau:

```powershell
Remove-Item "$env:APPDATA\3T Reader\modules\libreoffice" -Recurse -Force
Remove-Item "$env:APPDATA\3T Reader\modules\itaxviewer" -Recurse -Force
```

2. Mo app va keo tha file `.docx` hoac `.xlsx`.
3. Dong y tai LibreOffice module.
4. Xac nhan thanh progress chay, module bung vao `%APPDATA%`, va file duoc convert sang PDF hop le.
5. Keo tha file `.xml`.
6. Keo tha XML se render thanh PDF va mo ngay trong 3T Reader. iTaxViewer chi dung lam module du phong khi can mo bang phan mem thue rieng.

## Loi thuong gap

`PDFium: Data format error`: file Word/Excel dang bi nap thang vao PDF viewer hoac LibreOffice tao PDF rong/hong. Code Phase 2 da chan loi nay bang cach convert non-PDF truoc khi goi PDFium va kiem tra magic header `%PDF`.

Khong tai duoc module: kiem tra public URL tra `200`:

```text
https://reader.3tcomputer.com/downloads/modules/libreoffice_win.zip
https://reader.3tcomputer.com/downloads/modules/itaxviewer_installer.exe
```
