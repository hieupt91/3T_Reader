# Phase 2 Report - Signed PDF edit confirmation

Ngay thuc hien: 2026-06-26

Pham vi Phase 2 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Sua logic canh bao khi bat dau edit PDF da co chu ky so.
- Chi sua `app/actions/edit.py`.
- Khong sua luong chen text, chen anh, sua text goc, annotation, undo, signing.
- Khong xoa file.
- Khong commit.

## 1. Van de truoc khi sua

Trong `_ensure_edit_state()` cua `app/actions/edit.py`, logic canh bao file da ky so bi sai:

```python
if current not in warned:
    status.showMessage(...)
    warned.add(current)

if current not in warned:
    QMessageBox.warning(...)
```

Do `warned.add(current)` chay truoc, nhanh `QMessageBox.warning(...)` gan nhu khong bao gio chay. Ket qua la nguoi dung chi thay status nhe, khong co hop xac nhan ro truoc khi edit PDF da ky.

Rui ro:

- Nguoi dung co the vo tinh edit PDF da ky.
- Chu ky so co the mat hieu luc sau khi rebuild PDF.
- Hanh vi khong dung voi yeu cau Phase 2.

## 2. Cach sua da ap dung

Da chon Phuong an B trong phase plan:

- Hien `QMessageBox.warning` truoc.
- Neu user bam No thi return `None`, khong vao edit mode.
- Neu user bam Yes thi moi ghi nho file da duoc canh bao.
- Dung `os.path.abspath(current)` lam key de tranh lap canh bao do path tuong doi/tuyet doi khac nhau.
- Sau khi user xac nhan Yes, hien status message tieng Viet dung encoding.

Logic sau khi sua:

```python
warning_key = os.path.abspath(current)
if warning_key not in warned:
    reply = QMessageBox.warning(...)
    if reply != QMessageBox.StandardButton.Yes:
        return None
    warned.add(warning_key)
    status.showMessage(...)
```

## 3. File da sua

### `app/actions/edit.py`

Ham anh huong:

- `_ensure_edit_state(window)`

Pham vi anh huong:

- Khi nguoi dung bat dau mot phien edit tren PDF co chu ky so.
- Cac thao tac co the goi `_ensure_edit_state()`, vi du chen text/anh/ve/sua text goc.

Khong thay doi:

- Khong thay doi toa do text.
- Khong thay doi resize/xoay.
- Khong thay doi rebuild/save.
- Khong thay doi undo annotation.
- Khong thay doi signing.

## 4. Kiem tra da chay

### 4.1. Doc lai code sau patch

Da doc lai vung code `_ensure_edit_state()` va xac nhan:

- `QMessageBox.warning(...)` nam truoc `warned.add(...)`.
- `warned.add(warning_key)` chi chay sau khi user bam Yes.
- Khong con status message ASCII khong dau `"Tai lieu co chu ky so..."`.

### 4.2. Search static

Lenh:

```powershell
rg -n "_edit_sig_warned_paths|warning_key|warned\.add|QMessageBox\.warning|Tai lieu co chu ky so" app\actions\edit.py
```

Ket qua can chu y:

- `QMessageBox.warning` o truoc.
- `warned.add(warning_key)` o sau.
- Khong con chuoi `"Tai lieu co chu ky so..."`.

### 4.3. Python compile

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\edit.py
```

Ket qua:

```text
PASS
```

### 4.4. Stability contract test

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_stability_contracts.py -q --tb=short
```

Ket qua:

```text
26 passed, 2 failed
```

2 failed giong baseline Phase 0/Phase 1:

- `test_vietnamese_stamp_uses_unicode_font_when_available`
- `test_print_entry_uses_pdfjs_preview_for_screen_clarity`

Nhan dinh:

- Phase 2 khong lam tang so fail.
- 2 fail nay khong thuoc scope Phase 2.

## 5. Test thu cong nen lam trong app

Can test khi mo app:

1. Mo PDF da co chu ky so.
2. Bam Chen chu hoac thao tac edit bat ky.
3. App phai hien hop xac nhan:
   - Tieu de: `Tài liệu đã có chữ ký số`
   - Noi dung canh bao chu ky co the mat hieu luc.
4. Bam No:
   - Khong vao edit mode.
   - Khong tao edit state.
5. Bam lai thao tac, bam Yes:
   - Cho phep edit.
   - Cung file do khong hoi lap lai trong cung phien.
6. Mo PDF thuong khong co chu ky:
   - Khong hien hop canh bao.
   - Cac thao tac edit van binh thuong.

## 6. Rui ro con lai

- Chua test thu cong UI vi report nay moi chay static/compile/test contract.
- Neu `_pdf_has_signature_field(current)` khong nhan dien duoc mot so dang chu ky dac biet, Phase 2 khong thay doi phan do.
- Working tree van dirty lon; diff `app/actions/edit.py` co lan ca thay doi cu tu Phase 1 va B2, khong phai tat ca deu thuoc Phase 2.

## 7. Ket luan

Phase 2 da hoan thanh:

- Da sua logic confirm that truoc khi edit PDF da ky.
- Da dam bao `warned.add(...)` chi chay sau khi user bam Yes.
- `py_compile` pass.
- Contract test giu baseline `26 passed, 2 failed`.
- Chua commit theo `FIX_RULES.md`.
