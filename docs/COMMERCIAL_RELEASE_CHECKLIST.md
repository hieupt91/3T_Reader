# Commercial Release Checklist

Muc tieu: giup team chot nhanh nhung thu co the ship trong ban thuong mai,
nhung thu phai bo, va nhung phan chi can ghi notice.

## 1. Duoc ship

- `PySide6` neu tuan LGPL hoac dung commercial license.
- `pypdfium2` / PDFium cho render PDF.
- `pikepdf` cho thao tac cau truc PDF.
- `ReportLab` ban open-source.
- `cryptography`.
- `python-pkcs11`.
- Code license/update cua du an.
- Logic app, UI, workflow, signing, language pack, update client.

## 2. Phai bo khoi ban thuong mai

- `PyMuPDF` legacy path trong build chinh.
- Wrapper GPL-only neu con sot trong bundle phat hanh.
- Icon, font, logo, anh minh hoa khong ro license.
- Asset lay tu nguon ngoai nhung chua co quyen dung thuong mai.

## 3. Chi can ghi vao third-party notices

- Notice cho Qt / PySide6.
- Notice cho PDFium / pypdfium2.
- Notice cho pikepdf.
- Notice cho ReportLab OSS.
- Notice cho PDF.js neu co bundle.
- Notice cho bat ky font / icon / asset nguon ngoai nao con dung.

## 4. Ket luan ngan

- Khong bat buoc phai mua het.
- Muon ban closed-source an toan thi giu stack:
  - `PySide6`
  - `pypdfium2`
  - `pikepdf`
  - `ReportLab` OSS
- Khong ship `PyMuPDF` legacy path va khong ship GPL wrapper path trong ban phat hanh thuong mai.

