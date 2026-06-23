# Ke Hoach Sua Loi Chuyen Sau - 3T Reader

Ngay lap: 2026-06-22
Nguoi thuc hien: Codex
Pham vi: sua cac loi user da test/bao cao sau dot sua truoc khong dung duoc.

## Nguyen Tac Lam Viec

- Khong sua kieu "va nhanh" tung dong neu chua tai hien duoc loi hoac chua xac dinh luong code lien quan.
- Moi phase phai co muc tieu ro, file lien quan, cach test, va dieu kien "done".
- Sau khi lam xong mot phase, mo ung dung de user test thuc te.
- Chi commit sau khi user xac nhan phase do da OK.
- Khong tron nhieu blocker vao mot commit lon. Moi phase nen la mot commit rieng.
- Khong revert thay doi cua user neu khong co yeu cau ro.
- Moi thao tac ghi file PDF phai dung staged file cung thu muc dich + replace atomic/retry, tranh loi Windows file lock va cross-drive.
- Tat ca fix core phai co test tu dong neu co the. Test UI kho tu dong thi can co checklist test tay.

## Trang Thai Nhan Dinh Hien Tai

Dot sua truoc co mot so fix dung huong nhung chua du:

- Annotation overlay co them render lai theo `pagerendered/scalechanged`, nhung user da test bôi màu/gạch chân không được, can uu tien debug lai.
- Signing cross-drive bi sua sai: code dung `shutil.move(tmp, output)` nen van co the gay `[WinError 17]`.
- Seat limit reinstall chua du: backend van giu active seat neu user xoa app ma khong deactivate.
- Print orientation chi set theo trang hien tai/trang dau, chua xu ly tung trang.
- Page number chi xoa duoc marker moi; cac so trang chen tu ban cu co the khong xoa duoc.
- Chat history chi giu trong object dialog, chua persist theo PDF.
- TTS chi cache tam trong session, chua luu ben vung WAV/MP3.

## Phase 0 - Dong Bang Trang Thai Va Tao Baseline

Muc tieu:

- Ghi nhan trang thai git, test hien tai, va cac file dirty truoc khi sua.
- Xac dinh cac thay doi nao la cua dot sua truoc, khong xoa nham.

Viec can lam:

- Chay `git status --short --branch`.
- Chay test nhanh cac nhom lien quan: annotation, pdf save, signing, license.
- Ghi lai test fail hien co va khong coi chung la loi moi neu da fail truoc phase.
- Neu can, tao note trong phase log.

Dieu kien done:

- Co baseline test/log ro rang.
- Chua sua code trong phase nay tru khi can bo sung test baseline khong anh huong runtime.

### Phase 0 Baseline Log - 2026-06-22

Git baseline:

- Branch/worktree: `piper-vps-sync...origin/release-1.0.7-baseline-ocr-ai`.
- Worktree da dirty truoc khi bat dau sua Phase 1.
- Modified files: 19 files, gom `app/actions/_pdf_save.py`, `app/actions/annotate.py`, `app/actions/document_ops.py`, `app/actions/sign.py`, `app/window.py`, `packages/signing/shared.py`, `main_api.py`, `static/admin.html`, `static/index.html`, va cac file khac.
- Untracked files: `check_vps.py`, `docs/BUG_CHECKLIST_PHASE1.md`, `docs/DEEP_BUGFIX_PHASE_PLAN.md`, `test_annot.pdf`, `test_annot.py`.

Compile baseline:

- Lenh: `.\.venv313\Scripts\python.exe -m py_compile main.py app\window.py app\actions\annotate.py app\actions\sign.py app\actions\document_ops.py app\actions\_pdf_save.py packages\signing\shared.py packages\license_client\fingerprint.py`
- Ket qua: pass.

Test baseline nhanh:

- Lenh: `.\.venv313\Scripts\python.exe -m pytest tests\test_viewer_annotation_regressions.py tests\test_annotation_queue.py tests\test_pdf_save_helpers.py tests\test_signing_pr4.py tests\test_license_client.py tests\test_license_pr6.py tests\test_pdf_pipeline.py tests\test_smoke_windows.py tests\test_stability_contracts.py`
- Ket qua: `86 passed, 3 failed`.
- Fail hien co:
  - `tests/test_stability_contracts.py::test_token_monitor_runs_in_background_worker`
  - `tests/test_stability_contracts.py::test_token_monitor_skips_during_signing`
  - `tests/test_stability_contracts.py::test_vietnamese_stamp_uses_unicode_font_when_available`

Nhan dinh baseline:

- Nhom annotation regression/queue dang pass trong test tu dong, nhung user da test UI thay bôi màu/gạch chân không dùng được. Phase 1 phai uu tien test UI thuc te va them guard/test tot hon.
- Ba fail stability contract la fail ton tai truoc Phase 1, khong coi la regression moi khi sua annotation.

## Phase 1 - Sua Annotation: To Mau, Gach Duoi, Gach Ngang, Ghi Chu

Ly do uu tien:

- User da test truc tiep va bao "bôi tô màu gạch chân cũng không được".
- Day la tinh nang cot loi cua PDF editor; neu hong thi app kho dung.

Loi can xu ly:

- To sang/gach duoi/gach ngang khong hoat dong hoac mat sau khi scroll xuong roi scroll len.
- Ghi chu loi `name 'pikepdf' is not defined`.
- Khi tat auto-save phai co cach luu/flush ro rang.
- Overlay khong duoc mat khi PDF.js render lai page.

File lien quan:

- `app/actions/annotate.py`
- `assets/js/pdfjs_ui_hooks.js`
- `app/window.py`
- `app/annotation_sidebar.py`
- `tests/test_viewer_annotation_regressions.py`
- `tests/test_annotation_queue.py`

Huong sua ky thuat:

- Tach ro "PDF annotation da luu" va "overlay preview tam".
- Khong render lai bang cach xoa toan bo overlay cua viewer neu chi co mot page render lai.
- Moi mark phai co `mark_id`, `page_number`, `rects`, `style`, `color`, `path`.
- Handler `pagerendered` chi render overlay cua page do.
- Handler `scalechanged` co the render lai tat ca visible pages, nhung khong duoc xoa state Python.
- Khi tao highlight/underline/strikeout:
  - Lay selection payload tu PDF.js.
  - Them overlay ngay lap tuc.
  - Queue op luu vao PDF.
  - Push undo item.
- Khi save/flush thanh cong:
  - Khong clear overlay neu viewer chua reload.
  - Neu reload, load lai annotation tu file.
- Khi auto-save off:
  - Queue van giu pending.
  - `Ctrl+S` hoac nut Save phai flush annotations truoc khi save edit.

Test tu dong can co:

- Unit/source test bao dam `highlight_text`, `underline_text`, `strikeout_text` dung selection rects, khong prompt search.
- Test queue auto-save on/off.
- Test JS source co render theo `pagerendered` va khong remove overlay global sai cach.

Test tay sau khi mo app:

- Mo PDF co text.
- Boi den mot dong, bam To sang.
- Scroll xuong trang khac, scroll len lai, highlight van con.
- Lam tuong tu voi Gach duoi va Gach ngang.
- Them ghi chu, keo ghi chu, scroll di/ve, ghi chu van con.
- Tat auto-save trong tuy chinh toolbar, them annotation, bam Save, dong/mo lai PDF de kiem tra annotation con.

Dieu kien done:

- Test tu dong phase pass.
- User xac nhan tren app: to mau/gach duoi/gach ngang/ghi chu dung.
- Commit sau khi user xac nhan.

## Phase 2 - Sua Signing: USB, PFX, Ky Lo, Preview Chu Ky

Ly do uu tien:

- Loi hien tai co stack trace ro: `[WinError 17] The system cannot move the file to a different disk drive`.
- Dot sua truoc dung `shutil.move`, van co the gay dung loi nay.

Loi can xu ly:

- Ky so USB/PFX/ky lo fail khi temp o `C:` va output o `D:`.
- Sau khi keo tha preview, tha chuot khong hien chu ky.
- Dong thong bao nhung van keo duoc preview chu ky.
- Output fail khong duoc lam mat file dich cu.

File lien quan:

- `packages/signing/shared.py`
- `packages/signing/usb_worker.py`
- `packages/signing/windows_provider.py`
- `app/actions/sign.py`
- `app/actions/_pdf_save.py`
- `tests/test_signing_pr4.py`
- Bo sung test moi cho helper atomic signing output.

Huong sua ky thuat:

- Tao helper dung chung, vi du `write_signed_pdf_atomically(tmp_or_bytes, output_path)`.
- Temp signed output phai nam cung thu muc voi `output_path`.
- Khong `os.remove(output_path)` truoc khi staged file da ky thanh cong.
- Dung `os.replace(staged_path, output_path)` sau khi verify `%PDF-`.
- Neu pyHanko bat buoc ghi ra stream, open staged path cung thu muc dich.
- Voi in-place signing, tiep tuc dung `replace_document_with_staged`.
- Preview chu ky:
  - Chi cleanup khi cancel hoac sign flow ket thuc.
  - Neu dialog loi/canh bao bi dong, khong de bridge song ma state flow da huy.
  - Sau khi drop preview phai co placement hop le va preview hien dung vi tri.

Test tu dong can co:

- Test source khong con `shutil.move(tmp_path, output_path)` trong signing shared.
- Test helper tao staged path cung directory voi output.
- Test khong xoa output cu neu signing ghi staged fail.

Test tay sau khi mo app:

- Ky PFX vao file output o o D.
- Ky USB vao file output o o D.
- Ky lo vao thu muc output o o D.
- Thu cancel sau khi hien preview, dam bao preview bien mat sach.
- Thu drop preview va xac nhan ky, chu ky hien tren PDF da ky.

Dieu kien done:

- Khong con WinError 17 cross-drive.
- User xac nhan ky PFX/USB/ky lo dung it nhat voi mot file test.
- Commit sau khi user xac nhan.

## Phase 3 - Sua License Seat Limit Khi Cai Lai App

Ly do uu tien:

- Loi anh huong kich hoat ban quyen va khach hang that.
- Khong the giai quyet chi bang xoa local cache.

Loi can xu ly:

- Nhap key tren mot may, xoa app, cai lai, nhap lai key bi `Seat limit reached`.
- Deactivate thuong khong nen bien device thanh revoked.

File lien quan:

- `packages/license_client/fingerprint.py`
- `packages/license_client/vps_client.py`
- `vps_license_service.py`
- `main_api.py`
- `vps_models.py`
- `vps_schemas.py`
- `tests/test_license_pr6.py`
- Bo sung test service activation.

Huong sua ky thuat:

- Client:
  - Device fingerprint phai on dinh theo Windows MachineGuid neu co.
  - Khong dua du lieu volatile vao fingerprint.
- Server:
  - Neu `device_id` da co trong `active_devices`, activate lai phai success va refresh token, khong tinh seat moi.
  - `deactivate` user-requested chi remove active device, khong add vao `revoked_devices`.
  - `revoked_devices` chi dung cho admin revoke/ban.
  - Admin can co endpoint release seat neu can.
- Them thong diep loi tieng Viet ro rang cho seat limit.

Test tu dong can co:

- Activate seat=1 device A -> activate lai device A -> success.
- Activate seat=1 device A -> activate device B -> seat limit.
- Deactivate device A -> activate lai device A -> success, khong revoked.
- Admin revoke device A -> activate lai device A -> rejected.

Test tay:

- Kich hoat key tren may hien tai.
- Xoa local license cache gia lap.
- Nhap lai cung key, phai thanh cong.

Dieu kien done:

- Test service pass.
- User xac nhan kich hoat lai khong bi seat limit.
- Commit sau khi user xac nhan.

## Phase 4 - Sua PDF Save, Password, Compress, Page Number

Ly do uu tien:

- Nhieu loi lien quan cung mot goc: file lock, staged file, source/display path, temp decrypted path.

Loi can xu ly:

- Nen PDF sau dat/xoa mat khau bi `[WinError 5] Access is denied`.
- Xoa mat khau roi dat lai bi `invalid password`.
- Mo PDF co password xong ten file trong app bi doi.
- Lam so trang xong chua xoa duoc.
- Bi chen nhieu so trang tren/duoi/phai/trai.

File lien quan:

- `app/actions/_pdf_save.py`
- `app/actions/document_ops.py`
- `app/actions/file.py`
- `packages/pdf_engine/pdfium_engine.py`
- `app/window.py`
- `tests/test_pdf_save_helpers.py`
- Bo sung test page-number marker va password source/display path.

Huong sua ky thuat:

- Chuan hoa state:
  - `display_path`: file user thay.
  - `source_path`: file viewer dang load.
  - `temp_path`: decrypted/temp file neu co.
  - `write_target_path`: file thao tac can ghi.
- Voi PDF password:
  - Khi user mo password, viewer co the load temp decrypted, nhung title va tab phai dung `display_path`.
  - Remove password phai ghi ve file goc hoac Save As ro rang.
  - Compress sau password phai xac dinh dung target, khong nen nen temp roi bo quen file goc.
- Page number:
  - Marker moi phai du de xoa cac lan chen sau.
  - Truoc khi chen moi, xoa tat ca page-number marker cua app.
  - Khong hua xoa so trang cu khong co marker; neu can, tao mode "xoa theo vung" rieng.
- Save helper:
  - Dung `release_viewer_file_lock` khi can.
  - Retry PermissionError.
  - Staged file cung thu muc target.

Test tu dong can co:

- Add page number 2 lan -> chi con mot lop so trang cua app.
- Remove page number -> marker app bien mat.
- Remove password giu display path/title.
- Compress dung target path.

Test tay:

- Mo PDF co password, nhap password, tab/title van la ten file goc.
- Xoa password, dong/mo lai khong hoi password.
- Dat password lai, dong/mo lai hoi password moi.
- Nen PDF sau thao tac password khong WinError 5.
- Them so trang o nhieu vi tri lien tiep, khong chong len; bam xoa so trang, so trang do app them bien mat.

Dieu kien done:

- Test pass.
- User xac nhan cac luong password/compress/page number dung.
- Commit sau khi user xac nhan.

## Phase 5 - Sua Print Preview Va In An

Loi can xu ly:

- Chuyen trang thanh ngang chua dung.
- Preview trang mo.
- Target page bi mat khi doi single page/overview/fit page/fit width.
- Tooltip/action trong print preview chua Viet hoa du.

File lien quan:

- `app/window.py`
- `packages/pdf_engine/pdfium_engine.py`
- Test source/stability moi cho print flow neu co the.

Huong sua ky thuat:

- Khong chi set orientation mot lan truoc preview.
- Neu QPrinter/QPainter khong cho doi orientation giua job on dinh, can chon chien luoc:
  - In theo orientation cua current page neu print single/current page.
  - Hoac render tung PDF page vao page rect hien tai voi rotate/fit logic rieng.
- Preview clarity:
  - Render scale theo device pixel ratio va gioi han memory.
  - Khong render qua thap khi preview.
- Target page:
  - Lay `QPrintPreviewWidget` chinh xac.
  - Truoc khi trigger view/zoom action, luu `currentPage`.
  - Sau layout change, restore bang signal/timer ngan co guard, khong track bang polling lien tuc neu khong can.
- i18n:
  - Viet hoa action text va tooltip cua preview.
  - Sua mojibake trong chuoi moi.

Test tay:

- Mo PDF portrait.
- Mo PDF landscape.
- Mo PDF co ca portrait/landscape.
- Preview single page -> overview -> single page van quay ve trang dang xem.
- Fit Page -> Fit Width van giu target page.
- Preview net hon ban cu.

Dieu kien done:

- User xac nhan print preview va in dung.
- Commit sau khi user xac nhan.

## Phase 6 - Chat AI, TTS, Whats New, UI Labels

Loi can xu ly:

- Chat AI mat lich su moi lan chat/mac du bat luon noi.
- Bam Chat voi PDF khong co nut close/tat panel ro rang.
- TTS nen luu WAV/MP3 de dung/phat lai khong generate lai.
- "Co gi moi" can co noi dung dung thuc te.
- Nhieu tooltip/tieng Viet chua dau/chua translate.

File lien quan:

- `app/ai_chat_dialog.py`
- `packages/ai/chat_pdf.py`
- `app/actions/tts_dialog.py`
- `app/welcome_widget.py`
- `app/language_manager.py`
- `app/window.py`

Huong sua ky thuat:

- Chat:
  - Session history theo PDF key: hash path + mtime + size hoac document id.
  - Hide/show khong clear.
  - Doi PDF thi luu session cu, load session moi neu co.
  - Nut "An" va nut "Xoa lich su" rieng ro.
  - Neu user bam X window, chi hide nhung thong bao ro.
- TTS:
  - Cache audio ben vung trong app cache dir.
  - Cache key = sha256(text + voice + rate + provider + language).
  - Cho user "Luu audio thanh..." WAV/MP3.
  - Stop phai dung playback ngay, play lai dung file cached.
- Whats New:
  - Noi dung chi ghi nhung gi da user xac nhan OK.
  - Khong claim fix chua xong.
- i18n:
  - Di qua cac tooltip/menu/dialog hay gap.
  - Sua chuoi khong dau/mojibake trong source chinh.

Test tay:

- Mo Chat PDF, hoi 2 cau, an window, mo lai con lich su.
- Doi sang PDF khac, quay lai PDF cu, lich su cu con neu cung session.
- Bam An/Close panel khong gay ket app.
- Generate TTS, stop, play lai khong generate lai.
- Luu WAV/MP3 ra file user chon.

Dieu kien done:

- User xac nhan chat/TTS/UI OK.
- Commit sau khi user xac nhan.

## Phase 7 - Export Word Va Edit Existing PDF Text/Object

Ly do tach phase:

- Day la tinh nang lon, khong nen tron voi bugfix core.

Loi/yeu cau:

- PDF sang Word loi muc luc/icon.
- Can edit text/object co san trong PDF, khong chi object app tao.

Huong xu ly PDF -> Word:

- Chap nhan `pdf2docx` co gioi han; neu can tot hon phai them pipeline rieng.
- Tao option:
  - Fast convert: pdf2docx hien tai.
  - Layout-preserving: render page/image + OCR/text layer neu can.
  - Text-structured: extract text/table, uu tien muc luc/table, khong giu layout tuyet doi.
- Test voi file mau user cung cap.

Huong xu ly edit existing text/object:

- Phase thiet ke rieng:
  - Detect text spans theo page.
  - User click text -> lay bbox/span.
  - Redact/cover text cu.
  - Chen text moi bang overlay operation.
  - Save thanh PDF moi.
- Object/image existing:
  - Detect image XObject bbox neu engine ho tro.
  - Cho delete/replace theo bbox.
- Can UI ro rang vi PDF native edit rat phuc tap.

Dieu kien done:

- Co prototype voi file mau.
- User xac nhan muc do chap nhan.

## Thu Tu Commit De Xuat

1. `fix(annotation): stabilize highlight underline strikeout overlays`
2. `fix(signing): write signed PDFs atomically across drives`
3. `fix(license): allow same-device reactivation without consuming seats`
4. `fix(pdf-save): normalize password compress and page number workflows`
5. `fix(print): stabilize preview orientation target and rendering`
6. `fix(ai-tts-ui): persist chat sessions and cache generated speech`
7. `feat(pdf-edit-export): improve existing content editing and Word export`

## Lenh Kiem Tra Thuong Dung

```powershell
.\.venv313\Scripts\python.exe -m py_compile main.py app\window.py app\actions\annotate.py app\actions\sign.py app\actions\document_ops.py packages\signing\shared.py
.\.venv313\Scripts\python.exe -m pytest tests\test_viewer_annotation_regressions.py tests\test_annotation_queue.py tests\test_pdf_save_helpers.py tests\test_signing_pr4.py
.\.venv313\Scripts\python.exe -m pytest
```

## Quy Trinh Moi Phase

1. Doc lai file lien quan va test lien quan.
2. Them/sua test tai hien loi neu co the.
3. Sua code bang patch nho, tap trung vao phase.
4. Chay py_compile va test phase.
5. Mo ung dung cho user test.
6. Neu user bao OK, moi commit phase.
7. Neu user bao chua OK, sua tiep trong cung phase, khong nhay sang phase sau.

## Execution Log

### Phase 0 - Baseline Audit

Ket qua:

- `py_compile` pass cho cac file runtime chinh.
- Targeted baseline: 86 passed, 3 failed.
- 3 failed hien co nam trong `tests/test_stability_contracts.py`, khong thuoc annotation Phase 1:
  - `test_token_monitor_runs_in_background_worker`
  - `test_token_monitor_skips_during_signing`
  - `test_vietnamese_stamp_uses_unicode_font_when_available`

### Phase 1 - Annotation Overlay Stability

Van de da xac dinh:

- JS overlay note/mark trong `app/actions/annotate.py` co duong render dung bien `pageEl` khi bien nay chua duoc khai bao.
- Handler `pagerendered` dang render lai toan bo overlay va goi `removeOldOverlays()` toan cuc, co the xoa highlight/underline/strikeout cua trang khac khi PDF.js render lai tung trang.
- Test cu chua bat duoc loi JS nhung Python van compile vi JS nam trong raw string.

Sua da lam:

- Doi renderer overlay sang page-scoped render: `renderPage(pageNumber)`.
- `pagerendered` chi render lai dung page vua render.
- `scalechanged` moi render lai toan bo overlay.
- Sua note renderer de khai bao `var pageEl = pageView.div;` truoc khi append/bind.
- Them cleanup handler theo page de tranh tich luy mouse handlers khi scroll/zoom.
- Them regression test source-contract de chan loi `pageEl` undefined va render toan cuc xoa cheo.

Kiem tra:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\annotate.py
.\.venv313\Scripts\python.exe -m pytest tests\test_viewer_annotation_regressions.py tests\test_annotation_queue.py tests\test_pdf_save_helpers.py
```

Ket qua:

- 23 passed.

### Phase 2 - Signing Cross-Drive Output And Preview Cleanup

Van de da xac dinh:

- `packages/signing/shared.py` van ghi file ky vao temp mac dinh roi `shutil.move(tmp_path, output_path)`.
- Tren Windows, temp thuong o `C:` trong khi user luu file ky o `D:` nen phat sinh `WinError 17`.
- Flow pick vi tri ky trong `app/actions/sign.py` teardown WebChannel nhung chua ep chay JS cleanup trong `finally`, nen co the de sot listener/overlay sau khi dong prompt.

Sua da lam:

- Them helper `_make_output_staged_pdf_path(output_path)` de tao staged PDF ngay trong cung thu muc dich.
- Them helper `_replace_signed_output(staged_path, output_path)` dung `os.replace` va khong xoa file dich truoc.
- Ap helper moi cho ca `sign_pdf_with_session(...)` va `sign_pdf_with_pkcs12(...)`.
- Bo `shutil.move(tmp_path, output_path)` trong hai flow ky chinh.
- Trong `_pick_signature_placement(...)`, them JS cleanup call trong `finally` de dong sach overlay/listener cua pick-phase truoc khi teardown WebChannel.
- Them test hoi quy cho staged path, giu nguyen output cu neu staged file loi, va contract khong con `shutil.move`.

Kiem tra:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\sign.py packages\signing\shared.py
.\.venv313\Scripts\python.exe -m pytest tests\test_signing_pr4.py tests\test_pdf_save_helpers.py tests\test_smoke_windows.py
```

Ket qua:

- 35 passed.

### Phase 3 - License Seat Reuse On Reinstall

Van de da xac dinh:

- Fingerprint Windows hien tai co tron `COMPUTERNAME`; doi ten may hoac thay doi nguon fallback co the sinh `device_id` moi du cung may.
- Backend seat logic chi so khop bang `device_id`; neu `device_id` lech nhe thi cung may van bi tinh seat moi.
- Luong `deactivate` phia client gui `reason="user_requested"` nhung API route chua truyen `reason` vao service.
- Service top-level cu dang dua `device_id` vao `revoked_devices` ngay ca khi user tu deactivate/app reinstall.

Sua da lam:

- `packages/license_client/fingerprint.py`:
  - Neu co `MachineGuid` tren Windows thi fingerprint bo phu thuoc vao hostname.
- `vps_license_service.py`:
  - Them `_find_reusable_device_id(...)` de tai su dung seat neu cung `machine_name` + `platform`.
  - Khi gap cung may nhung `device_id` moi, chuyen seat cu sang `device_id` moi thay vi an seat moi.
  - `deactivate(..., reason)` khong dua vao `revoked_devices` neu la `user_requested`, `app_reinstall`, `app_uninstall`.
- `main_api.py`:
  - Route `/api/license/deactivate` truyen `req.reason` xuong service.
- `tests/test_license_pr6.py`:
  - Them test fingerprint Windows bo qua hostname khi co `MachineGuid`.
  - Them source-contract test cho reusable seat, non-revoke deactivate, va API pass-through `reason`.

Kiem tra:

```powershell
.\.venv313\Scripts\python.exe -m py_compile packages\license_client\fingerprint.py vps_license_service.py main_api.py
.\.venv313\Scripts\python.exe -m pytest tests\test_license_pr6.py
```

Ket qua:

- 5 passed.

### Phase 4 - PDF Save, Password, Compress, Page Number

Trang thai xac nhan:

- Phase nay da co dau hieu hoan tat ve mat code va regression test.
- Logic hien tai phu hop voi huong sua da de ra trong ke hoach: staged file cung thu muc dich, tach `source_path` / `display_path` / `temp_path`, va page-number workflow co marker de xoa lap lai an toan.
- Chua thay log test tay duoc ghi ro trong file nay; neu can chot phase theo dung quy trinh goc thi user nen test lai cac luong password/compress/page number tren app.

Sua da co trong code:

- `app/actions/_pdf_save.py`:
  - Co `make_staged_pdf_path(...)`, `release_viewer_file_lock(...)`, `replace_file_with_retry(...)`, `replace_document_with_staged(...)`.
  - Ghi staged PDF trong cung thu muc voi file dich va co retry khi gap file lock.
- `app/actions/document_ops.py`:
  - Dung `_document_read_and_target_paths(window)` cho cac luong password/compress/page number.
  - `set_pdf_password(...)`, `remove_pdf_password(...)`, `compress_pdf(...)` da phan biet `read_path` va `target_path`.
  - `add_page_numbers(...)` va `remove_page_numbers(...)` dung marker `_PAGENUM_MARKER_KEY` va xoa lop page number cu truoc khi chen lai.
- `app/actions/file.py` va `app/window.py`:
  - State document da tach ro `source_path`, `display_path`, `temp_path`.
  - Luong mo PDF co mat khau da giu `display_path` la ten file goc va track file giai ma tam rieng.

Kiem tra:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\_pdf_save.py app\actions\document_ops.py app\actions\file.py app\window.py
.\.venv313\Scripts\python.exe -m pytest tests\test_pdf_save_helpers.py
```

Ket qua:

- `py_compile` pass.
- `tests/test_pdf_save_helpers.py`: 12 passed.

Ghi chu:

- Co the xem Phase 4 la "done in code/test".
- Neu can dong phase theo dung checklist goc, chi con buoc user test tay tren app va commit neu user xac nhan.
