# Phase 3 Report - Remove leftover edit debug prints

Ngay thuc hien: 2026-06-26

Pham vi Phase 3 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Loai bo debug print con sot trong luong edit.
- Khong thay doi logic xu ly.
- Khong xoa cac `print()` trong worker/protocol CLI.
- Khong commit.

## 1. File da sua

### `app/actions/edit.py`

Da xoa 2 dong debug print ro rang:

```python
print(f"DEBUG: reportDragMove python slot invoked with: {l, b, r, t}")
```

```python
print(f"DEBUG: Python _finish received drag_move! New box: {l, b, r, t}")
```

Pham vi anh huong:

- Luong chon object va keo di chuyen object/text da chen.
- Chi giam log nhieu, khong doi signal, toa do, save, rebuild hay UI overlay.

Khong thay doi:

- `self.dragMoveConfirmed.emit(l, b, r, t)` van giu nguyen.
- Xu ly `action == "drag_move"` van giu nguyen:
  - cap nhat `target_op["box"]`
  - dong bo anchor text
  - render lai edit state

## 2. Cac `print()` da co y giu lai

Da quet rong:

```powershell
rg -n "\bprint\(" app packages -g "*.py"
```

Con cac `print()` ngoai scope Phase 3, khong xoa trong phase nay:

- `packages/signing/usb_worker.py`: stdout JSON la protocol worker.
- `packages/signing/windows_provider.py`: stdout token/error la protocol kiem tra token.
- `packages/document_core/export_runner.py`: stdout/stderr dung cho process export.
- `app/ocr_dialog.py`: log tien trinh OCR, can danh gia rieng neu muon doi sang logger.
- `app/pdf_viewer.py`: console message debug cua JS, can phase rieng neu muon tat.
- `packages/pdf_engine/pymupdf_engine.py`: print loi rebuild/font, khong phai debug print ro rang.
- `app/actions/sign.py`: print loi config/image, can phase rieng neu muon doi sang logger.
- `app/actions/annotate.py`: print loi JS rotate, can phase rieng neu muon doi sang logger.
- `app/actions/piper_tts_manager.py`: print loi Piper/download, can phase rieng neu muon doi sang logger.

Ly do khong xoa:

- Phase 3 chi yeu cau don debug print con sot trong luong edit.
- Mot so `print()` la protocol stdout, xoa se gay hong worker.
- Mot so `print()` la error logging trong module khac, can sua co chu dich rieng de tranh mat dau vet debug.

## 3. Kiem tra da chay

### 3.1. Search trong `edit.py`

Lenh:

```powershell
rg -n "DEBUG:|print\(" app\actions\edit.py
```

Ket qua:

```text
Khong con ket qua.
```

### 3.2. Search `DEBUG:` toan bo Python source

Lenh:

```powershell
rg -n "DEBUG:" app packages -g "*.py"
```

Ket qua:

```text
Khong con ket qua.
```

### 3.3. Python compile

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\edit.py
```

Ket qua:

```text
PASS
```

### 3.4. Stability contract test

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_stability_contracts.py -q --tb=short
```

Ket qua:

```text
26 passed, 2 failed
```

2 failed giong baseline Phase 0/1/2:

- `test_vietnamese_stamp_uses_unicode_font_when_available`
- `test_print_entry_uses_pdfjs_preview_for_screen_clarity`

Nhan dinh:

- Phase 3 khong lam tang so fail.
- 2 fail nay khong thuoc scope Phase 3.

## 4. Rui ro con lai

- Van con nhieu `print()` ngoai `edit.py`, nhung khong xoa trong phase nay theo dung scope.
- Neu muon don tiep cac print loi trong OCR/Piper/sign/annotate/pdf_engine, nen tao phase rieng va doi sang logger co kiem soat.
- Working tree van dirty lon tu truoc; diff `app/actions/edit.py` co lan thay doi tu Phase 1, Phase 2 va B2.

## 5. Ket luan

Phase 3 da hoan thanh:

- Xoa 2 debug print trong luong UI edit.
- `app/actions/edit.py` khong con `DEBUG:` hoac `print()`.
- Toan bo `app packages` khong con chuoi `DEBUG:`.
- `py_compile` pass.
- Contract test giu baseline `26 passed, 2 failed`.
- Chua commit theo `FIX_RULES.md`.
