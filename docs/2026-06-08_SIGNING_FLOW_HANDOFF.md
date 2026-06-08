# 3T Reader Signing Flow Handoff

Ngay lap: 2026-06-08

Muc tieu cua buoi lam viec nay la lam ro va sua luong ky de nguoi dung khong con cam giac "keo xong roi mat", va de flow di thang toi chuyen ky + ghi file.

## Da lam

### 1. Bo hop thoai placement cho luong ky

Truoc day luong ky tay, ky so PFX va ky USB token deu co mot hop thoai placement trung gian sau khi da keo vung ky tren PDF.

Hien tai:
- `_pick_signature_placement()` van dung de nguoi dung keo/chon vung ky tren PDF.
- Sau khi da co `placement`, flow di thang sang cac buoc tiep theo.
- Khong con mo lai `SignaturePlacementDialog` cho `sign_with_pfx()`, `sign_document()` va `sign_handwritten()`.

Y nghia UX:
- Keo xong la khong con bi "rut" ve mot dialog trung gian.
- Nguoi dung thay vi tri preview tren PDF va tiep tuc nhap thong tin can thiet de ky.

### 2. Giữ preview cho toi khi xong

Da them helper `_cleanup_signature_preview(window, web_view=None)` trong `app/actions/sign.py`.

Muc dich:
- Giu preview hien tren PDF trong qua trinh nhap PFX/PIN/xac nhan.
- Cleanup preview va detach WebChannel theo cung mot cach o cuoi luong, hoac khi huy.

### 3. Regession test cho luong ky

Da them test contract trong `tests/test_stability_contracts.py` de chan viec quay lai placement dialog:
- `sign_with_pfx()`
- `sign_document()`
- `sign_handwritten()`

## File da thay doi trong phan nay

- `app/actions/sign.py`
- `tests/test_stability_contracts.py`

## Kiem tra da chay

- `.\.venv313\Scripts\python.exe -m py_compile app\actions\sign.py tests\test_stability_contracts.py`
- `.\.venv313\Scripts\python.exe -m pytest tests\test_stability_contracts.py -q`

Ket qua:
- `8 passed`

## Luu y cho buoi sau

1. Khi test UI, dung mot PDF that va thu ca 3 nhom:
   - ky tay
   - ky tu file PFX
   - ky USB token

2. Neu muon lam UX ro hon nua:
   - co the them status text ro hon cho giai doan "dang chon vi tri" va "dang ky"
   - co the them chan/hint ngay tren PDF neu user keo chua dung y

3. Worktree luc do con co cac file khac dang modified/unstaged tu truoc:
   - khong gom chung vao commit nay neu khong lien quan truc tiep den signing flow

## Tom tat ngan

Ngay nay da chuyen luong ky tu "chon vi tri -> mo dialog placement -> ky" sang "chon vi tri -> ky ngay", dong thoi giu preview de nguoi dung khong bi mat huong trong qua trinh lam viec.

