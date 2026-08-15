# Phase 7 Report - Root folder and temporary file cleanup

Ngay thuc hien: 2026-06-26

Pham vi Phase 7 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Lam root du an sach hon.
- Khong xoa nham file build/deploy/test can thiet.
- Kiem tra reference/build/git truoc khi archive.
- Uu tien archive truoc, khong xoa han.
- Khong commit.

## 1. File da doc

Da doc:

- `docs/CODE_CLEANUP_PHASE_PLAN.md`
- `FIX_RULES.md`
- `.gitignore`
- root file listing
- git status/git ls-files

## 2. Nhom candidate da kiem tra

Theo Phase 7 plan, da kiem tra cac nhom:

- `patch_*.py`
- `fix.py`
- `fix_js.py`
- `clean.py`
- `add_log.py`
- `*.log` o root
- `test_*.pdf` o root
- `test_pz2.py`
- `tmpvtacm57z.docx`

## 3. Kiem tra truoc khi archive

### 3.1. Reference trong source/docs

Da chay literal search bang `rg -F` cho tung filename.

Ket qua:

- Nhom untracked/ignored chi xuat hien trong tai lieu cleanup/baseline hoac khong co reference.
- Khong thay reference runtime/import cho cac file untracked da archive.
- Khong thay build/deploy goi cac file untracked da archive.

### 3.2. Build spec / installer / scripts

Da chay search tren:

- `3T_Reader.spec`
- `installer_script.iss`
- `build_secure.py`
- `scripts/`
- `installer/`

Ket qua:

- Khong co reference den cac file untracked da archive.

### 3.3. Git tracking

Da phan loai:

- Untracked/ignored: duoc archive.
- Tracked hoac modified: khong archive trong Phase 7 nay.

Ly do:

- Phase 7 plan noi ro khong tron cleanup voi bugfix.
- Worktree dang co nhieu thay doi runtime chua commit.
- Move tracked file se tao deletion/rename trong git, rui ro cao hon va nen lam commit cleanup rieng sau.

## 4. File da archive

Do filesystem/sandbox khong cho tao thu muc archive moi `dev_junk_archive` hoac `docs/cleanup_archive`, da archive vao thu muc `debug/` co san.

Tat ca file duoc doi ten theo prefix:

```text
debug/phase7_20260626__<ten_file_goc>
```

Danh sach:

- `add_log.py`
- `clean.py`
- `patch_edit_dialog.py`
- `patch_edit_render.py`
- `patch_edit_render2.py`
- `patch_fonts.py`
- `patch_inline.py`
- `patch_insert.py`
- `patch_pymupdf.py`
- `test_pz2.py`
- `tmpvtacm57z.docx`
- `_run_stderr.log`
- `_run_stdout.log`
- `app_run.log`
- `cloudflared.log`
- `error.log`
- `error2.log`
- `import.log`
- `output.log`
- `pyarmor.bug.log`

Ghi chu:

- `debug/` dang nam trong `.gitignore`, nen cac file archive nay khong lam tang noise trong git status.
- Day la archive tam theo dung tinh than Phase 7, chua xoa han.

## 5. File co y chua dung

Khong move cac file tracked/modified sau:

- `fix.py`
- `fix_js.py`
- `patch_data.py`
- `patch_data_sudo.py`
- `patch_tts.py`
- `patch_vps.py`
- cac `test_*.pdf` tracked o root

Ly do:

- Cac file nay dang duoc git track hoac dang modified.
- Can cleanup commit rieng neu muon xoa/di chuyen han.
- Khong nen lam trong luc worktree dang co nhieu bugfix runtime chua commit.

## 6. Trang thai root sau cleanup

Root khong con cac file untracked/ignored da archive:

- `add_log.py`
- `clean.py`
- `patch_edit_dialog.py`
- `patch_edit_render.py`
- `patch_edit_render2.py`
- `patch_fonts.py`
- `patch_inline.py`
- `patch_insert.py`
- `patch_pymupdf.py`
- `test_pz2.py`
- `tmpvtacm57z.docx`
- cac log root da archive trong danh sach tren

Root van con cac candidate tracked de xu ly sau:

- `fix.py`
- `fix_js.py`
- `patch_data.py`
- `patch_data_sudo.py`
- `patch_tts.py`
- `patch_vps.py`
- cac `test_*.pdf` tracked

## 7. Kiem tra da chay

### 7.1. Python compile

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\edit.py app\actions\annotate.py app\actions\document_ops.py app\actions\_pdf_save.py app\pdf_viewer.py app\window.py app\local_server.py packages\signing\shared.py packages\ai\translate.py
```

Ket qua:

```text
PASS
```

### 7.2. Test lien quan PDF save/local server

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_pdf_save_helpers.py tests\test_local_server.py -q --tb=short
```

Ket qua:

```text
29 passed
```

### 7.3. Stability contract

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

- Phase 7 khong lam tang so failed baseline.
- 2 failed nay khong thuoc scope Phase 7.

## 8. Rui ro con lai

- Cac file archive dang nam trong `debug/`, la thu muc ignored. Neu muon giu archive trong git thi can move sang docs bang co che khac hoac sua policy folder.
- Cac file tracked root candidate van con; nen xu ly trong commit cleanup rieng sau khi bugfix runtime duoc commit.
- Chua xoa han file nao.

## 9. Ket luan

Phase 7 da hoan thanh phan an toan:

- Da doc plan va lam theo quy trinh check reference/build/git.
- Da archive 20 file root tam untracked/ignored.
- Khong xoa han file nao.
- Khong move tracked file.
- Compile pass.
- Test lien quan pass `29/29`.
- Contract test giu baseline `26 passed, 2 failed`.
- Chua commit theo `FIX_RULES.md`.
