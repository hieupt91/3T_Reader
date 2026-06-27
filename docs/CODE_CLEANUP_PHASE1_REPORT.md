# Phase 1 Report - UI message and mojibake cleanup

Ngay thuc hien: 2026-06-26

Pham vi Phase 1 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Sua chuoi UI bi mojibake.
- Sua thong bao sai ngu canh trong `document_ops.py`.
- Chi sua string/message, khong thay doi logic nghiep vu.
- Khong xoa file.
- Khong commit.

## 1. File da sua

### 1.1. `packages/signing/shared.py`

Da sua cac chuoi hien thi trong bao cao o ky so:

- `"ChÆ°a kÃ½"` -> `"Chưa ký"`
- `"Ã” kÃ½ nÃ y chÆ°a Ä‘Æ°á»£c kÃ½ sá»‘."` -> `"Ô ký này chưa được ký số."`
- `"KhÃ´ng rÃµ"` -> `"Không rõ"`

Pham vi anh huong:

- Hop thoai/thong tin khi click vao o ky so.
- Truong hop o ky chua duoc ky.
- Truong hop chu ky khong co ten hien thi.

Khong thay doi:

- Khong thay doi logic xac thuc chu ky.
- Khong thay doi luong ky USB.
- Khong thay doi toa do/appearance chu ky.

### 1.2. `app/actions/edit.py`

Da sua cac chuoi UI bi mojibake:

- Tooltip nut resize object:
  - `"KÃ©o Ä‘á»ƒ thu phÃ³ng"` -> `"Kéo để thu phóng"`
- Warning khi khong tim thay PDF hop le de bat dau edit:
  - `"KhÃ´ng thá»ƒ chá»‰nh sá»­a"` -> `"Không thể chỉnh sửa"`
  - Message chi tiet -> `"Không tìm thấy bản PDF hợp lệ để bắt đầu phiên chỉnh sửa."`
- Status resize object:
  - `"ÄÃ£ thay Ä‘á»•i kÃ­ch thÆ°á»›c Ä‘á»‘i tÆ°á»£ng"` -> `"Đã thay đổi kích thước đối tượng"`

Pham vi anh huong:

- UI chon/xoay/resize object chen.
- Warning khi edit state khong lay duoc PDF hop le.
- Status bar sau khi resize object.

Khong thay doi:

- Khong sua toa do text.
- Khong sua logic resize.
- Khong sua save/rebuild.
- Khong sua undo.

Luu y:

- `app/actions/edit.py` da co cac thay doi cu tu truoc Phase 1 trong working tree. Diff tong cua file nay co the hien ca cac thay doi cu, khong phai tat ca deu thuoc Phase 1.

### 1.3. `app/actions/document_ops.py`

Da sua thong bao sai ngu canh va mojibake trong cac thao tac document:

#### `add_watermark()`

Truoc:

- Bao sai la khong the danh so trang.

Sau:

- `"Không thể thêm watermark trên file đang giải mã"`
- `"Hãy xóa mật khẩu hoặc mở lại file gốc trước khi thêm watermark để tránh ghi nhầm vào bản tạm."`

#### `remove_watermark()`

Truoc:

- Bao sai la khong the xoa so trang.

Sau:

- `"Không thể xóa watermark trên file đang giải mã"`
- `"Hãy xóa mật khẩu hoặc mở lại file gốc trước khi xóa watermark để tránh ghi nhầm vào bản tạm."`

#### `compress_pdf()`

Truoc:

- Noi dung dung ngu canh nen PDF nhung bi mojibake.

Sau:

- `"Không thể nén file đang giải mã"`
- `"Hãy xóa mật khẩu hoặc mở lại file gốc trước khi nén PDF để tránh sai lệch trạng thái mã hóa."`

#### `export_pages_to_images()`

Truoc:

- Bao sai la khong the danh so trang/them so trang.

Sau:

- `"Không thể xuất ảnh từ file đang giải mã"`
- `"Hãy xóa mật khẩu hoặc mở lại file gốc trước khi xuất ảnh để tránh ghi nhầm vào bản tạm."`

#### `export_pdf_to_text()`

Truoc:

- Bao sai la khong the xoa so trang.

Sau:

- `"Không thể xuất văn bản từ file đang giải mã"`
- `"Hãy xóa mật khẩu hoặc mở lại file gốc trước khi xuất văn bản để tránh ghi nhầm vào bản tạm."`

Pham vi anh huong:

- Chi anh huong text hien thi trong warning.
- Khong thay doi cach ghi file.
- Khong thay doi reload viewer.
- Khong thay doi xu ly mat khau/temp file.

## 2. Kiem tra da chay

### 2.1. Python compile

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\document_ops.py app\actions\edit.py packages\signing\shared.py
```

Ket qua:

```text
PASS
```

### 2.2. Quet chuoi mojibake target

Da quet cac pattern target trong 3 file:

- `KhÃ`
- `ChÆ`
- `KÃ©o`
- `ÄÃ`
- `máº`
- `láº`
- `trÆ`
- `nÃ`

Ket qua:

- Khong con chuoi mojibake target can sua trong 3 file Phase 1.
- Mot so pattern co the bat nham chuoi tieng Viet dung do PowerShell/console, da doi chieu bang doc file UTF-8 truc tiep.

### 2.3. Stability contract test

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_stability_contracts.py -q --tb=short
```

Ket qua:

```text
26 passed, 2 failed
```

2 failed giong baseline Phase 0:

- `test_vietnamese_stamp_uses_unicode_font_when_available`
- `test_print_entry_uses_pdfjs_preview_for_screen_clarity`

Nhan dinh:

- Phase 1 khong lam tang so fail.
- 2 fail nay khong thuoc scope Phase 1.

## 3. Rui ro con lai

- Chua test UI thu cong trong app vi Phase 1 moi chay kiem tra tu dong/cau truc.
- Working tree van dirty lon tu truoc; can tiep tuc lam theo phase, khong reset/checkout lung tung.
- `app/actions/edit.py` va `packages/signing/shared.py` con cac thay doi cu ngoai Phase 1, nen khi review diff can phan biet thay doi cu voi thay doi Phase 1.

## 4. Ket luan

Phase 1 da hoan thanh muc tieu:

- Sua chuoi chu ky so bi mojibake.
- Sua tooltip/status/warning edit bi mojibake.
- Sua thong bao document ops sai ngu canh.
- `py_compile` pass.
- Contract test van giu baseline 26 passed, 2 failed.

Chua commit theo dung `FIX_RULES.md`.
