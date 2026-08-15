# Ke hoach don dep code va giam bug cho 3T Reader

Tai lieu nay dung de don dep du an theo tung phase, khong xoa nham tinh nang, khong lam giam cong nang ung dung va tranh tinh trang code chong cheo. Moi phase phai lam rieng, kiem tra rieng, commit rieng neu can.

## 1. Muc tieu

- Lam sach code rac, file tam, file patch thu nghiem va log khong con can thiet.
- Giam bug UI do overlay, reload viewer, undo, temp file, encoding va thong bao sai ngu canh.
- Giam code chong cheo giua cac luong: annotation, edit text/image, ky so, PDF.js viewer, soft reload.
- Giu nguyen toan bo tinh nang hien co cua ung dung.
- Moi thay doi deu co duong lui ro rang bang git diff, test va commit rieng.

## 2. Nguyen tac bat buoc

Ap dung dung theo `FIX_RULES.md`:

- Chi sua dung nhom loi/pham vi cua phase dang lam.
- Khong xoa code neu chua chung minh code do khong duoc goi.
- Khong xoa tinh nang, khong rut gon luong nghiep vu dang dung.
- Khong don nhieu nhom loi trong cung mot commit.
- Truoc khi xoa file/code phai co bang chung:
  - `rg` khong thay noi import/goi.
  - Kiem tra `git log` de biet file do duoc tao cho loi nao.
  - Kiem tra `3T_Reader.spec`, script build, script deploy.
  - Neu la file runtime trong `app/` hoac `packages/`, phai chay test lien quan.
- Moi phase xong phai ghi:
  - Da sua file nao.
  - Pham vi anh huong.
  - Da kiem tra gi.
  - Con rui ro nao.

## 3. Trang thai hien tai can ghi nho

Working tree hien dang co nhieu thay doi chua commit. Khong duoc reset hoac checkout lung tung vi co the mat cac ban va gan day.

Nhom thay doi runtime dang ton tai:

- `app/actions/annotate.py`
- `app/actions/document_converter.py`
- `app/actions/edit.py`
- `app/actions/piper_tts_manager.py`
- `app/language_manager.py`
- `app/local_server.py`
- `app/pdf_inline_editor.py`
- `app/pdf_viewer.py`
- `app/webchannel.py`
- `app/window.py`
- `assets/js/inline_text_bridge.js`
- `main.py`
- `packages/ai/translate.py`
- `packages/pdf_engine/pymupdf_engine.py`
- `packages/signing/shared.py`
- `tests/test_stability_contracts.py`

Nhom file moi/chua track can xu ly can than:

- `packages/net_utils.py`: file tien ich SSL, dang duoc cac file network import.
- `BUG_FIX_STATUS_14.md`: co the la tai lieu trang thai loi, can doc truoc khi xoa.
- `patch_*.py`, `fix.py`, `fix_js.py`, `clean.py`, `add_log.py`: kha nang cao la file va tam.
- `test_pz2.py`, `tmpvtacm57z.docx`: kha nang cao la file test/tam.

## 4. Cac diem da kiem tra nhanh

### 4.1. Nhom audit A1/A2/B1/B2/C1

Trang thai hien tai theo kiem tra code:

| Ma | Noi dung | Trang thai | Ghi chu |
| --- | --- | --- | --- |
| A1 | `annotationMode=2` sang `annotationMode=1` | Da gan vao code | `app/local_server.py` |
| A2 | SSL bypass truc tiep | Da chuyen sang `make_ssl_context()` | Con fallback trong `packages/net_utils.py` |
| B1 | Race condition stamp PDF | Da dung ten UUID | `packages/signing/shared.py` |
| B2 | Leak file `work_*.pdf` trong edit | Da co cleanup file working cu | `app/actions/edit.py` |
| C1 | USB monitor dung `QThread` | Da co `worker.moveToThread(thread)` | `app/window.py` |

### 4.2. Kiem tra cu phap

Da chay `py_compile` cho nhom file trong luong edit, annotation, PDF save, viewer, signing, SSL. Ket qua: sach loi cu phap.

Lenh tham chieu:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\edit.py app\actions\annotate.py app\actions\document_ops.py app\actions\_pdf_save.py app\pdf_viewer.py app\window.py app\local_server.py packages\net_utils.py packages\signing\shared.py packages\ai\translate.py app\language_manager.py app\actions\document_converter.py app\actions\piper_tts_manager.py
```

## 5. Danh sach rui ro can xu ly

### 5.1. Rui ro UI hien sai tieng Viet

Co chuoi bi mojibake that trong source, khong chi la terminal hien thi sai.

Vi du:

- `packages/signing/shared.py`
  - `"ChÆ°a kÃ½"` phai la `"Chưa ký"`.
  - `"Ã” kÃ½ nÃ y chÆ°a Ä‘Æ°á»£c kÃ½ sá»‘."` phai la `"Ô ký này chưa được ký số."`.
  - `"KhÃ´ng rÃµ"` phai la `"Không rõ"`.
- `app/actions/document_ops.py`
  - Nhieu thong bao sai encoding va sai ngu canh.
- `app/actions/edit.py`
  - Tooltip resize bi mojibake.
  - Status resize object bi mojibake.

Rui ro:

- Hien hop thoai loi font.
- Thong tin chu ky so hien sai.
- Tooltip thao tac object/text hien sai.

### 5.2. Rui ro thong bao sai chuc nang

Trong `app/actions/document_ops.py`, mot so ham khong phai danh so trang nhung hien thong bao danh so trang/xoa so trang.

Vi du:

- `add_watermark()` lai bao "Khong the danh so trang".
- `remove_watermark()` lai bao "Khong the xoa so trang".
- `export_pages_to_images()` lai bao "them so trang".
- `export_pdf_to_text()` lai bao "xoa so trang".

Rui ro:

- Nguoi dung thao tac watermark/export nhung nhan thong bao cua page number.
- Kho truy loi vi UI bao sai luong.

### 5.3. Rui ro canh bao sua PDF da ky bi sai logic

Trong `app/actions/edit.py`, logic canh bao khi sua PDF da co chu ky so dang bi tu triet tieu:

```python
if current not in warned:
    status.showMessage(...)
    warned.add(current)

if current not in warned:
    QMessageBox.warning(...)
```

Sau nhanh dau, `current` da nam trong `warned`, nen nhanh hoi xac nhan phia sau gan nhu khong chay.

Rui ro:

- Nguoi dung co the edit PDF da ky ma khong duoc hoi xac nhan ro.
- Chu ky so co the mat hieu luc sau khi edit.

### 5.4. Rui ro debug print con sot

Trong `app/actions/edit.py` con cac dong debug:

- `DEBUG: reportDragMove python slot invoked...`
- `DEBUG: Python _finish received drag_move...`

Rui ro:

- Log nhiem.
- Kho phan biet log debug cu voi loi that.

### 5.5. Rui ro code do dang/chong cheo

`app/actions/edit_overlays.py` dang co ve la module thu nghiem:

- Mo ta co che "overlay truoc, rebuild khi save".
- Nhung hien khong thay noi import/goi module nay.
- Luong that dang nam trong `app/actions/edit.py` va `app/pdf_viewer.py`.

Rui ro:

- Ky thuat vien sau doc nham, sua nham module khong chay.
- De phat sinh hai co che overlay song song neu ai do kich hoat nua voi.

### 5.6. Rui ro undo annotation con lag

Luong undo annotation hien da dung huong:

- Xoa overlay mark.
- Queue thao tac xoa annotation that.
- Flush queue.
- Schedule refresh viewer.

Nhung moi lan Ctrl+Z van co the dong vao PDF that va reload/soft reload.

Rui ro:

- Ctrl+Z nhieu lan co the lag.
- Neu reload bi tre, UI co the tam thoi con overlay cu.

### 5.7. Rui ro root folder co file tam/log/patch

Nhom file kha nang cao la tam:

- `patch_edit_dialog.py`
- `patch_edit_render.py`
- `patch_edit_render2.py`
- `patch_fonts.py`
- `patch_inline.py`
- `patch_insert.py`
- `patch_pymupdf.py`
- `fix.py`
- `fix_js.py`
- `clean.py`
- `add_log.py`
- `app_run.log`
- `error.log`
- `error2.log`
- `test_*.pdf`
- `tmpvtacm57z.docx`

Rui ro:

- Lam roi thu muc root.
- De chay nham patch cu.
- Kho xac dinh file nao la source chinh.

## 6. Phuong an chia phase

### Phase 0 - Dong bang hien trang va tao baseline

Muc tieu:

- Ghi lai dung trang thai hien tai truoc khi don.
- Khong sua code runtime trong phase nay.

Viec can lam:

1. Chay:

```powershell
git status --short
git diff --stat
```

2. Ghi lai cac file dang modified/untracked.
3. Chay `py_compile` nhom file trong `app/` va `packages/` co thay doi.
4. Neu can, chay test nhanh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/test_stability_contracts.py -q
```

5. Khong xoa file nao.

Tieu chi xong:

- Co baseline ro rang.
- Biet file nao dang la thay doi runtime, file nao la file tam.

Pham vi anh huong:

- Khong anh huong app.

Commit:

- Khong bat buoc.

### Phase 1 - Sua loi hien thi chuoi va thong bao sai

Muc tieu:

- Sua loi UI thay ngay bang mat.
- Chi sua string, khong sua logic nghiep vu.

File can xu ly:

- `packages/signing/shared.py`
- `app/actions/document_ops.py`
- `app/actions/edit.py`

Viec can lam:

1. Sua chuoi mojibake trong `packages/signing/shared.py`:
   - `"ChÆ°a kÃ½"` thanh `"Chưa ký"`.
   - `"Ã” kÃ½ nÃ y chÆ°a Ä‘Æ°á»£c kÃ½ sá»‘."` thanh `"Ô ký này chưa được ký số."`.
   - `"KhÃ´ng rÃµ"` thanh `"Không rõ"`.

2. Sua chuoi mojibake trong `app/actions/edit.py`:
   - Tooltip resize.
   - Status resize object.
   - Bat ky chuoi UI nao con match mau mojibake.

3. Sua thong bao sai ngu canh trong `app/actions/document_ops.py`:
   - `add_watermark`: thong bao ve watermark.
   - `remove_watermark`: thong bao ve xoa watermark.
   - `export_pages_to_images`: thong bao ve xuat anh.
   - `export_pdf_to_text`: thong bao ve xuat text.

4. Quet lai:

```powershell
rg -n "Ã|Â|Ä|áº|á»|Æ|â€|â†|âœ" app packages -g "*.py"
```

Luu y:

- Lenh tren co the bat ca chuoi tieng Viet hop le trong `language_manager.py`, nen phai doc ngu canh, khong sua may moc.

Kiem tra:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\document_ops.py app\actions\edit.py packages\signing\shared.py
```

Test thu cong:

- Mo app.
- Kiem tra hop thoai ky so khi click o ky chua ky.
- Kiem tra tooltip resize object.
- Kiem tra thao tac watermark/export tren file khong phu hop de xem message dung chuc nang.

Tieu chi xong:

- Khong con mojibake trong cac chuoi UI cua 3 file tren.
- Thong bao dung chuc nang.

Commit de xuat:

```text
fix(ui): repair Vietnamese messages in document and signing flows
```

### Phase 2 - Sua logic canh bao PDF da ky

Muc tieu:

- Khong de nguoi dung vo tinh edit PDF da ky ma khong duoc canh bao ro.
- Khong lam thay doi cac tinh nang chen text, chen anh, ve, sua text goc.

File can xu ly:

- `app/actions/edit.py`

Phuong an:

Co 2 lua chon, can chon mot:

Phuong an A - Chi status nhe:

- Bo nhanh `QMessageBox.warning`.
- Giu status message mot lan moi file.
- Rui ro thap, it gay phien nguoi dung.

Phuong an B - Confirm that:

- Hien `QMessageBox.warning` truoc.
- Neu user chon Yes moi `warned.add(current)`.
- Neu user chon No thi return `None`.
- An toan hon cho chu ky so.

De xuat:

- Chon Phuong an B vi chu ky so la tinh nang nhay cam.

Kiem tra:

- Mo PDF co chu ky.
- Bam chen text/chen anh/sua text goc.
- App phai hoi xac nhan mot lan cho file do.
- Bam No thi khong vao edit mode.
- Bam Yes thi tiep tuc binh thuong.

Tieu chi xong:

- Khong con logic `warned.add(current)` truoc khi confirm.
- Cac thao tac edit tren PDF thuong khong bi anh huong.

Commit de xuat:

```text
fix(edit): restore confirmation before editing signed PDFs
```

### Phase 3 - Don debug print va log runtime nhiem

Muc tieu:

- Loai bo debug print con sot trong luong edit.
- Khong thay doi logic xu ly.

File can xu ly:

- `app/actions/edit.py`
- Co the doc them `app/actions/annotate.py`, `packages/pdf_engine/pymupdf_engine.py`, `app/actions/sign.py`.

Viec can lam:

1. Xoa hoac doi sang logger debug cac dong:
   - `print(f"DEBUG: reportDragMove...")`
   - `print(f"DEBUG: Python _finish...")`

2. Khong xoa cac print trong worker CLI that su can stdout, vi co the la protocol:
   - `packages/signing/usb_worker.py`
   - `packages/signing/windows_provider.py`
   - `packages/document_core/export_runner.py`

Kiem tra:

```powershell
rg -n "DEBUG:|print\(" app packages -g "*.py"
```

Tieu chi xong:

- Khong con debug print ro rang trong luong UI edit.
- Cac worker can stdout van giu.

Commit de xuat:

```text
chore(edit): remove leftover debug prints
```

### Phase 4 - Ra soat code do dang va code chong cheo

Muc tieu:

- Xac dinh code nao la runtime that, code nao la thu nghiem.
- Chua xoa ngay neu chua co bang chung day du.

File can doc ky:

- `app/actions/edit.py`
- `app/actions/edit_overlays.py`
- `app/pdf_viewer.py`
- `assets/js/inline_text_bridge.js`
- `app/pdf_inline_editor.py`
- `app/webchannel.py`

Viec can lam:

1. Lap bang mapping luong edit:

| Luong | File chinh | JS/bridge | Ghi chu |
| --- | --- | --- | --- |
| Chen text moi | `edit.py`, `inline_text_bridge.js` | QWebChannel | Runtime chinh |
| Chen anh | `edit.py`, JS image bridge | QWebChannel | Runtime chinh |
| Chon/xoay/resize object | `edit.py`, `pdf_viewer.update_ops()` | JS injected | Runtime chinh |
| Sua text goc | `edit.py`, PDF selection payload | PDF rebuild | Runtime chinh |
| Overlay edit deferred | `edit_overlays.py` | `.t3-edit-overlay` | Chua thay noi goi |

2. Kiem tra `edit_overlays.py`:

```powershell
rg -n "edit_overlays|add_edit_overlay|remove_edit_overlay|clear_edit_overlays|get_overlay_ops_for_save|t3-edit-overlay" app packages tests assets
```

3. Neu van khong co noi goi:
   - Lua chon an toan 1: doi ten/ghi comment "unused experimental module".
   - Lua chon manh hon: xoa file trong commit rieng, sau khi test day du edit.

De xuat:

- Chua xoa trong dot dau.
- Doi sang tai lieu hoa la "experimental unused" hoac dua vao folder `docs/archived_design_notes/` neu muon giu y tuong.

Kiem tra:

- Chen text.
- Resize text.
- Xoay text.
- Sua text goc.
- Ctrl+Z edit.
- Save/Save As.

Commit de xuat:

```text
docs(edit): document active edit pipeline and unused overlay module
```

Hoac neu quyet dinh xoa sau test:

```text
chore(edit): remove unused experimental edit overlay module
```

### Phase 5 - On dinh annotation, overlay va Ctrl+Z

Muc tieu:

- Giam tinh trang UI con hien to/gach sau khi undo.
- Giam lag khi Ctrl+Z nhieu lan.

File can doc:

- `app/actions/annotate.py`
- `app/actions/_pdf_save.py`
- `app/pdf_viewer.py`
- `assets/js/pdfjs_ui_hooks.js`

Trang thai hien tai:

- Da co `_remove_overlay_mark()`.
- Da co `compact_annotation_overlay_state()`.
- Da co `_schedule_annotation_viewer_refresh()`.
- Da invalidate cache sau khi ghi annotation.

Rui ro con lai:

- Moi Ctrl+Z co the flush PDF that.
- Nhieu Ctrl+Z lien tiep van co the lag.

Huong sua nhe:

1. Tang debounce refresh tu 90ms len muc hop ly hon neu can.
2. Khi undo lien tiep, gom refresh, khong reload moi lan.
3. Dam bao overlay JS duoc xoa ngay truoc khi PDF save xong.

Huong sua sau:

1. Tao batch undo trong 250-400ms.
2. Flush annotation queue mot lan cho nhieu undo.
3. Refresh viewer mot lan sau batch.

Khuyen nghi:

- Phase nay chi lam sau khi Phase 1-3 sach.
- Can test thu cong ky vi de gay regression UI.

Test thu cong:

- To sang 5 doan.
- Gach chan 5 doan.
- Gach ngang 5 doan.
- Bam Ctrl+Z lien tuc.
- Xac nhan:
  - UI bien mat dung.
  - File dong mo lai khong con annotation da undo.
  - Khong bi treo, khong quay ve dau trang neu khong can.

Commit de xuat:

```text
fix(annotation): coalesce undo refresh and clear stale overlays
```

### Phase 6 - Kiem soat temp file, cache va reload viewer

Muc tieu:

- Dam bao file tam khong tich luy vo han.
- Dam bao reload viewer khong lam trang trang/blank.
- Giu page/zoom/focus sau thao tac.

File can doc:

- `app/actions/edit.py`
- `app/actions/_pdf_save.py`
- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/actions/pages.py`
- `app/actions/document_ops.py`
- `app/actions/sign.py`

Can kiem tra:

- `reader_pdf_edit/base_*.pdf`
- `reader_pdf_edit/work_*.pdf`
- `reader_pdf_sig/*`
- `.3t_stage_*.pdf`
- cache bust token cua `LocalPDFJSServer`

Da co:

- `_reset_edit_state()` xoa `base_snapshot` va `working_file`.
- `_render_edit_state()` xoa working file cu.
- `save_edits_as()` xoa working file cu sau rebuild.
- `replace_document_with_staged()` co invalidate cache.

Rui ro can xem tiep:

- Khi app crash giua chung, temp folder van con file cu.
- Cac thao tac ky so co the tao temp ma chua don het.
- Soft reload failed co fallback `window.location.replace`, can test lai.

Huong sua an toan:

1. Them ham cleanup temp session cu theo tuoi file, vi du > 24h.
2. Chi cleanup trong folder rieng cua app:
   - `%TEMP%\reader_pdf_edit`
   - `%TEMP%\reader_pdf_sig`
3. Khong xoa temp dang duoc state hien tai tham chieu.

Test:

- Chen text, save, save as.
- Xoa trang, chen trang.
- Ky o ky, ky tay, ky USB.
- Dong mo app lai.
- Kiem tra khong blank viewer.

Commit de xuat:

```text
fix(temp): prune stale edit and signing temp files safely
```

### Phase 7 - Don root folder va file tam

Muc tieu:

- Lam root du an sach.
- Khong xoa nham file build/deploy/test can thiet.

Nhom nghi la file tam:

- `patch_*.py`
- `fix.py`
- `fix_js.py`
- `clean.py`
- `add_log.py`
- `*.log` o root
- `test_*.pdf` o root
- `test_pz2.py`
- `tmpvtacm57z.docx`

Quy trinh bat buoc truoc khi xoa:

1. Kiem tra file co duoc import/goi khong:

```powershell
rg -n "ten_file_khong_duoi_py|ten_ham_chinh" .
```

2. Kiem tra build spec:

```powershell
rg -n "ten_file|patch|fix|test_" 3T_Reader.spec *.iss scripts build_secure.py
```

3. Kiem tra git:

```powershell
git ls-files ten_file
git log --oneline -- ten_file
```

4. Neu la untracked va khong can:
   - Uu tien move vao `dev_junk_archive/` truoc.
   - Sau 1 vong test moi xoa han.

Khuyen nghi:

- Phase 7 nen lam sau khi da commit cac bugfix runtime.
- Khong tron file cleanup voi bugfix.

Commit de xuat:

```text
chore(repo): archive obsolete patch scripts and root logs
```

Hoac neu xoa han:

```text
chore(repo): remove obsolete temporary patch and log files
```

### Phase 8 - Test gate truoc khi build

Muc tieu:

- Xac nhan don dep khong lam mat tinh nang.

Lenh kiem tra toi thieu:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\edit.py app\actions\annotate.py app\actions\document_ops.py app\actions\_pdf_save.py app\pdf_viewer.py app\window.py app\local_server.py packages\signing\shared.py packages\ai\translate.py
```

Neu co thoi gian:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/test_stability_contracts.py -q
.\.venv313\Scripts\python.exe -m pytest tests/test_pdf_save_helpers.py -q
.\.venv313\Scripts\python.exe -m pytest tests/test_local_server.py -q
```

Test thu cong bat buoc:

1. Mo PDF thuong.
2. Chen text:
   - Font.
   - Bold.
   - Italic.
   - Underline.
   - Resize nho/to.
   - Xoay.
   - Save/Save As.
3. Sua text goc:
   - Boi den.
   - Sua.
   - Khong nhay ve dau trang.
   - Khong lech toa do bat thuong.
4. Annotation:
   - To sang.
   - Gach chan.
   - Gach ngang.
   - Ctrl+Z lien tuc.
   - Dong mo lai file kiem tra file that.
5. Trang:
   - Xoa trang.
   - Chen trang sau.
   - Danh so trang.
   - Xoa so trang.
6. OCR:
   - OCR trang.
   - OCR tai lieu.
   - Kiem tra overlay/progress khong chong.
7. Chat PDF:
   - Cau hoi ngan.
   - Cau hoi dai.
   - Lich su chat con trong phien.
8. Dich:
   - Doi ngon ngu 2-3 lan.
   - Khong load mai.
9. Ky so:
   - Kiem tra USB co/khong co.
   - Ky vao o ky.
   - Ky truc tiep khong qua o ky.
   - Click chu ky xem thong tin.
   - Mo lai trong 3T Reader va app PDF khac.
10. In:
   - 1 trang.
   - 2 trang.
   - Nhieu trang.
   - Quay lai 1 trang.

Tieu chi pass:

- Khong crash.
- Khong blank viewer.
- Khong mat overlay sau khi thao tac.
- Khong hien chuoi mojibake.
- Khong mat tinh nang.

### Phase 9 - Tai lieu hoa va ban giao

Muc tieu:

- Ky thuat vien sau doc vao biet code nao la luong chinh.
- Giam nguy co sua nham code do dang.

Can cap nhat:

- `docs/DEEP_BUGFIX_PHASE_PLAN.md` hoac tao file rieng neu can.
- `BUG_FIX_STATUS_14.md` neu file nay dang la bang theo doi loi.
- Tai lieu mapping luong:
  - Edit text/image.
  - Annotation/undo.
  - Signing.
  - Viewer reload.
  - Temp/cache.

Noi dung can ghi:

- File nao la entry point.
- File nao chi la helper.
- File nao khong duoc sua neu chua test.
- Nhung test thu cong bat buoc truoc build.

Commit de xuat:

```text
docs: document cleanup phases and active runtime flows
```

## 7. Thu tu uu tien de lam thuc te

Khuyen nghi lam theo thu tu sau:

1. Phase 1: sua mojibake va message sai.
2. Phase 2: sua logic confirm khi edit PDF da ky.
3. Phase 3: xoa debug print trong edit.
4. Phase 8 rut gon: chay py_compile va test thu cong nhanh.
5. Commit rieng cho 1-3 neu pass.
6. Phase 4: tai lieu hoa/xu ly `edit_overlays.py`.
7. Phase 5: toi uu undo annotation neu van con lag.
8. Phase 6: cleanup temp an toan.
9. Phase 7: don root folder.
10. Phase 8 day du truoc build.
11. Phase 9: cap nhat tai lieu ban giao.

## 8. Nhung viec khong nen lam ngay

- Khong xoa `app/actions/edit_overlays.py` ngay khi chua test het luong edit.
- Khong xoa hang loat `patch_*.py` neu chua commit runtime fix hien tai.
- Khong sua dong thoi signing, edit, annotation, OCR trong mot commit.
- Khong thay doi co che reload viewer neu chua co file PDF test va thao tac lap lai.
- Khong chay script patch cu neu chua doc noi dung.
- Khong dung `git reset --hard`.

## 9. Bang phan loai file can theo doi

| File/Nhom file | Loai | Rui ro | Huong xu ly |
| --- | --- | --- | --- |
| `app/actions/edit.py` | Runtime chinh | Cao | Chi sua theo phase nho, test text/edit/save |
| `app/pdf_viewer.py` | Runtime chinh | Cao | Can test reload/overlay/page/zoom |
| `app/actions/annotate.py` | Runtime chinh | Cao | Can test annotation va undo |
| `app/actions/document_ops.py` | Runtime chinh | Trung binh | Sua message truoc, logic sau |
| `packages/signing/shared.py` | Runtime signing | Cao | Sua string can than, test click signature |
| `app/window.py` | Main UI | Cao | Khong sua rong, can py_compile va mo app |
| `packages/net_utils.py` | Helper moi | Trung binh | Giu, vi dang duoc import |
| `app/actions/edit_overlays.py` | Co ve unused/experimental | Trung binh | Chua xoa ngay, tai lieu hoa truoc |
| `patch_*.py` | File patch tam | Thap/trung binh | Archive/xoa sau khi commit runtime |
| `*.log` root | Log tam | Thap | Xoa/archive sau |
| `test_*.pdf` root | Test artifact | Thap | Chuyen vao `tests/fixtures` neu can giu |
| `tmpvtacm57z.docx` | Temp artifact | Thap | Xoa sau khi xac nhan khong dung |

## 10. Mau checklist moi phase

Dung checklist nay truoc khi bao xong moi phase:

- [ ] Da doc file lien quan.
- [ ] Da xac dinh entry point runtime.
- [ ] Da sua dung pham vi.
- [ ] Khong xoa tinh nang.
- [ ] Khong xoa file neu chua co bang chung.
- [ ] Da chay `py_compile` file vua sua.
- [ ] Da chay test tu dong neu co.
- [ ] Da test thu cong luong anh huong.
- [ ] Da xem `git diff`.
- [ ] Da ghi lai rui ro con lai.

## 11. Ket luan

Huong don dep an toan nhat la khong bat dau bang viec xoa file. Nen bat dau tu cac bug chac chan va nho:

1. Sua string mojibake.
2. Sua message sai ngu canh.
3. Sua logic canh bao edit PDF da ky.
4. Xoa debug print.

Sau khi cac bug UI nho da sach va co commit rieng, moi chuyen sang don code do dang, overlay/undo, temp file va root junk. Cach nay giu duoc tinh nang hien co, tranh mat code vua fix, va lam cho moi thay doi deu co the truy vet.
