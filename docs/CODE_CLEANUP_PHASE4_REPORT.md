# Phase 4 Report - Edit pipeline mapping and unused overlay module

Ngay thuc hien: 2026-06-26

Pham vi Phase 4 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Xac dinh code nao la runtime that, code nao la thu nghiem.
- Lap mapping luong edit.
- Kiem tra `app/actions/edit_overlays.py`.
- Chua xoa code neu chua co bang chung day du.
- Khong commit.

## 1. File da doc

Da doc cac file trong scope:

- `app/actions/edit.py`
- `app/actions/edit_overlays.py`
- `app/pdf_viewer.py`
- `assets/js/inline_text_bridge.js`
- `app/pdf_inline_editor.py`
- `app/webchannel.py`

## 2. Mapping luong edit runtime hien tai

| Luong | Entry point | Bridge/JS | Viewer/render | Ket luan |
| --- | --- | --- | --- | --- |
| Chen text moi | `app/actions/edit.py::insert_text_to_pdf()` | `app/pdf_inline_editor.py::run_inline_text()`, `assets/js/inline_text_bridge.js`, `inlineTextBridge` | `_render_edit_state()`, `pdf_viewer.update_ops()`, `reload_soft()` | Runtime chinh |
| Chen anh | `app/actions/edit.py::insert_image_to_pdf()` | `app/pdf_inline_editor.py::run_inline_image()`, `inline_image_bridge.js`, `inlineImageBridge` | `_render_edit_state()`, `pdf_viewer.update_ops()`, `reload_soft()` | Runtime chinh |
| Chon/xoay/resize/di chuyen object | `app/actions/edit.py::select_inserted_object()` | `areaPickBridge`, `objectActionBridge`, `_SHOW_OBJECT_WITH_HANDLES_JS` | `_run_object_action_session()`, `_render_edit_state()`, `pdf_viewer.update_ops()` | Runtime chinh |
| Sua text da chen | `app/actions/edit.py::edit_text_object()` | Dialog Python `_TextEditDialog`, live preview JS trong `edit.py` | `_render_edit_state()` | Runtime chinh |
| Sua text goc PDF | `app/actions/edit.py::edit_existing_text()` | PDF.js selection payload, `editExistingTextBridge` proxy co san trong `app/webchannel.py` | Tao op redact/text, `_render_edit_state()`, `reload_document(... soft_reload=True)` | Runtime chinh |
| Xoa object da chen | `app/actions/edit.py::delete_inserted_object()` | Area pick | `_render_edit_state()` hoac `_reset_edit_state()` khi het ops | Runtime chinh |
| Che vung/ve tu do | `app/actions/edit.py::redact_area()`, `draw_on_pdf()` | Area pick/dialog ve | `_render_edit_state()` | Runtime chinh |
| Save/Save As | `app/actions/edit.py::save_edits()`, `save_edits_as()` | Khong dung JS bridge moi | `get_pdf_engine().rebuild_pdf_with_ops()` va copy atomic | Runtime chinh |
| Deferred edit overlay | `app/actions/edit_overlays.py` | `.t3-edit-overlay` | Khong thay noi goi runtime | Experimental unused |

## 3. Ket qua kiem tra `edit_overlays.py`

Lenh:

```powershell
rg -n "edit_overlays|add_edit_overlay|remove_edit_overlay|clear_edit_overlays|get_overlay_ops_for_save|t3-edit-overlay" app packages tests assets docs
```

Ket qua:

- Trong `app`, `packages`, `tests`, `assets`: chi thay cac ham/class CSS nam trong chinh `app/actions/edit_overlays.py`.
- Khong thay import/goi:
  - `add_edit_overlay`
  - `remove_edit_overlay`
  - `clear_edit_overlays`
  - `get_overlay_ops_for_save`
- Trong `docs`: co ban copy source/tai lieu phase plan, khong phai runtime.

Ket luan:

- `app/actions/edit_overlays.py` hien khong duoc wire vao runtime.
- Module nay khong phai luong edit dang chay.
- Khong nen xoa ngay vi co the la y tuong deferred overlay can giu de doi chieu sau.

## 4. Thay doi da ap dung

Da them canh bao vao docstring dau file `app/actions/edit_overlays.py`:

```text
IMPORTANT: this module is currently not wired into the runtime edit pipeline.
The active pipeline lives in app.actions.edit, app.pdf_inline_editor and
app.pdf_viewer.update_ops/reload_soft.
```

Pham vi anh huong:

- Chi la tai lieu/comment trong module.
- Khong thay doi ham, import, signal, UI, save, reload, overlay.

Ly do:

- Tranh ky thuat vien sau doc nham `edit_overlays.py` la pipeline dang chay.
- Giu lai thiet ke experimental de tham khao, khong xoa khi chua co test edit day du.

## 5. Kiem tra da chay

### 5.1. Python compile

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m py_compile app\actions\edit.py app\actions\edit_overlays.py app\pdf_viewer.py app\pdf_inline_editor.py app\webchannel.py
```

Ket qua:

```text
PASS
```

### 5.2. Stability contract test

Lenh:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\test_stability_contracts.py -q --tb=short
```

Ket qua:

```text
26 passed, 2 failed
```

2 failed giong baseline Phase 0/1/2/3:

- `test_vietnamese_stamp_uses_unicode_font_when_available`
- `test_print_entry_uses_pdfjs_preview_for_screen_clarity`

Nhan dinh:

- Phase 4 khong lam tang so fail.
- 2 fail nay khong thuoc scope Phase 4.

## 6. Rui ro con lai

- Chua test thu cong cac luong edit trong UI.
- `edit_overlays.py` van ton tai trong source, nhung da duoc danh dau experimental unused.
- Neu sau nay muon xoa han `edit_overlays.py`, nen lam commit rieng sau khi test:
  - chen text
  - chen anh
  - resize/xoay/di chuyen
  - sua text goc
  - Ctrl+Z edit
  - Save/Save As

## 7. Khuyen nghi tiep theo

- Chua xoa `app/actions/edit_overlays.py` trong dot nay.
- Neu can don manh hon o phase sau, co 2 lua chon:
  - Archive module thanh tai lieu thiet ke trong `docs/archived_design_notes/`.
  - Xoa file trong commit rieng sau khi test UI day du.
- Khong nen wire module nay vao runtime neu chua co ke hoach thay doi kien truc edit, vi se tao them mot co che overlay song song voi `pdf_viewer.update_ops()`.

## 8. Ket luan

Phase 4 da hoan thanh:

- Da lap mapping luong edit runtime.
- Da xac nhan `edit_overlays.py` la experimental unused.
- Da them canh bao vao docstring de tranh sua nham.
- `py_compile` pass.
- Contract test giu baseline `26 passed, 2 failed`.
- Chua xoa code va chua commit theo `FIX_RULES.md`.
