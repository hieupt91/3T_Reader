# Phase 6 Report - Temp file, cache and viewer reload control

Ngay thuc hien: 2026-06-26

Pham vi Phase 6 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Dam bao file tam khong tich luy vo han.
- Dam bao reload viewer khong lam trang trang/blank.
- Giu page/zoom/focus sau thao tac.
- Chi cleanup trong folder rieng cua app hoac file staged `.3t_*` cua PDF dich.
- Khong xoa tinh nang.
- Khong commit.

## 1. File da doc

Da doc cac file trong scope:

- `app/actions/edit.py`
- `app/actions/_pdf_save.py`
- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/actions/pages.py`
- `app/actions/document_ops.py`
- `app/actions/sign.py`

Da doc lai quy uoc:

- `FIX_RULES.md`
- `docs/CODE_CLEANUP_PHASE_PLAN.md`

## 2. Hien trang truoc khi sua

Da co san cac co che tot:

- `_reset_edit_state()` xoa `base_snapshot` va `working_file`.
- `_render_edit_state()` xoa `working_file` cu.
- `save_edits()` va `save_edits_as()` rebuild file cuoi va reset/cleanup edit state.
- `replace_document_with_staged()` dung staged file, replace atomic, invalidate PDF.js cache.
- `reload_document()` giu page/zoom va co retry neu viewer load blank.
- `LocalPDFJSServer.invalidate_pdf_cache()` xoa cache display/signature theo path.

Rui ro con lai dung Phase 6:

- Neu app crash giua chung, file trong `%TEMP%\reader_pdf_edit` va `%TEMP%\reader_pdf_sig` co the con lai.
- File staged `.3t_stage_*.pdf` va cac staged ky so `.3t_*_*.pdf` trong thu muc PDF dich co the con lai neu crash truoc replace.
- Test local server tao `LocalPDFJSServer` bang `__new__`, bo qua `__init__`, lam `cache_bust_token()` co the loi do thieu `_path_versions`.

## 3. Thay doi runtime da ap dung

### 3.1. `app/actions/_pdf_save.py`

Them helper cleanup trung tam:

- `STALE_TEMP_MAX_AGE_SECONDS = 24 * 60 * 60`
- `collect_active_pdf_temp_paths(window)`
- `prune_stale_app_temp_files(...)`
- `prune_stale_staged_pdf_files(...)`

Pham vi cleanup:

- `%TEMP%\reader_pdf_edit`
  - prefix: `base_`, `work_`, `op_`, `img_`
- `%TEMP%\reader_pdf_sig`
  - prefix: `sig_`
- Thu muc cua PDF dich
  - prefix: `.3t_stage_`, `.3t_existing_sig_`, `.3t_sigfields_`, `.3t_pfx_signed_`, `.3t_signed_`, `.3t_handwritten_`
  - suffix: `.pdf`

Dieu kien xoa:

- File phai nam trong dung folder/prefix tren.
- File phai cu hon 24 gio.
- File khong nam trong `active_paths`.
- Neu dang bi khoa hoac khong xoa duoc thi bo qua, khong lam hong workflow.

`make_staged_pdf_path()` duoc gan them cleanup staged cu trong chinh thu muc target truoc khi tao staged moi.

### 3.2. `app/window.py`

Them `_prune_stale_temp_files()` va goi mot lan khi app khoi dong sau khi `_global_state` da duoc tao.

Ly do:

- Don file temp cu tu lan chay truoc/crash truoc.
- Khong can viewer da load.
- Khong xoa file dang duoc tab/state hien tai tham chieu.

### 3.3. `app/actions/edit.py`

Khi bat dau tao edit session moi trong `_ensure_edit_state()`:

- Goi `prune_stale_app_temp_files(active_paths=collect_active_pdf_temp_paths(window))`.
- Sau do moi tao `base_<session>.pdf` va `work_<session>.pdf`.

Ly do:

- Don cac edit temp cu theo tuoi file.
- Giu lai `base_snapshot`, `working_file`, `image_path` neu dang active trong tab/edit state.

### 3.4. `app/actions/sign.py`

Trong `sign_handwritten()`:

- Goi cleanup an toan truoc khi tao/copy file `reader_pdf_sig/sig_*`.

Ly do:

- Day la luong tao file tam trong `%TEMP%\reader_pdf_sig`.
- Khong dong vao USB/PFX signing logic.

### 3.5. `app/local_server.py`

Them guard cho `_path_versions` trong:

- `cache_bust_token()`
- `invalidate_pdf_cache()`

Ly do:

- Dam bao cache bust token van hoat dong neu server object duoc tao bang `__new__` trong test hoac trong context khong chay `__init__`.
- Giu dung y tuong version token sau invalidate.

## 4. Thay doi test

Sua/tang test trong `tests/test_pdf_save_helpers.py`:

- Them `test_prune_stale_app_temp_files_keeps_active_and_recent`.
- Them `test_make_staged_pdf_path_prunes_old_staged_pdf_in_target_dir`.
- Chinh fixture `test_ensure_edit_state_prefers_display_path_over_legacy_op_temp` de file display co header `%PDF`, dung voi validate runtime hien tai.

## 5. Pham vi khong thay doi

Khong thay doi:

- Logic render PDF.js.
- Soft reload fallback trong `app/pdf_viewer.py`.
- Xoa trang/chen trang.
- Save/Save As.
- Ky USB/PFX.
- OCR.
- AI.
- Annotation undo Phase 5.

## 6. Kiem tra da chay

### 6.1. Python compile

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\_pdf_save.py app\actions\edit.py app\actions\sign.py app\window.py app\local_server.py app\pdf_viewer.py app\actions\pages.py app\actions\document_ops.py
```

Ket qua:

```text
PASS
```

### 6.2. Test temp/reload/local server lien quan Phase 6

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_pdf_save_helpers.py tests\test_local_server.py tests\test_local_server_security.py tests\test_annotation_queue.py tests\test_viewer_annotation_regressions.py -q --tb=short
```

Ket qua:

```text
52 passed
```

### 6.3. Stability contract test

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_stability_contracts.py -q --tb=short
```

Ket qua:

```text
26 passed, 2 failed
```

2 failed giong baseline cac phase truoc:

- `test_vietnamese_stamp_uses_unicode_font_when_available`
- `test_print_entry_uses_pdfjs_preview_for_screen_clarity`

Nhan dinh:

- Phase 6 khong lam tang so failed baseline.
- 2 failed nay khong thuoc scope Phase 6.

## 7. Test thu cong can lam tren UI

Can test thu cong:

1. Mo app, mo PDF lon, thao tac zoom/page, dong mo lai.
2. Chen text, chon/xoay/resize, Save, Save As.
3. Xoa trang, chen trang, xac nhan viewer khong blank va giu trang hop ly.
4. Ky tay/chon anh chu ky, xac nhan preview va file sau ky binh thuong.
5. Ky USB/PFX, xac nhan hien thi va reload viewer binh thuong.
6. Mo lai app sau khi crash gia lap/co temp cu, xac nhan khong xoa file active.

## 8. Rui ro con lai

- Cleanup chi xoa file cu hon 24 gio, nen file temp moi sau crash van co the con toi ngay hom sau. Day la chu y an toan de tranh xoa nham file dang dung.
- Chua cleanup `%TEMP%\3t_reader_decrypted` vi khong nam trong Phase 6 plan va dang duoc quan ly boi `_session_temp_paths`.
- Can test UI that de xac nhan cam giac reload sau cac thao tac nang nhu ky so, xoa trang, chen trang.

## 9. Ket luan

Phase 6 da hoan thanh:

- Them cleanup temp an toan theo tuoi file.
- Chi xoa trong folder/prefix app so huu.
- Co co che giu file dang active trong tab/edit state.
- Staged `.3t_*` cu duoc prune trong thu muc PDF dich.
- Cache bust token local server co guard `_path_versions`.
- Test lien quan pass `52/52`.
- Contract test giu baseline `26 passed, 2 failed`.
- Chua commit theo `FIX_RULES.md`.
