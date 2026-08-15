# Active Runtime Handoff - 3T Reader

Ngay cap nhat: 2026-06-26

Tai lieu nay la ban ban giao ky thuat sau cac phase cleanup. Muc tieu la giup nguoi sua tiep biet dau la luong runtime that, dau la helper, dau la code thu nghiem khong nen sua/xoa neu chua test du.

## 1. Trang thai gate hien tai

Ket qua Phase 8:

- `py_compile` runtime gate: PASS.
- `tests/test_pdf_save_helpers.py`: `14 passed`.
- `tests/test_local_server.py`: `15 passed`.
- `tests/test_stability_contracts.py`: `26 passed, 2 failed`.
- Full suite: `232 passed, 6 failed, 24 skipped`.

Ket luan:

- Chua coi automated gate la xanh hoan toan.
- Neu build noi bo de test UI thi duoc, nhung phai ghi ro known failed tests.
- Neu build release/chot ban giao, can fix hoac chap nhan ro 6 failed trong `docs/CODE_CLEANUP_PHASE8_REPORT.md`.

Known failed tests can theo doi:

- `test_package_wildcard_import_does_not_import_pymupdf`
- `test_no_fitz_in_default_path`
- `test_normalize_language_pack_payload_rejects_wrong_code`
- `test_second_instance_can_forward_pdf_path`
- `test_vietnamese_stamp_uses_unicode_font_when_available`
- `test_print_entry_uses_pdfjs_preview_for_screen_clarity`

## 2. Nguyen tac sua tiep

- Khong sua dong thoi edit, annotation, signing, OCR trong mot commit.
- Khong xoa file/module runtime neu chua co `rg` reference check va test UI.
- Khong chay lai cac script patch cu o root neu chua doc noi dung.
- Khong dung `git reset --hard`.
- Khi thao tac PDF tren Windows, uu tien staged file cung thu muc dich va atomic replace/retry.
- Moi thay doi lien quan viewer reload phai test:
  - page hien tai
  - zoom
  - scroll
  - khong blank viewer
  - khong mat overlay

## 3. Main UI va tab state

Runtime chinh:

- `app/window.py`

Vai tro:

- Tao main window/ribbon/menu.
- Noi QAction toi function trong `app/actions/*`.
- Quan ly tab qua `_tabs_data`.
- Moi tab co state:
  - `viewer`
  - `source_path`
  - `display_path`
  - `web_view`
  - `search_query`
  - `temp_path`
  - `_pdf_edit_state` neu dang edit.

Entry points dang noi trong toolbar/menu:

- Save/Save As: `save_edits()`, `save_edits_as()`.
- Edit text/image: `insert_text_to_pdf()`, `insert_image_to_pdf()`, `edit_existing_text()`, `select_inserted_object()`.
- Annotation: `highlight_text()`, `underline_text()`, `strikeout_text()`, `add_comment()`, `undo_last_edit()`.
- Signing: `check_token()`, `create_signature_field()`, `sign_document()`, `sign_with_pfx()`, `sign_handwritten()`, `verify_signed_document()`.
- OCR: `ocr_current_page()`, `ocr_full_document()`.
- AI: `open_chat_dialog()`, `open_translate_dialog()`, `open_summarize_dialog()`, `open_search_dialog()`.
- Print: `print_current_pdf()`.

Can than:

- `window.py` la file rui ro cao. Sua rong o day de gay regression UI.
- Neu them action moi, can cap nhat ca toolbar/menu/i18n label neu co.
- Neu sua close tab/close app, can dam bao pending annotation va temp path duoc flush/cleanup.

## 4. Edit text/image runtime flow

Runtime chinh:

- `app/actions/edit.py`
- `app/pdf_inline_editor.py`
- `app/webchannel.py`
- `assets/js/inline_text_bridge.js`
- `assets/js/inline_image_bridge.js`
- `assets/js/area_pick.js`
- `packages/pdf_engine/pymupdf_engine.py`
- `app/pdf_viewer.py`

Entry points:

- `insert_text_to_pdf(window)`
- `insert_image_to_pdf(window)`
- `edit_existing_text(window)`
- `select_inserted_object(window)`
- `delete_inserted_object(window)`
- `save_edits(window)`
- `save_edits_as(window)`
- `undo_last_edit(window)`

State:

- `_ensure_edit_state(window)` tao session edit.
- `_pdf_edit_state` nam trong active tab state.
- Field quan trong:
  - `original_path`
  - `base_snapshot`
  - `working_file`
  - `ops`
  - `next_id`

Render/save:

- `_render_edit_state()` rebuild `working_file` tu `base_snapshot + ops`.
- `window.viewer.update_ops()` cap nhat overlay/preview.
- `save_edits()` rebuild lan cuoi, copy atomic vao file goc, reset edit state.
- `save_edits_as()` tao ban sao, khong reset viewer bat buoc.

Bridge/JS:

- `areaPickBridge`: chon vung tren PDF.
- `inlineTextBridge`: live insert text.
- `objectActionBridge`: resize/move/rotate object da chen.
- `editExistingTextBridge`: sua text goc tu PDF.js selection payload.

Khong nham lan:

- `app/actions/edit_overlays.py` la experimental unused. Hien khong wire vao runtime edit pipeline.
- Khong dung `edit_overlays.py` lam can cu sua preview hien tai neu chua chu dong doi kien truc.

Manual test bat buoc khi sua:

- Chen text moi: font, bold, italic, underline.
- Resize to/nho, xoay, move.
- Save va Save As.
- Dong mo lai file.
- Sua text goc: boi den, sua, khong nhay ve dau trang, khong lech toa do bat thuong.
- Undo edit/object.

Automated tests lien quan:

- `tests/test_pdf_save_helpers.py`
- `tests/test_inline_editor_win.py`
- `tests/test_stability_contracts.py`

## 5. Annotation va undo runtime flow

Runtime chinh:

- `app/actions/annotate.py`
- `app/annotation_sidebar.py`
- `assets/js/pdfjs_ui_hooks.js`
- `app/pdf_viewer.py`
- `app/actions/_pdf_save.py`

Entry points:

- `highlight_text(window)`
- `underline_text(window)`
- `strikeout_text(window)`
- `add_comment(window)`
- `undo_last_annotation(window)`
- `delete_current_page(window)` hien van nam trong annotate flow.

Queue/flush:

- `_queue_annotation_op()` gom thao tac ghi PDF.
- `_flush_annotations_before_heavy_op()` phai duoc goi truoc edit/page/sign neu co pending annotation.
- `_schedule_annotation_undo_flush()` gom nhieu undo lien tiep de giam lag va stale overlay.
- `compact_annotation_overlay_state()` don overlay state sau thao tac.

Can than:

- UI overlay va PDF annotation la 2 lop khac nhau.
- Undo phai xoa overlay UI ngay, nhung flush PDF co the batch ngan.
- Khong clear toan bo overlay state neu viewer chua reload dung cach.

Manual test bat buoc khi sua:

- To sang 5 doan.
- Gach chan 5 doan.
- Gach ngang 5 doan.
- Them ghi chu.
- Bam `Ctrl+Z` lien tuc.
- Dong mo lai file de xac nhan PDF that khong con annotation da undo.

Automated tests lien quan:

- `tests/test_annotation_queue.py`
- `tests/test_viewer_annotation_regressions.py`
- `tests/test_pr7_helpers.py::test_delete_mark_annotations_by_ids`

## 6. Signing runtime flow

Runtime chinh:

- `app/actions/sign.py`
- `packages/signing/shared.py`
- `packages/signing/windows_provider.py`
- `packages/signing/usb_worker.py`
- `app/local_server.py`
- `app/pdf_viewer.py`
- `assets/js/pdfjs_ui_hooks.js`

Entry points:

- `check_token(window)`
- `create_signature_field(window)`
- `sign_document(window)`
- `sign_with_pfx(window)`
- `sign_handwritten(window)`
- `verify_signed_document(window)`

Background/worker:

- `_run_usb_signing_task()` dung worker/thread de khong khoa UI.
- USB token monitor trong `app/window.py` dung QThread worker pattern.

PDF update:

- Signing ghi staged PDF bang `make_staged_pdf_path()`.
- Sau khi ky/xu ly xong, reload qua `replace_document_with_staged()`.
- `LocalPDFJSServer.invalidate_pdf_cache()` phai duoc goi khi PDF thay doi.

Viewer/click signature:

- `app/local_server.py` cung cap `/sigmeta`.
- `app/pdf_viewer.py` co `signature_clicked`.
- `assets/js/pdfjs_ui_hooks.js` gan hook click tren signature overlay/widget.

Can than:

- Ky so la luong rui ro cao. Khong sua message/UI ma bo qua test click chu ky.
- File da ky khi edit PDF se mat hop le chu ky. `edit.py` da co warning truoc khi edit PDF co signature.
- Khi ky xong phai test hien thi truc quan trong 3T Reader va app PDF khac.

Manual test bat buoc khi sua:

- Kiem tra USB co/khong co.
- Ky vao o ky.
- Ky truc tiep khong qua o ky.
- Ky PFX.
- Ky tay/chon anh chu ky.
- Click chu ky xem thong tin.
- Dong mo lai trong 3T Reader.
- Mo file bang app PDF khac.
- Xac nhan giu page/zoom/scroll hop ly.

Automated tests lien quan:

- `tests/test_signing_pr4.py`
- `tests/test_stability_contracts.py`
- `tests/test_windows_provider.py`
- `tests/test_signature_templates.py`

## 7. Viewer reload, cache va temp file

Runtime chinh:

- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/actions/_pdf_save.py`

Viewer:

- `PDFViewerWidget.load_pdf()` load PDF qua local PDF.js server.
- `PDFViewerWidget.reload_soft()` reload PDF tai cho, co fallback `window.location.replace`.
- `PDFViewerWidget.update_ops()` cap nhat overlay edit ops.

Local server:

- `LocalPDFJSServer.viewer_url()` tao URL PDF.js.
- `cache_bust_token()` them token theo mtime/size/version.
- `invalidate_pdf_cache()` clear display/signature cache theo path.
- `/pdf` stream PDF.
- `/sigmeta` tra target/click metadata cho signature.

PDF save helper:

- `make_staged_pdf_path()` tao staged file cung thu muc target.
- `replace_document_with_staged()` replace atomic va reload viewer.
- `reload_document()` giu page/zoom neu co the.
- `prune_stale_app_temp_files()` cleanup temp cu an toan.
- `collect_active_pdf_temp_paths()` giu file dang active khong bi prune.

Temp/cache:

- `%TEMP%\reader_pdf_edit`: edit session temp.
- `%TEMP%\reader_pdf_sig`: signature image temp.
- `.3t_*` trong thu muc PDF dich: staged PDF.

Manual test bat buoc khi sua:

- Xoa trang/chen trang khong blank viewer.
- Danh so trang/xoa so trang khong blank viewer.
- Ky xong khong nhay ve dau trang bat thuong.
- Chen text/save xong khong mat overlay.
- Mo PDF lon > 30MB neu co.

Automated tests lien quan:

- `tests/test_pdf_save_helpers.py`
- `tests/test_local_server.py`
- `tests/test_local_server_security.py`
- `tests/test_viewer_annotation_regressions.py`

## 8. Page operations va page numbers

Runtime chinh:

- `app/actions/pages.py`
- `app/actions/document_ops.py`
- `app/actions/_pdf_save.py`

Entry points:

- `delete_current_page(window)` trong `app/actions/annotate.py`.
- `rotate_pages_action(window)`
- `merge_pdfs_action(window)`
- `split_pdf_action(window)`
- `add_page_numbers(window)`
- `remove_page_numbers(window)`

Can than:

- Non-PDF converted documents can co read path va target/display path rieng.
- Page number chi nen ap dung PDF; file khong phai PDF can thong bao ro.
- Page ops phai reload dung source/temp/display path.

Manual test bat buoc:

- Xoa trang.
- Chen trang sau.
- Xoay trang.
- Danh so trang.
- Xoa so trang.
- Save/Save As sau thao tac trang.

## 9. OCR, AI chat, translate va TTS

OCR runtime:

- `app/actions/ocr.py`
- `app/ocr_dialog.py`
- `packages/ocr/engine.py`

Entry points:

- `ocr_current_page(window)`
- `ocr_full_document(window)`

AI chat runtime:

- `app/actions/ai_actions.py::open_chat_dialog()`
- `app/ai_chat_dialog.py`
- `packages/ai/chat_pdf.py`

Chat history:

- `PDFChatSession.history` luu lich su.
- History duoc persist theo identity path trong `packages/ai/chat_pdf.py`.

Translate runtime:

- `app/actions/ai_actions.py::open_translate_dialog()`
- `app/ai_translate_dialog.py`
- `packages/ai/translate.py`
- `app/language_manager.py`

Known risk:

- Phase 8 full suite con fail `_normalize_language_pack_payload(...)` vi wrong-code payload tra `None`, test ky vong `{}`.

TTS runtime:

- `app/actions/tts_dialog.py`
- `app/actions/piper_tts_manager.py`

Manual test bat buoc:

- OCR trang va OCR tai lieu, overlay/progress khong chong.
- Chat PDF cau ngan/cau dai, history khong mat trong session.
- Doi ngon ngu dich 2-3 lan, khong load mai.
- TTS auto language voi van ban tieng Viet/Anh.

## 10. Print runtime

Runtime chinh:

- `app/window.py::print_current_pdf()`
- `app/window.py::_configured_pdf_printer()`
- `app/window.py::_do_print_pages()`

Known risk:

- Phase 8 stability contract con fail vi source khong co `"app.pdfViewer.scrollMode = 3"`.
- Print preview single-page mode can test UI that, nhat la sau khi doi qua 2 trang/nhieu trang roi quay ve 1 trang.

Manual test bat buoc:

- In 1 trang.
- In 2 trang.
- In nhieu trang.
- Quay lai 1 trang.
- Page orientation va preview khong bi sai.

## 11. Helper-only / experimental / archive

Khong coi la runtime chinh:

- `app/actions/edit_overlays.py`
  - Experimental unused.
  - Da danh dau docstring.
  - Khong import/call trong runtime hien tai.
- `debug/phase7_20260626__*`
  - Archive file tam root Phase 7.
  - Khong phai source runtime.
- Root `patch_*.py`, `fix.py`, `fix_js.py`
  - Mot so file van tracked/modified.
  - Khong chay neu chua doc noi dung.
  - Nen xu ly bang commit cleanup rieng sau khi runtime fix da commit.

## 12. Manual checklist truoc build

Truoc build noi bo:

1. Mo PDF thuong.
2. Chen text: font, bold, italic, underline, resize, xoay, save/save as.
3. Sua text goc: boi den, sua, khong nhay dau trang, khong lech toa do.
4. Annotation: to sang, gach chan, gach ngang, ghi chu, Ctrl+Z lien tuc.
5. Page ops: xoa trang, chen trang sau, danh so trang, xoa so trang.
6. OCR trang va OCR tai lieu.
7. Chat PDF cau ngan/cau dai, history con trong phien.
8. Translate doi ngon ngu nhieu lan.
9. Signing: USB co/khong co, ky o ky, ky truc tiep, ky PFX, ky tay, click xem thong tin.
10. Print: 1 trang, 2 trang, nhieu trang, quay lai 1 trang.

Tieu chi pass:

- Khong crash.
- Khong blank viewer.
- Khong mat overlay sau thao tac.
- Khong hien chuoi mojibake.
- Khong mat tinh nang da co.

## 13. Tai lieu lien quan

- `docs/CODE_CLEANUP_PHASE_PLAN.md`
- `docs/CODE_CLEANUP_PHASE0_BASELINE.md`
- `docs/CODE_CLEANUP_PHASE1_REPORT.md`
- `docs/CODE_CLEANUP_PHASE2_REPORT.md`
- `docs/CODE_CLEANUP_PHASE3_REPORT.md`
- `docs/CODE_CLEANUP_PHASE4_REPORT.md`
- `docs/CODE_CLEANUP_PHASE5_REPORT.md`
- `docs/CODE_CLEANUP_PHASE6_REPORT.md`
- `docs/CODE_CLEANUP_PHASE7_REPORT.md`
- `docs/CODE_CLEANUP_PHASE8_REPORT.md`
- `BUG_FIX_STATUS_14.md`
