# Phase 8 Report - Test gate before build

Ngay thuc hien: 2026-06-26

Pham vi Phase 8 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Xac nhan viec cleanup khong lam mat tinh nang.
- Chay gate tu dong truoc build.
- Ghi lai manual checklist can test tren UI.
- Khong sua runtime trong phase nay.
- Khong commit.

## 1. File da doc

Da doc:

- `docs/CODE_CLEANUP_PHASE_PLAN.md`
- `FIX_RULES.md`
- `git status`

## 2. Trang thai worktree truoc Phase 8

Worktree dang co nhieu thay doi tu cac phase/bugfix truoc:

- Runtime changed: `app/actions/edit.py`, `app/actions/annotate.py`, `app/actions/_pdf_save.py`, `app/window.py`, `app/local_server.py`, signing/AI/helper files...
- Docs/report moi: `docs/CODE_CLEANUP_PHASE0_BASELINE.md` den `docs/CODE_CLEANUP_PHASE7_REPORT.md`.
- Root junk untracked da duoc archive trong Phase 7 vao `debug/phase7_20260626__*` va khong con hien trong root.

Phase 8 khong sua code runtime; chi chay gate va ghi report.

## 3. Automated gate da chay

### 3.1. Python compile gate

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\edit.py app\actions\annotate.py app\actions\document_ops.py app\actions\_pdf_save.py app\pdf_viewer.py app\window.py app\local_server.py packages\signing\shared.py packages\ai\translate.py
```

Ket qua:

```text
PASS
```

Ket luan:

- Cac file runtime chinh trong Phase 8 compile duoc.
- Khong co loi cu phap/import-time syntax o gate toi thieu.

### 3.2. Stability contracts

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/test_stability_contracts.py -q --tb=short
```

Ket qua:

```text
26 passed, 2 failed
```

Failed:

- `test_vietnamese_stamp_uses_unicode_font_when_available`
  - Ly do: `style.background is None`.
  - Day la baseline fail da xuat hien tu cac phase truoc.
- `test_print_entry_uses_pdfjs_preview_for_screen_clarity`
  - Ly do: source khong co chuoi `"app.pdfViewer.scrollMode = 3"`.
  - Day la baseline fail da xuat hien tu cac phase truoc.

### 3.3. PDF save helpers

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/test_pdf_save_helpers.py -q --tb=short
```

Ket qua:

```text
14 passed
```

### 3.4. Local server tests

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/test_local_server.py -q --tb=short
```

Ket qua:

```text
15 passed
```

### 3.5. Full test suite

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests -q --tb=short
```

Ket qua:

```text
232 passed, 6 failed, 24 skipped
```

Failed:

- `tests/test_pdf_pipeline.py::TestNoPyMuPdfInDefaultPath::test_package_wildcard_import_does_not_import_pymupdf`
  - `fitz` da co trong `sys.modules`.
  - Co kha nang la test-order/environment issue hoac module nao do import PyMuPDF truoc do.
- `tests/test_pr7_helpers.py::test_normalize_language_pack_payload_rejects_wrong_code`
  - `_normalize_language_pack_payload(...)` tra `None`, test ky vong `{}`.
- `tests/test_single_instance.py::test_second_instance_can_forward_pdf_path`
  - `received == []`, test ky vong nhan duoc path cua instance thu hai.
- `tests/test_smoke_windows.py::TestWindowsPdfEngine::test_no_fitz_in_default_path`
  - `fitz_loaded` la `True`.
- `tests/test_stability_contracts.py::test_vietnamese_stamp_uses_unicode_font_when_available`
  - `style.background is None`.
- `tests/test_stability_contracts.py::test_print_entry_uses_pdfjs_preview_for_screen_clarity`
  - Thieu contract string `"app.pdfViewer.scrollMode = 3"`.

## 4. Danh gia gate

Trang thai automated gate:

```text
PARTIAL PASS / NOT GREEN
```

Da pass:

- `py_compile` gate toi thieu.
- `tests/test_pdf_save_helpers.py`.
- `tests/test_local_server.py`.
- Da so full suite: `232 passed`.

Chua pass:

- Full suite con 6 failed.
- Stability contracts con 2 failed baseline.

Ket luan build gate:

- Chua nen coi day la build gate xanh hoan toan.
- Neu can build test noi bo van co the build, nhung phai ghi ro known failed tests.
- Neu build release/chot ban giao, can xu ly 6 failed hoac danh dau accepted baseline co chu ky xac nhan.

## 5. Manual UI checklist theo Phase 8

Chua the xac nhan PASS tu dong cac muc manual sau, vi can thao tac truc tiep tren UI:

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

## 6. Rui ro con lai

- Full suite chua xanh do 6 failed.
- Mot so failed la baseline da biet, nhung van la build/release risk neu khong duoc chap nhan ro.
- Manual UI checklist chua duoc xac nhan trong Phase 8 nay.
- Worktree dang dirty voi nhieu thay doi runtime/docs; can commit chia nho truoc khi build release de de rollback.

## 7. De xuat xu ly tiep

Thu tu nen xu ly neu muon gate xanh hon:

1. Fix `test_normalize_language_pack_payload_rejects_wrong_code` vi pham vi nho.
2. Dieu tra `fitz` import order/default path.
3. Dieu tra `single_instance` forwarding.
4. Quyet dinh contract cho Vietnamese stamp background.
5. Quyet dinh contract in/preview `scrollMode = 3`.
6. Chay lai full suite.
7. Mo app va test manual checklist.

## 8. Ket luan

Phase 8 da hoan thanh phan automated gate:

- Da doc plan va `FIX_RULES.md`.
- Da chay `py_compile` toi thieu: PASS.
- Da chay 3 nhom pytest trong plan:
  - stability contracts: `26 passed, 2 failed`.
  - pdf save helpers: `14 passed`.
  - local server: `15 passed`.
- Da chay full suite bo sung: `232 passed, 6 failed, 24 skipped`.
- Chua sua runtime trong Phase 8.
- Chua commit theo `FIX_RULES.md`.
