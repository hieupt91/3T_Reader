# Phase 5 Report - Annotation overlay and Ctrl+Z stability

Ngay thuc hien: 2026-06-26

Pham vi Phase 5 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Giam tinh trang UI con hien to/gach sau khi undo.
- Giam lag khi bam `Ctrl+Z` nhieu lan.
- Chi cham luong annotation/overlay/undo.
- Khong xoa tinh nang.
- Khong commit.

## 1. File da doc

Da doc cac file trong scope:

- `app/actions/annotate.py`
- `app/actions/_pdf_save.py`
- `app/pdf_viewer.py`
- `assets/js/pdfjs_ui_hooks.js`

Da doc lai quy uoc:

- `FIX_RULES.md`
- `docs/CODE_CLEANUP_PHASE_PLAN.md`

## 2. Hien trang truoc khi sua

Trong `app/actions/annotate.py` da co cac co che quan trong:

- `_remove_overlay_mark()` de xoa overlay mark tren UI.
- `compact_annotation_overlay_state()` de don state overlay annotation.
- `_flush_annotation_queue()` de ghi cac thao tac annotation vao PDF.
- `_refresh_viewer_after_annotation_change()` de refresh viewer sau khi PDF thay doi.

Van de con lai dung voi Phase 5:

- Khi undo mark/note, code co the ghi PDF va refresh viewer qua sat tung thao tac.
- Neu bam `Ctrl+Z` lien tiep, moi thao tac undo de tao mot dot flush/reload rieng, de gay lag.
- Overlay tren UI can bien mat ngay, nhung ghi PDF/reload co the gom lai ngan de on dinh hon.

## 3. Thay doi da ap dung

Chi sua runtime trong:

- `app/actions/annotate.py`

### 3.1. Them batch flush cho undo annotation

Them helper:

```python
_schedule_annotation_undo_flush(window, target_path: str, *, delay_ms: int = 320)
```

Tac dung:

- Gom nhieu thao tac undo lien tiep trong khoang ngan.
- Chi flush annotation queue mot lan o timer moi nhat.
- Chi refresh viewer mot lan sau khi flush thanh cong.
- Co fallback neu khong import duoc `QTimer`: flush va refresh ngay.

Co che chong timer cu:

- Dung `window._annotation_undo_flush_seq`.
- Moi lan goi helper se tang sequence.
- Timer cu se tu bo qua neu khong con la sequence moi nhat.

### 3.2. Sua undo mark

Trong `undo_last_annotation()` voi `kind == "mark"`:

- Giu hanh vi xoa overlay UI ngay bang `_remove_overlay_mark(window, mark_id)`.
- Khong flush PDF/reload viewer ngay tung lan nua.
- Queue thao tac xoa annotation voi `delay_ms=500`.
- Goi `_schedule_annotation_undo_flush(window, path)` de gom flush/reload.

Muc tieu:

- UI bien mat mark ngay.
- PDF van duoc ghi that.
- Nhieu lan `Ctrl+Z` lien tiep khong tao nhieu reload sat nhau.

### 3.3. Sua undo note

Trong `undo_last_annotation()` voi `kind == "note_add"`:

- Giu hanh vi danh dau tombstone note trong overlay state.
- Giu JS xoa note truc quan ngay neu webview san sang.
- Khong flush PDF/reload viewer ngay tung lan nua.
- Queue thao tac xoa note voi `delay_ms=500`.
- Goi `_schedule_annotation_undo_flush(window, path)` de gom flush/reload.

### 3.4. Don helper refresh cu khong con dung

Sau khi doi sang `_schedule_annotation_undo_flush()`, helper cu:

```python
_schedule_annotation_viewer_refresh()
```

khong con caller runtime trong `annotate.py`, nen da bo de tranh co 2 co che refresh song song.

## 4. Pham vi anh huong

Anh huong truc tiep:

- Undo to sang.
- Undo mau to.
- Undo gach duoi.
- Undo gach ngang.
- Undo ghi chu moi them.

Khong thay doi:

- Tao annotation moi.
- Luu PDF annotation.
- Save/Save As.
- Text insert/edit.
- Ky so.
- OCR.
- Viewer core.

## 5. Kiem tra da chay

### 5.1. Python compile

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\annotate.py app\actions\_pdf_save.py app\pdf_viewer.py
```

Ket qua:

```text
PASS
```

### 5.2. Annotation targeted tests

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_annotation_queue.py tests\test_pr7_helpers.py::test_delete_mark_annotations_by_ids tests\test_viewer_annotation_regressions.py -q --tb=short
```

Ket qua:

```text
16 passed
```

### 5.3. Stability contract test

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_stability_contracts.py -q --tb=short
```

Ket qua:

```text
26 passed, 2 failed
```

2 failed giong baseline Phase 0/1/2/3/4:

- `test_vietnamese_stamp_uses_unicode_font_when_available`
- `test_print_entry_uses_pdfjs_preview_for_screen_clarity`

Nhan dinh:

- Phase 5 khong lam tang so failed baseline.
- 2 failed nay khong thuoc scope Phase 5.

## 6. Test thu cong can lam tren UI

Can test thu cong cac luong sau:

1. To sang 5-10 doan lien tiep, bam `Ctrl+Z` tung cai.
2. To sang/gach duoi/gach ngang xen ke, bam `Ctrl+Z` nhanh nhieu lan.
3. Them ghi chu, bam `Ctrl+Z`.
4. Sau khi undo het, khong con overlay mau/to/gach tren UI.
5. Luu file, dong mo lai, cac annotation da undo khong con trong PDF.
6. Kiem tra scroll/page hien tai khong bi nhay bat thuong sau batch undo.

## 7. Rui ro con lai

- PDF write/reload sau undo duoc delay ngan 320ms, nen can test UI that de xac nhan cam giac thao tac.
- Neu may cham va PDF lon, reload sau batch van co the mat thoi gian, nhung se it dot reload hon truoc.
- Worktree dang co nhieu thay doi cu tu cac phase/loi truoc. Phase 5 chi them co che batch undo trong `app/actions/annotate.py`.

## 8. Ket luan

Phase 5 da hoan thanh:

- Overlay undo van xoa ngay tren UI.
- Ghi PDF va refresh viewer sau undo duoc gom lai.
- Giam nguy co chong overlay va lag khi bam `Ctrl+Z` lien tiep.
- `py_compile` pass.
- Annotation targeted tests pass `16/16`.
- Stability contract giu baseline `26 passed, 2 failed`.
- Chua commit theo `FIX_RULES.md`.
