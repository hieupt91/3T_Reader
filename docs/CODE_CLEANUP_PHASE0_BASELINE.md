# Phase 0 Baseline - Code cleanup

Ngay tao baseline: 2026-06-26

Muc tieu Phase 0:

- Ghi lai hien trang du an truoc khi don dep.
- Khong sua code runtime.
- Khong xoa file nao.
- Xac nhan toi thieu rang cac file Python lien quan khong loi cu phap.
- Ghi lai test contract hien tai pass/fail de lam moc so sanh cho cac phase sau.

## 1. Lenh da chay

### 1.1. Git status

```powershell
git status --short
```

Ket qua tom tat:

- 20 file tracked dang co thay doi hoac bi xoa.
- 14 file untracked.
- Co 1 tai lieu moi vua tao o Phase Plan: `docs/CODE_CLEANUP_PHASE_PLAN.md`.

### 1.2. Diff stat

```powershell
git diff --stat
```

Ket qua:

```text
20 files changed, 374 insertions(+), 115 deletions(-)
```

Co canh bao line ending:

```text
LF will be replaced by CRLF the next time Git touches it
```

Canh bao nay xuat hien o mot so file Python/JS dang thay doi. Day la canh bao line ending, khong phai loi cu phap.

### 1.3. Name status

```powershell
git diff --name-status
```

Ket qua:

```text
M app/actions/annotate.py
M app/actions/document_converter.py
M app/actions/edit.py
D app/actions/edit.py.rej
M app/actions/piper_tts_manager.py
M app/language_manager.py
M app/local_server.py
M app/pdf_inline_editor.py
M app/pdf_viewer.py
M app/webchannel.py
M app/window.py
M assets/js/inline_text_bridge.js
M docs/Ho_So_Phap_Ly/BAN_MO_TA_PHAN_MEM.pdf
M fix.py
M fix_js.py
M main.py
M packages/ai/translate.py
M packages/pdf_engine/pymupdf_engine.py
M packages/signing/shared.py
M tests/test_stability_contracts.py
```

### 1.4. Untracked files

```powershell
git ls-files --others --exclude-standard
```

Ket qua:

```text
BUG_FIX_STATUS_14.md
add_log.py
clean.py
docs/CODE_CLEANUP_PHASE_PLAN.md
packages/net_utils.py
patch_edit_dialog.py
patch_edit_render.py
patch_edit_render2.py
patch_fonts.py
patch_inline.py
patch_insert.py
patch_pymupdf.py
test_pz2.py
tmpvtacm57z.docx
```

### 1.5. Python compile check

```powershell
.\.venv313\Scripts\python.exe -m py_compile main.py fix.py fix_js.py app\actions\annotate.py app\actions\document_converter.py app\actions\edit.py app\actions\piper_tts_manager.py app\language_manager.py app\local_server.py app\pdf_inline_editor.py app\pdf_viewer.py app\webchannel.py app\window.py packages\ai\translate.py packages\pdf_engine\pymupdf_engine.py packages\signing\shared.py packages\net_utils.py tests\test_stability_contracts.py add_log.py clean.py patch_edit_dialog.py patch_edit_render.py patch_edit_render2.py patch_fonts.py patch_inline.py patch_insert.py patch_pymupdf.py test_pz2.py
```

Ket qua:

```text
PASS - khong co loi cu phap Python.
```

So file Python da compile: 28.

### 1.6. Stability contract test

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_stability_contracts.py -q --tb=short
```

Ket qua:

```text
26 passed, 2 failed
```

2 test fail:

```text
FAILED tests/test_stability_contracts.py::test_vietnamese_stamp_uses_unicode_font_when_available
Reason: style.background is None
```

```text
FAILED tests/test_stability_contracts.py::test_print_entry_uses_pdfjs_preview_for_screen_clarity
Reason: source khong co chuoi "app.pdfViewer.scrollMode = 3"
```

Nhan dinh:

- 2 fail nay khong duoc sua trong Phase 0.
- Day la baseline hien tai de so sanh sau cac phase sau.
- Neu Phase sau lam tang so fail thi can dung lai de doc diff.

### 1.7. Git diff check

```powershell
git diff --check
```

Ket qua:

- Khong bao loi whitespace/conflict marker.
- Chi co canh bao line ending LF -> CRLF o mot so file.

## 2. Phan loai file tracked dang thay doi

### 2.1. Runtime core - rui ro cao

| File | Vai tro | Ghi chu |
| --- | --- | --- |
| `app/window.py` | Main window, toolbar, token monitor, print | Rui ro cao, khong sua rong |
| `app/pdf_viewer.py` | PDF.js viewer wrapper, soft reload, overlay ops | Rui ro cao voi blank viewer/reload |
| `app/local_server.py` | Local PDF server, PDF.js URL, signature hitbox/info | Rui ro cao voi viewer va ky so |
| `app/actions/edit.py` | Chen/sua text, image, object action, save edit | Rui ro rat cao |
| `app/actions/annotate.py` | To sang, gach chan, undo annotation, page ops cu | Rui ro cao voi overlay/undo |
| `app/actions/document_converter.py` | Convert/download module | Rui ro trung binh |
| `app/actions/piper_tts_manager.py` | TTS/Piper download/runtime | Rui ro trung binh |
| `app/language_manager.py` | Language packs/download | Rui ro trung binh |
| `app/pdf_inline_editor.py` | Inline PDF editor helper | Rui ro trung binh |
| `app/webchannel.py` | WebChannel bridges | Rui ro cao neu sua sai bridge |
| `packages/ai/translate.py` | Translate/network | Rui ro trung binh |
| `packages/pdf_engine/pymupdf_engine.py` | PDF rebuild/render ops | Rui ro cao voi edit text/image |
| `packages/signing/shared.py` | Signing stamp/info/check | Rui ro cao voi ky so |

### 2.2. UI/asset

| File | Vai tro | Ghi chu |
| --- | --- | --- |
| `assets/js/inline_text_bridge.js` | JS overlay chen text | Rui ro cao voi chen text/resize |
| `docs/Ho_So_Phap_Ly/BAN_MO_TA_PHAN_MEM.pdf` | Tai lieu PDF | Binary changed, can xac dinh co can commit khong |

### 2.3. Scripts/test/docs

| File | Vai tro | Ghi chu |
| --- | --- | --- |
| `main.py` | Entry point app | Rui ro cao neu sua sai startup |
| `fix.py` | Script patch/temporary | Can doc truoc khi giu/xoa |
| `fix_js.py` | Script patch/temporary | Can doc truoc khi giu/xoa |
| `tests/test_stability_contracts.py` | Contract tests | Dang co 2 fail baseline |
| `app/actions/edit.py.rej` | Reject file da bi xoa | Can xac dinh co con can doi chieu khong |

## 3. Phan loai file untracked

### 3.1. Can giu vi dang la thay doi co chu dich

| File | Ly do |
| --- | --- |
| `docs/CODE_CLEANUP_PHASE_PLAN.md` | Tai lieu phase plan vua tao |
| `packages/net_utils.py` | Helper SSL dang duoc cac file network import |

### 3.2. Can doc truoc khi quyet dinh

| File | Ghi chu |
| --- | --- |
| `BUG_FIX_STATUS_14.md` | Co the la tai lieu theo doi loi so 14 |
| `add_log.py` | Co ve script tam |
| `clean.py` | Co ve script tam |
| `test_pz2.py` | Co ve test tam |

### 3.3. Nghiem la file patch tam

| File |
| --- |
| `patch_edit_dialog.py` |
| `patch_edit_render.py` |
| `patch_edit_render2.py` |
| `patch_fonts.py` |
| `patch_inline.py` |
| `patch_insert.py` |
| `patch_pymupdf.py` |

### 3.4. Nghiem la artifact tam

| File | Ghi chu |
| --- | --- |
| `tmpvtacm57z.docx` | Co ve file DOCX tam |

## 4. Baseline ket qua

| Hang muc | Ket qua |
| --- | --- |
| Tracked changes | 20 file |
| Untracked files | 14 file |
| Diff size | 374 insertions, 115 deletions |
| Python compile | PASS |
| Stability contracts | 26 passed, 2 failed |
| `git diff --check` | Khong loi whitespace, chi canh bao LF/CRLF |
| Runtime code changed in Phase 0 | Khong |
| File bi xoa trong Phase 0 | Khong |

## 5. Rui ro hien tai can giu trong dau

1. Working tree dang dirty lon, khong duoc reset/checkout lung tung.
2. `packages/net_utils.py` dang untracked nhung da duoc import trong code runtime, khong duoc xoa.
3. `docs/CODE_CLEANUP_PHASE_PLAN.md` dang untracked va nen duoc giu.
4. `tests/test_stability_contracts.py` hien fail 2 test; can coi day la baseline, khong do Phase 0.
5. File binary `BAN_MO_TA_PHAN_MEM.pdf` dang modified; can xac dinh co chu dich commit hay khong truoc release.
6. Cac script `patch_*.py`, `fix.py`, `fix_js.py` chua duoc don; khong chay lai neu chua doc noi dung.

## 6. Dieu kien san sang sang Phase 1

Da dat:

- Baseline git status da ghi.
- Baseline diff stat da ghi.
- Baseline untracked files da ghi.
- Python compile pass.
- Stability contract baseline da ghi.

Co the sang Phase 1:

- Sua mojibake va message sai ngu canh.
- Chi sua cac file target Phase 1:
  - `packages/signing/shared.py`
  - `app/actions/document_ops.py`
  - `app/actions/edit.py`

Khong nen lam trong Phase 1:

- Khong xoa root junk.
- Khong sua annotation/undo.
- Khong sua print preview.
- Khong sua stamp background test.
- Khong commit neu chua duoc yeu cau.
