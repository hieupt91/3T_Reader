# Phase 9 Report - Documentation and handoff

Ngay thuc hien: 2026-06-26

Pham vi Phase 9 theo `docs/CODE_CLEANUP_PHASE_PLAN.md`:

- Tai lieu hoa luong runtime chinh.
- Giam nguy co sua nham code dang do dang/experimental.
- Ghi file nao la entry point, helper, file can tranh sua neu chua test.
- Ghi manual checklist bat buoc truoc build.
- Khong sua runtime.
- Khong commit.

## 1. File da doc

Da doc:

- `docs/CODE_CLEANUP_PHASE_PLAN.md`
- `FIX_RULES.md`
- `BUG_FIX_STATUS_14.md`
- `docs/DEEP_BUGFIX_PHASE_PLAN.md`
- Cac file runtime de lay entry point:
  - `app/window.py`
  - `app/actions/edit.py`
  - `app/actions/annotate.py`
  - `app/actions/sign.py`
  - `app/actions/_pdf_save.py`
  - `app/pdf_viewer.py`
  - `app/local_server.py`
  - `app/actions/pages.py`
  - `app/actions/document_ops.py`
  - `app/actions/ocr.py`
  - `app/ai_chat_dialog.py`
  - `app/ai_translate_dialog.py`
  - `packages/ai/chat_pdf.py`
  - `packages/ai/translate.py`
  - `app/language_manager.py`

## 2. Tai lieu moi da tao

Da tao:

- `docs/ACTIVE_RUNTIME_HANDOFF.md`

Noi dung chinh:

- Trang thai gate hien tai tu Phase 8.
- Nguyen tac sua tiep.
- Main UI va tab state.
- Edit text/image runtime flow.
- Annotation/undo runtime flow.
- Signing runtime flow.
- Viewer reload/cache/temp flow.
- Page operations va page numbers.
- OCR, AI chat, translate, TTS.
- Print runtime.
- Helper-only / experimental / archive.
- Manual checklist truoc build.
- Tai lieu lien quan.

Ly do tao file rieng:

- `docs/DEEP_BUGFIX_PHASE_PLAN.md` la ke hoach bugfix chuyen sau cu va da dai.
- Phase 9 can mot file handoff ngan gon hon, tap trung vao runtime active hien tai.
- Tranh tron ke hoach cu voi mapping ban giao moi.

## 3. File tracking da cap nhat

Da cap nhat:

- `BUG_FIX_STATUS_14.md`

Noi dung them:

- Ghi chu "Ghi Chu Ban Giao Phase 9".
- Link toi `docs/ACTIVE_RUNTIME_HANDOFF.md`.
- Link toi `docs/CODE_CLEANUP_PHASE8_REPORT.md`.
- Nhac lai gate hien tai:
  - `py_compile`: PASS.
  - `tests/test_pdf_save_helpers.py`: `14 passed`.
  - `tests/test_local_server.py`: `15 passed`.
  - `tests/test_stability_contracts.py`: `26 passed, 2 failed`.
  - Full suite: `232 passed, 6 failed, 24 skipped`.
- Nhac can fix/chap nhan 6 failed tests va test UI thu cong truoc build release.

## 4. Mapping runtime da ghi trong handoff

### 4.1. Edit text/image

Entry points:

- `insert_text_to_pdf()`
- `insert_image_to_pdf()`
- `edit_existing_text()`
- `select_inserted_object()`
- `delete_inserted_object()`
- `save_edits()`
- `save_edits_as()`
- `undo_last_edit()`

Files:

- `app/actions/edit.py`
- `app/pdf_inline_editor.py`
- `app/webchannel.py`
- `assets/js/inline_text_bridge.js`
- `assets/js/inline_image_bridge.js`
- `assets/js/area_pick.js`
- `packages/pdf_engine/pymupdf_engine.py`
- `app/pdf_viewer.py`

### 4.2. Annotation/undo

Entry points:

- `highlight_text()`
- `underline_text()`
- `strikeout_text()`
- `add_comment()`
- `undo_last_annotation()`

Files:

- `app/actions/annotate.py`
- `app/annotation_sidebar.py`
- `assets/js/pdfjs_ui_hooks.js`
- `app/pdf_viewer.py`
- `app/actions/_pdf_save.py`

### 4.3. Signing

Entry points:

- `check_token()`
- `create_signature_field()`
- `sign_document()`
- `sign_with_pfx()`
- `sign_handwritten()`
- `verify_signed_document()`

Files:

- `app/actions/sign.py`
- `packages/signing/shared.py`
- `packages/signing/windows_provider.py`
- `packages/signing/usb_worker.py`
- `app/local_server.py`
- `app/pdf_viewer.py`
- `assets/js/pdfjs_ui_hooks.js`

### 4.4. Viewer reload/cache/temp

Entry points/helpers:

- `PDFViewerWidget.load_pdf()`
- `PDFViewerWidget.reload_soft()`
- `PDFViewerWidget.update_ops()`
- `LocalPDFJSServer.viewer_url()`
- `LocalPDFJSServer.cache_bust_token()`
- `LocalPDFJSServer.invalidate_pdf_cache()`
- `make_staged_pdf_path()`
- `replace_document_with_staged()`
- `reload_document()`
- `prune_stale_app_temp_files()`

Files:

- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/actions/_pdf_save.py`

## 5. File/module can tranh sua nham

Da ghi ro trong handoff:

- `app/actions/edit_overlays.py`
  - Experimental unused.
  - Khong wire vao runtime edit pipeline hien tai.
- `debug/phase7_20260626__*`
  - Archive root junk Phase 7.
  - Khong phai runtime.
- Root `patch_*.py`, `fix.py`, `fix_js.py`
  - Khong chay neu chua doc noi dung.
  - Nen cleanup bang commit rieng sau khi runtime da commit.

## 6. Kiem tra da chay

Phase 9 la docs-only, khong sua runtime nen khong chay lai full test.

Da kiem tra bang `rg` trong qua trinh lap tai lieu:

- Entry points edit.
- Entry points annotation.
- Entry points signing.
- Viewer reload/cache/temp helpers.
- AI/OCR/translate references.
- `edit_overlays.py` experimental status.

Gate tu dong gan nhat lay tu Phase 8:

- `py_compile`: PASS.
- Full suite: `232 passed, 6 failed, 24 skipped`.

## 7. Rui ro con lai

- Manual UI checklist van chua duoc xac nhan PASS.
- Automated gate chua xanh hoan toan vi 6 failed tests.
- Worktree dang dirty voi nhieu thay doi runtime/docs; nen chia commit nho truoc build release.
- `docs/DEEP_BUGFIX_PHASE_PLAN.md` chua duoc rewrite, vi Phase 9 da tao handoff rieng de tranh churn lon.

## 8. Ket luan

Phase 9 da hoan thanh:

- Da tao `docs/ACTIVE_RUNTIME_HANDOFF.md`.
- Da cap nhat `BUG_FIX_STATUS_14.md`.
- Da ghi mapping luong runtime chinh.
- Da ghi file helper/experimental khong nen sua nham.
- Da ghi manual checklist truoc build.
- Khong sua runtime.
- Chua commit theo `FIX_RULES.md`.
