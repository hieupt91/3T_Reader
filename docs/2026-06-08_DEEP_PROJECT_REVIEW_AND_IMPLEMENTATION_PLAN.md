# Bao cao deep review du an 3T Reader Phase 1 Win

Ngay lap: 2026-06-08

Pham vi: Doc va doi chieu toan bo cau truc chinh cua du an `3T_Reader_Phase1_Win`, cac file Markdown trong du an, ma nguon Python/JavaScript lien quan den viewer, annotation, edit, sign, OCR, AI, license, updater, build/installer va test. Bao cao nay khong sua code ung dung, chi tao file tong hop moi.

## 1. Ket luan ngan gon

Du an da co nen tang san pham ro: Windows desktop PDF reader/editor dung PyQt/WebEngine + PDF.js, engine PDF thuong mai-than-thien dua tren pikepdf/reportlab/pypdfium2, ky so bang pyHanko/PKCS#11/PFX, OCR Tesseract, AI da nha cung cap, license/update qua VPS, va bo test kha day cho logic nen.

Trang thai hien tai: phu hop giai doan "Phase 1 technical beta", chua nen gan nhan "commercial-ready" hoac "phase1-win-ready" cho den khi xu ly cac diem sau:

- Loai bo hoac tach optional duong `fitz`/PyMuPDF trong luong ky tay/con dau, vi tai lieu compliance dang yeu cau khong ship PyMuPDF trong ban thuong mai.
- Sua xung dot phim tat `Ctrl+Shift+S` giua "Luu thanh file moi" va "Tom tat AI".
- Lam ro hoac kich hoat USB token monitor: `app/window.py:2130` hien la ham `pass`.
- Gioi han local PDF server theo danh sach file duoc mo trong session, thay vi chap nhan moi duong dan PDF tuyet doi hop le.
- Hoan thien kiem thu WebEngine/GUI thu cong hoac E2E: bo test Python pass, nhung chua thay bang chung automation cho hanh trinh that tren giao dien.
- Dong bo tai lieu release/compliance vi mot so Markdown con lech ve Python version, icon provenance, trang thai PDF.js va cac viec manual.

Ket qua test da chay: `.\.venv313\Scripts\python.exe -m pytest` => `171 passed, 24 skipped in 37.90s`.

Cap nhat sau batch trien khai dau tien trong ngay 2026-06-08:

- Da chuyen luong ky tay/con dau trong `app/actions/sign.py` khoi `fitz`/PyMuPDF sang `get_pdf_engine().rebuild_pdf_with_ops()` voi op `image`.
- Da doi shortcut AI Tom tat tu `Ctrl+Shift+S` sang `Ctrl+Alt+S`, giu `Ctrl+Shift+S` cho Save As.
- Da bat USB token monitor bang worker nen QThread, khong con stub `pass` va khong chay subprocess chan UI thread.
- Da them allowed PDF registry cho `LocalPDFJSServer`; endpoint `/pdf` chi phuc vu file da duoc viewer dang ky trong session server.
- Da sua `save_edits_quiet()` de dung nhánh `save_edits(..., reload_viewer=False)`.
- Da them regression tests trong `tests/test_stability_contracts.py` va bo sung local server registry tests.
- Ket qua verify moi: `.\.venv313\Scripts\python.exe -m pytest` => `178 passed, 24 skipped`.

Cap nhat sau batch trien khai thu hai trong ngay 2026-06-08:

- Da chuyen object edit action trong `app/actions/edit.py` tu polling `window.__3tPendingAction` moi 80 ms sang `objectActionBridge` qua QWebChannel.
- Da them `_ObjectActionBridgeProxy` vao `app/webchannel.py` de proxy WebChannel on dinh co contract ro cho rotate/delete/edit/move/dismiss/retry.
- Da bo import `QThread` thua trong `app/actions/edit.py`.
- Da them contract tests de chan viec quay lai polling JS va de xac nhan UI update dang dung `packages.updater` thay vi package update client cu.
- Ket qua verify moi: `.\.venv313\Scripts\python.exe -m pytest` => `180 passed, 24 skipped`.

Cap nhat sau batch trien khai thu ba trong ngay 2026-06-08:

- Da bo sung state API cho annotation queue: `pending_count()`, `is_flushing()` va `last_error()`.
- `has_pending_annotations()` co the nhan dien ca truong hop queue dang flush cho file hien tai, khong chi cac op con nam trong danh sach pending.
- Khi thao tac nang bi chan vi chu thich chua luu xong, canh bao nay hien ly do cu the hon: dang flush hay loi gan nhat.
- Da them regression tests cho pending/flushing state, status message khi flush dang chay va noi dung canh bao heavy-op.
- Ket qua verify moi: `.\.venv313\Scripts\python.exe -m pytest` => `183 passed, 24 skipped`.

Cap nhat sau batch trien khai thu tu trong ngay 2026-06-08:

- Da chuyen fallback doc text trong `packages/ai/chat_pdf.py` tu `fitz`/PyMuPDF sang `pypdfium2`, de AI chat khong con di qua runtime AGPL path.
- Da them tests xac nhan fallback pdfium cua AI chat va contract khong con `import fitz` trong module nay.
- Da sua comment cu trong `app/window.py` ve print path de khong con ghi nham PyMuPDF.
- Ket qua verify moi: `.\.venv313\Scripts\python.exe -m pytest` => `185 passed, 24 skipped`.

Cap nhat sau batch trien khai thu nam trong ngay 2026-06-08:

- Da bien `packages/update_client/checker.py` thanh compatibility wrapper sang `packages.updater.update_client`.
- Import cu `packages.update_client` van giu ten `UpdateInfo`, `UpdateResult`, `check_for_update`, `download_update`, nhung khong con implementation download thieu SHA/signature verification.
- Da them test xac nhan legacy checker delegate sang updater signed path.
- Ket qua verify moi: `.\.venv313\Scripts\python.exe -m pytest` => `186 passed, 24 skipped`.

## 2. Du lieu da kiem tra

### 2.1 Code va module chinh

- `main.py`: diem vao ung dung.
- `app/window.py`: lop cua so chinh, ribbon/menu, tab state, open/close document, shortcut/action wiring, license/update entry points.
- `app/pdf_viewer.py`: wrapper QWebEngineView + PDF.js + QWebChannel + local server.
- `app/local_server.py`: HTTP server noi bo phuc vu PDF.js va file PDF.
- `assets/js/pdfjs_ui_hooks.js`: hook vao PDF.js UI, cau noi page state/selection/zoom.
- `assets/js/polyfill.js`: polyfill cho WebEngine/PDF.js.
- `app/webchannel.py`: proxy QWebChannel on dinh cho cac bridge.
- `app/actions/annotate.py`: highlight/underline/strikeout/comment/note overlay + hang doi ghi PDF.
- `app/actions/edit.py`: insert text/image, select/move/delete object, draw/redact-like operations, save edit.
- `app/actions/sign.py`: ky PFX/USB token, truong chu ky, ky tay/con dau, verify.
- `app/actions/ai_actions.py`: dialog va thao tac AI.
- `packages/pdf_engine/pdfium_engine.py`: engine PDF chinh bang pikepdf/reportlab/pypdfium2.
- `packages/signing/*`: provider ky so, Windows PKCS#11, verifier, appearance.
- `packages/license_client/*`: license/trial/cache/heartbeat.
- `packages/updater/*` va `packages/update_client/*`: update client va dialog.
- `packages/ocr/engine.py`: phat hien Tesseract/tessdata, OCR page.
- `tests/*`: 26 file test, bao phu local server, signing utilities, license/update, OCR path, AI provider, PDF pipeline va regression helpers.

### 2.2 Tai lieu Markdown da doc va tong hop

Du an co 122 file `.md`; trong do khoang 63 file thuoc docs/README/changelog/ADR/checklist cua du an, con lai phan lon nam trong vendor/build/cache. Cac nhom tai lieu quan trong:

- `README.md`: mo ta Phase 0 foundation va ghi chu Windows Phase 1.
- `docs/PHASE1_WIN_STATUS.md`: Windows PDF.js render/build/installer pass; blocker con lai la test USB token that; app packaged launch duoc; chua nen tag `phase1-win-ready`.
- `docs/PHASE1_WIN_HANDOFF.md`: can test token that, install/uninstall cycle, compliance/notices/branding, UI polish.
- `docs/2026-06-04_VIEWER_ANNOTATION_STABILIZATION_CHECKLIST.md`: PR1-PR8 pass ve code; dieu kien release van can manual GUI/console check tren it nhat 3 PDF.
- `docs/UX_AUTO_FIX_CHECKLIST.md`: 21/21 UX fixes da danh dau done; log verify ghi `171 passed, 24 skipped`; rui ro con lai la chua co JS test runner/WebEngine manual.
- `docs/REMAINING_WORK_CHECKLIST.md`: refactor lam mot phan; code signing bi chan ben ngoai; Tesseract bundle reduction can DLL runtime trace; hardcoded strings audit done; Sphinx docs pass.
- `docs/HARDCODED_STRINGS.md`: 1,594 dong non-ASCII hardcoded tren 38 file. Nhieu nhat: `app/window.py`, `app/language_manager.py`, `app/actions/sign.py`, `app/actions/edit.py`.
- Nhom compliance: Phase 0 ve ky thuat da dong, nhung chua commercial-ready; can pin official PDF.js source, SBOM/CycloneDX, Qt/WebEngine Chromium notices, fixture edit khong AGPL, khong PyMuPDF/PyKCS11 trong ban commercial, real hardware smoke test, code signing.
- Nhom VPS/update: backend live tai `/home/hieupt/projects/3T_Reader/phase1-backend`; public host `reader.3tcomputer.com`, `license.3tcomputer.com`; manifest update can `sha256` va Ed25519 signature.
- ADRs: chon Pdfium + pikepdf/reportlab, PDF.js qua local HTTP server, QWebChannel bridge, pyHanko signing, multi-provider AI.

Diem lech trong tai lieu:

- Mot so setup docs van nhac `phase1-mac` trong ngu canh Windows.
- Python version khong dong nhat giua cac docs: co noi 3.11/3.12, co noi 3.12, co noi 3.11-3.13.
- Co doc compliance noi icon provenance chua pin, trong khi `assets/icons/README.md` da pin Fluent/Lucide commit.
- Mot so log PowerShell trong docs co mojibake/encoding issue, gay kho doc neu dung lam tai lieu ban giao.

### 2.3 Trang thai worktree

Truoc khi lap bao cao, worktree da co thay doi san:

- `app/actions/edit.py`: import them `QThread`, hien chua thay su dung trong file.
- `app/window.py`: them nut `Gach duoi` va `Gach ngang` vao nhom danh dau.

Bao cao nay khong revert, khong sua hai file tren.

## 3. Ban do kien truc hien tai

### 3.1 Luong khoi dong va shell ung dung

`PDFReaderApp` trong `app/window.py` la trung tam. Cua so chinh:

- Tao tab manager, ribbon/menu/status/search/sidebar.
- Quan ly state tab qua `_tabs_data` va `_global_state`.
- Mo tai lieu bang `open_document()`, tao `PDFViewerWidget`, nap file PDF, ket noi signal page/zoom/load.
- Dong tab/app qua `_close_tab()` va `closeEvent()`, co check unsaved edit va flush hang doi annotation.
- Khoi tao license/update/AI/sign/OCR action.

Nhan xet: He thong hoat dong duoc, nhung `window.py` van la "God Object". Da co class tach rieng nhu `TabManager`, `RibbonBuilder`, `MenuBuilder`, `SearchPanel`, `StatusBarBuilder`, nhung `RibbonBuilder` va `MenuBuilder` hien moi la adapter goi nguoc ve `_build_toolbar_impl()` va `_build_menubar_impl()` trong `window.py`. Dieu nay lam rui ro regression cao khi them tinh nang UI moi.

### 3.2 Viewer PDF.js + WebEngine

`app/pdf_viewer.py`:

- Dung `QWebEngineView` de render PDF.js.
- Khoi dong `LocalPDFJSServer` de phuc vu PDF.js va file PDF bang HTTP localhost.
- Inject `polyfill.js` o `DocumentCreation`.
- Inject `pdfjs_ui_hooks.js` o `DocumentReady`.
- Ket noi QWebChannel qua cac bridge on dinh trong `app/webchannel.py`.
- Poll page/zoom moi 150ms, dong thoi nhan event tu hook JS.

Diem tot:

- Cau truc bridge proxy on dinh giup giam loi stale callback khi doi viewer/tab.
- PDF.js duoc chay qua local HTTP server nen tranh nhieu loi `file://` voi ES module.
- Hook JS da co cache selection va report page state.

Rui ro:

- `_DebugPage.javaScriptConsoleMessage` in tat ca log JS ra console; nen gate bang debug flag cho ban release.
- Neu local server fail, viewer co fallback `file://`; voi PDF.js moi, `file://` co the loi module/CORS. Nen bien no thanh fallback co canh bao ro, hoac fail co huong dan restart server.

### 3.3 Local server

`app/local_server.py` phuc vu:

- Static PDF.js assets.
- `GET /pdf?p=<absolute-path>` de stream PDF.
- MIME `.js`/`.mjs`.
- Mot so normalizer cho signature appearance de tranh PDF.js ve khung widget ky so khong mong muon.

Diem tot:

- Co check canonical path, path traversal va tests security.
- Static asset co whitelist tuong doi chat.
- MIME cho PDF.js module duoc fix.

Rui ro:

- Endpoint `/pdf?p=` chap nhan duong dan PDF tuyet doi hop le tren may, mien la canonical/existing. Ve security, localhost van nen gioi han theo "allowed document registry" do app dang mo, de tranh bat ky page local nao goi localhost doc file PDF khac.
- `_normalise_pdfjs_appearance_boxes()` can thiep PDF bytes bang pikepdf cho display-only. Day la diem can test regression voi nhieu loai chu ky/field vi co the anh huong cach PDF.js hien thi signature widget.

### 3.4 Annotation

`app/actions/annotate.py`:

- Highlight/underline/strikeout/comment/note.
- Tao overlay ngay tren viewer de phan hoi nhanh.
- Dua op vao `_AnnotationOpQueue`, debounce va ghi PDF bang pikepdf.
- Flush queue khi thao tac nang hoac dong file.
- Co fallback selection tu `QWebEnginePage.selectedText()` va pdfplumber search neu PDF.js payload khong du.

Diem tot:

- UX phan hoi nhanh vi overlay xuat hien truoc.
- Hang doi ghi file giam viec rebuild lien tuc.
- Close tab/app co check pending queue.

Rui ro:

- Overlay co the hien thanh cong trong khi ghi file that bai. Can indicator "Dang luu/Da luu/Loi luu" de nguoi dung biet trang thai that.
- `flush()` tra `False` khi dang flushing, nhung khong phan biet "dang co thao tac ghi" voi "ghi that bai"; nen tach status de close/save dua thong bao chinh xac.
- Comment hien con dang dung `QInputDialog.getMultiLineText`; nen nang len note/comment panel hien dai hon.

### 3.5 Edit PDF

`app/actions/edit.py`:

- `_ensure_edit_state()` tao snapshot goc va working file trong temp.
- Insert text/image tao operation va rebuild working PDF ngay bang `get_pdf_engine().rebuild_pdf_with_ops`.
- Reload viewer sau moi operation.
- Chon/move/delete object bang area pick va JS handles.
- `save_edits()` ghi file, reset state, reload viewer.

Diem tot:

- Workflow an toan hon viec ghi thang vao file goc: co working copy va prompt khi PDF da signed.
- Engine dung pikepdf/reportlab, phu hop huong khong dung PyMuPDF cho edit thuong mai.

Rui ro:

- Edit chua that su overlay-first/deferred save. Moi insert text/image van rebuild va reload PDF, co the cham va mat context voi file lon.
- `save_edits_quiet()` docstring noi khong reload viewer, nhung implementation co goi reload. Can sua docstring hoac hanh vi.
- Object action polling `window.__3tPendingAction` moi 80ms thay vi QWebChannel typed bridge. Cach nay pragmatically chay duoc, nhung brittle hon bridge co signal/contract ro.
- Neu staging image fail, code co fallback im lang ve path goc; neu anh goc bi xoa/doi cho sau do, save co the loi.
- Thay doi moi trong worktree import `QThread` o `app/actions/edit.py`, hien chua su dung.

### 3.6 PDF engine

`packages/pdf_engine/pdfium_engine.py`:

- Dung pypdfium2 de render/thong tin document.
- Dung pikepdf/reportlab de edit overlay, watermark, split/merge/rotate/delete, create blank.
- Check password/auth bang pikepdf + pypdfium2.

Diem tot:

- Phu hop dinh huong license thuong mai hon PyMuPDF.
- Text wrapping da co do rong string qua reportlab.

Gioi han:

- Day la overlay/page operation engine, chua phai editor object-aware nhu Acrobat/Foxit. Khong nen marketing la "sua PDF nhu Word" neu chua co layout reflow, font matching, paragraph object model.

### 3.7 Sign/USB token/PFX

`app/actions/sign.py` va `packages/signing/*`:

- Ho tro PFX, USB token PKCS#11, field ky, appearence, verify.
- Signing task chay trong `QThread`, dialog modal dung `QEventLoop`.
- Windows provider scan PKCS#11 paths qua env/System32/SysWOW64/Program Files/registry/localappdata.

Diem tot:

- Kien truc pyHanko dung huong va co tests helper.
- Co phan detect token/provider va verify.

Rui ro cao:

- `app/actions/sign.py:1892` `sign_handwritten()` import `fitz` tai `app/actions/sign.py:1894`. Neu dong goi PyMuPDF vao ban commercial, no mau thuan voi checklist compliance "khong PyMuPDF trong ban thuong mai".
- `_start_token_monitor()` trong `app/window.py:2130` dang `pass`, trong khi `_check_token_presence()` co code. Neu UI/tai lieu noi co monitor token real-time thi hien chua dung.
- Real USB token smoke test van la blocker theo docs. Bo test Python khong thay the duoc test hardware.

### 3.8 OCR

`packages/ocr/engine.py`:

- Tim Tesseract qua env, bundled path, system install.
- Quan ly tessdata/language.
- OCR page va tich hop action trong app.

Diem tot:

- Test co bao phu path discovery va language.

Rui ro:

- Docs con neu Tesseract bundle reduction can runtime DLL trace. Can test installer tren may sach.
- Can nang UX de chon ngon ngu, page range, batch OCR, deskew, output searchable PDF ro rang hon.

### 3.9 AI

`packages/ai/provider.py` va `app/actions/ai_actions.py`:

- Ho tro nhieu provider: OpenAI, Anthropic, Groq, OpenRouter, HuggingFace, Ollama, Gemini/3T AI va fallback.
- API key luu qua secure config.
- UI co summarize/chat/translate/ask doc tuy action wiring can xem tiep khi polish.

Diem tot:

- Da co multi-provider, phu hop nguoi dung co API key rieng va co the chay local qua Ollama.

Rui ro:

- Can UI "AI co trich dan trang/nguon" neu muon canh tranh Acrobat/Foxit.
- Can guard privacy: hien ro file nao gui len cloud provider, tuy chon local-only, va log/audit cau hoi cho doanh nghiep.

### 3.10 License/update/VPS

`packages/license_client/*`, `app/license_dialog.py`, `packages/updater/*`, `app/update_dialog.py`:

- Co trial, offline signed token cache, grace, heartbeat.
- Update manifest co sha256 va Ed25519 signature theo docs.
- Backend VPS da co host public va endpoint language/update/license.

Diem tot:

- Co tests cho tampered cache grace va clock rollback.
- Huong signed update la dung cho san pham thuong mai.

Rui ro:

- Ton tai hai nhom updater: `packages/updater` va `packages/update_client`; can hop nhat hoac xac dinh ownership de tranh drift.
- Can test update end-to-end voi installer that, signature manifest that, rollback/retry khi download fail.

## 4. Danh sach van de uu tien

### P0 - Chan release thuong mai

1. `fitz`/PyMuPDF trong luong ky tay
   - Vi tri: `app/actions/sign.py:1892`, `app/actions/sign.py:1894`.
   - Tac dong: Mau thuan compliance neu ban commercial dong goi PyMuPDF.
   - Huong xu ly: Viet lai ky tay/con dau bang pikepdf/reportlab/Pillow hoac tach thanh optional dev-only plugin khong nam trong commercial build. Them test/static audit fail neu `import fitz` xuat hien trong code path commercial.

2. Chua co USB token hardware acceptance
   - Vi tri lien quan: `packages/signing/windows_provider.py`, `app/actions/sign.py`, docs Phase1.
   - Tac dong: Tinh nang cot loi voi thi truong Viet Nam chua duoc xac nhan tren thiet bi that.
   - Huong xu ly: Lap matrix test voi it nhat 2-3 token pho bien, driver clean machine, ky thanh cong, ky fail PIN sai, rut token giua chung, verify sau ky.

3. Compliance/release assets chua dong
   - Tac dong: Chua nen phat hanh thuong mai neu thieu SBOM, license notices Qt/WebEngine/Chromium/PDF.js, code signing, installer uninstall smoke, PDF.js provenance.
   - Huong xu ly: Dong checklist release va gan vao CI/artifact build.

### P1 - Anh huong UX va do on dinh san pham

4. Xung dot `Ctrl+Shift+S`
   - Vi tri: Save As `app/window.py:432`; AI summarize `app/window.py:678`, `app/window.py:1123`.
   - Tac dong: Nguoi dung bam shortcut co the chay action khong mong muon.
   - Huong xu ly: Giu `Ctrl+Shift+S` cho Save As; doi AI summarize sang `Ctrl+Alt+S` hoac bo shortcut, dung command palette/AI panel.

5. USB token monitor chua kich hoat
   - Vi tri: `app/window.py:2130` `_start_token_monitor()` dang trong; `app/window.py:2134` co `_check_token_presence()`.
   - Tac dong: Status token tren UI co the khong cap nhat real-time.
   - Huong xu ly: Them QTimer voi interval hop ly, debounce status change, khong scan PKCS#11 qua nang tren UI thread.

6. Local server doc PDF qua duong dan tuyet doi
   - Vi tri: `app/local_server.py:50`, `app/local_server.py:81`.
   - Tac dong: Surface localhost rong hon can thiet.
   - Huong xu ly: Khi `PDFViewerWidget` mo file, register token/id cho file do; `/pdf?id=...` chi phuc vu file da dang ky. Bo hoac chi giu `/pdf?p=` o debug mode.

7. `window.py` van qua tap trung
   - Vi tri: `app/window.py:113`, `_build_toolbar_impl()` `app/window.py:403`, `_build_menubar_impl()` `app/window.py:889`.
   - Tac dong: Them tinh nang moi de gay regression, kho test UI state.
   - Huong xu ly: Tach `ActionRegistry`, `ShortcutRegistry`, `DocumentSession`, `RibbonBuilder` that su build UI ngoai `window.py`, va dat state vao dataclass.

8. Edit rebuild/reload moi action
   - Vi tri: `app/actions/edit.py`.
   - Tac dong: File lon se cham, mat scroll/zoom/selection, trai nghiem kem hon editor thi truong.
   - Huong xu ly: Overlay-first cho text/image/object, chi rebuild khi Save/Preview/Export; luu viewport va selection khi reload bat buoc.

9. Comment UX con cu
   - Vi tri: `app/actions/annotate.py`.
   - Tac dong: `QInputDialog` khong phu hop workflow comment nhieu nguoi dung.
   - Huong xu ly: Them right comments panel, click-to-place sticky note, list/filter/search comments, jump-to-comment, export XFDF/summary.

10. Chua co E2E GUI/WebEngine automation
    - Tac dong: Python unit tests pass nhung chua dam bao JS hook, WebEngine render, overlay, click flows hoat dong tren Windows packaged app.
    - Huong xu ly: Them manual release checklist co screenshot, hoac Playwright/Qt automation neu kha thi; toi thieu smoke tren 3 PDF: text PDF, scanned PDF, signed PDF.

### P2 - No ky thuat va chat luong dai han

11. Object edit dung polling JS
    - Vi tri: `app/actions/edit.py:72`, `app/actions/edit.py:833`, `app/actions/edit.py:848`.
    - Tac dong: Kho debug va kho validate contract.
    - Huong xu ly: Them `objectActionBridge` QWebChannel co signal payload typed.

12. `save_edits_quiet()` khong khop docstring
    - Vi tri: `app/actions/edit.py:1430`.
    - Huong xu ly: Sua ten/docstring hoac bo reload trong mode quiet.

13. Hai updater package co nguy co drift
    - Vi tri: `packages/updater/*`, `packages/update_client/*`.
    - Huong xu ly: Chon mot package public, package kia deprecated hoac wrapper co test.

14. Hardcoded text/i18n con lon
    - Vi tri: theo `docs/HARDCODED_STRINGS.md`.
    - Huong xu ly: Tach string UI sang language resources, uu tien strings user-facing trong `window.py`, `sign.py`, `edit.py`.

15. Console/log encoding
    - Tac dong: Mojibake trong docs/log lam kho ban giao va audit.
    - Huong xu ly: Ep `PYTHONIOENCODING=utf-8`, chuan hoa script audit/build va docs generated output.

## 5. Doi chieu tinh nang voi ung dung thi truong

Nguon chinh thuc da tham khao:

- Adobe Acrobat features: https://www.adobe.com/acrobat/features.html
- Foxit PDF Editor features: https://www.foxit.com/PDF-editor/
- Foxit plan comparison/eSign features: https://www.foxit.com/esign-pdf/comparison.html
- Nitro PDF Standard/Pro features: https://www.gonitro.com/pdf/nitro-pro
- Nitro OCR features: https://www.gonitro.com/ocr
- PDF-XChange Editor features: https://www.pdf-xchange.com/product/pdf-xchange-editor/features-group/6/features

### 5.1 Nhom tinh nang thi truong coi la mac dinh

Adobe/Foxit/Nitro/PDF-XChange deu dua cac nhom sau vao goi chinh:

- View/print/search/comment.
- Edit text/image/link/layout truc tiep.
- Organize pages: merge/split/reorder/delete/rotate/extract/insert.
- OCR tao PDF searchable/editable; co page range, language, batch, deskew/image adjustment.
- Fill/create forms, auto form field recognition, signature field.
- eSign/digital signature, tracking, templates.
- Protect/security: password, permissions, redact, sanitize metadata.
- Convert/export: Word, Excel, PowerPoint, image, HTML/text.
- Compare two PDFs.
- AI assistant: summarize, ask/chat, rewrite, translate, citations/page references.
- Comment/collaboration: list comments, filter, status, reply, export/import annotations.

### 5.2 3T Reader dang co gi

3T Reader da co:

- Viewer PDF.js, tab, search, zoom, navigation, sidebar.
- Highlight/underline/strikeout/comment/note.
- Insert text/image, draw/rect, object select/move/delete o muc overlay/edit op.
- Page/document ops qua pdf engine: merge/split/rotate/delete/watermark/create blank.
- OCR Tesseract.
- Ky PFX/USB token va verify bang pyHanko.
- AI multi-provider.
- License/trial/update.
- Build/installer Windows.

### 5.3 Khoang cach so voi thi truong

Khoang cach lon nhat khong phai "co nut hay khong", ma la chieu sau workflow:

- Comment can panel quan ly nhu Acrobat/Foxit, khong chi dialog nhap text.
- Edit can contextual toolbar va object inspector, khong chi action ribbon.
- OCR can output/searchable-layer workflow ro rang, page range, batch, progress, quality options.
- Redaction can co "mark for redaction" -> "apply" -> "sanitize", khong chi ve hop den/de len noi dung.
- Forms can tao va chinh AcroForm, auto detect fields, export/import data.
- AI can tra loi co citations theo trang/doan, privacy mode va lich su chat.
- Signing can hien chain/trust/certificate details va status token that-time.
- Page organizer can dung thumbnail drag-drop, insert from file, duplicate/extract selected.
- Compare documents va batch operations chua ro hoac chua co.

## 6. De xuat nang cap de de dung, truc quan, hop thi truong Viet Nam

### 6.1 UX layout nen huong toi

Nen chuyen tu ribbon day nut sang bo cuc "workspace":

- Thanh tren: Open/Save/Export/Sign/OCR/AI, search, zoom, page.
- Sidebar trai: thumbnails/bookmarks/attachments/search results.
- Vung giua: PDF viewer.
- Sidebar phai: Comments/Properties/AI/Sign/OCR tuy context.
- Floating mini-toolbar khi boi den text: highlight, underline, strikeout, note, copy, ask AI.
- Floating mini-toolbar khi chon object: move, delete, opacity, color, font, layer/order, lock.
- Status bar ro: Dang luu annotation, da luu, edit mode, signed PDF warning, token connected/disconnected.

### 6.2 Tinh nang uu tien cho nguoi dung doanh nghiep Viet Nam

- USB token dashboard: nha cung cap token, serial, cert subject, han cert, trang thai driver, nut test ky.
- Mau con dau/chu ky: thu vien stamp noi bo, ten cong ty, MST, nguoi ky, ngay ky dong.
- OCR tieng Viet: chon `vie+eng`, deskew, batch OCR, tao searchable PDF, canh bao chat luong scan.
- AI noi bo/local-first: che do khong gui file ra cloud; neu dung cloud thi hien ro provider va pham vi du lieu gui.
- Trich xuat thong tin: MST, so hoa don, ngay, ben A/ben B, CCCD/CMND, so hop dong.
- Audit log: mo file, sua file, ky, verify, export, update.
- Template workflow: hop dong, hoa don, bien ban, phieu thu/chi.

### 6.3 Cai tien de tranh nguoi dung bi roi

- Moi mode phai co trang thai ro tren UI: View/Edit/Annotate/Sign/OCR.
- Khi vao Edit tren file da signed, hien canh bao ro: edit co the lam mat tinh hop le chu ky.
- Neu annotation dang pending save, hien spinner nho va chan dong app cho den khi flush xong hoac user chap nhan bo qua.
- Doi shortcut AI de khong tranh Save As.
- Them "Undo/Redo" that su cho edit/annotation, hien history ngan gon.
- Them "Recover unsaved session" neu app crash trong khi co working file.

## 7. Lo trinh trien khai de dua len san pham

### Giai doan A - On dinh release blocker (1-2 tuan)

Muc tieu: san pham chay on tren Windows beta va khong vi pham compliance ro rang.

1. Loai bo `fitz` khoi luong ky tay/con dau commercial.
2. Sua xung dot shortcut `Ctrl+Shift+S`.
3. Kich hoat token monitor hoac bo claim tren UI/docs.
4. Local server: thay `/pdf?p=absolute-path` bang allowed document registry.
5. Dong bo docs: Python version, PDF.js provenance, icon provenance, status `phase1-win-ready`.
6. Lap hardware test log cho USB token.
7. Chay installer smoke tren may sach: install, launch, open PDF, sign/OCR if available, uninstall.

Acceptance:

- `pytest` pass.
- Build installer pass.
- Manual GUI smoke pass tren 3 PDF.
- Ky USB token that pass it nhat 1 provider; neu chua, ghi ro beta limitation.
- Khong con `import fitz` trong artifact commercial.

### Giai doan B - UX core va workflow editor (2-4 tuan)

Muc tieu: nguoi dung binh thuong de tim tinh nang va thao tac it bi reload/giat.

1. Tach `ActionRegistry` va `ShortcutRegistry`.
2. Tach `DocumentSession` dataclass thay dict state trong `_tabs_data`.
3. Lam Comments panel ben phai: list, jump, filter, delete, edit note.
4. Floating selection toolbar cho mark/comment/copy/AI.
5. Overlay-first edit queue: text/image/object hien tren viewer, chi rebuild khi Save/Preview.
6. Object property inspector: font, size, color, opacity, position, page.
7. Page organizer thumbnail drag-drop va page range actions.

Acceptance:

- Open/edit/annotate/save khong mat zoom/page neu khong bat buoc.
- Comment thao tac duoc khong qua modal dialog cu.
- Shortcut map khong co collision.

### Giai doan C - Thuong mai hoa va dong goi (4-8 tuan)

Muc tieu: artifact co the ban/ban giao cho khach doanh nghiep.

1. SBOM CycloneDX cho Python deps va bundled assets.
2. Notices cho Qt/PyQt/WebEngine/Chromium/PDF.js/Tesseract.
3. Official pin PDF.js source + checksum.
4. Code signing Windows va timestamp.
5. Update manifest signed E2E; test rollback/retry.
6. Tesseract bundle slimming dua tren DLL runtime trace.
7. Crash/log collection local opt-in.
8. Security review local server, update, license cache, API key storage.

Acceptance:

- Artifact signed.
- Installer clean install/uninstall.
- Notices/SBOM di kem.
- Update tu version cu len moi thanh cong va fail-safe neu signature sai.

### Giai doan D - Tinh nang canh tranh thi truong (8+ tuan)

Muc tieu: khac biet voi PDF editor pho thong, tap trung khach Viet Nam.

1. Redaction workflow day du: mark, review, apply, sanitize hidden text/metadata.
2. Compare documents: text diff + visual diff + report.
3. Forms: fill/create AcroForm, auto detect field, export/import data.
4. Batch OCR/export/sign.
5. AI citations theo trang/doan, chat history, export summary, local-only mode.
6. Certificate trust view: chain, revocation, timestamp, policy, cert expiry warning.
7. Admin deployment: config policy, license seat, update channel, offline activation package.

## 8. Kiem thu can them

### 8.1 Automated tests

- Shortcut collision test: quet tat ca `QAction.shortcut()` trong `PDFReaderApp`.
- Commercial import audit: fail neu `fitz`/PyMuPDF xuat hien trong module build commercial.
- Local server allowed registry test: chi file registered moi duoc serve.
- Annotation flush state test: phan biet flushing/failure/success.
- Update duplication test: dam bao chi mot client public duoc dung trong app.
- Edit session recovery test: working file ton tai sau crash co the restore.

### 8.2 Manual/E2E tests

- PDF text binh thuong: open/search/highlight/underline/strikeout/comment/save/reopen.
- PDF scan: OCR one page, OCR all, search text OCR.
- PDF signed: verify, them chu ky, edit warning, reopen verify status.
- File lon 100-300 trang: scroll, zoom, search, annotate, save.
- May sach Windows: install, launch, open file, update check, uninstall.
- USB token: connected/disconnected/PIN sai/PIN dung/rut token giua chung.

## 9. Tieu chi de gan nhan phase1-win-ready

Chi nen gan nhan `phase1-win-ready` khi dat tat ca:

- Build Windows + installer pass tren may dev va may sach.
- `pytest` pass.
- Manual WebEngine smoke pass tren 3 loai PDF.
- Ky PFX va USB token that pass; neu token that chua pass thi release label phai la beta/no-token-certified.
- Khong co shortcut collision nghiem trong.
- Local server khong expose arbitrary absolute PDF path.
- Commercial artifact khong ship PyMuPDF neu policy van cam.
- SBOM/notices/PDF.js provenance/code signing co bang chung.
- Docs status/handoff/checklist dong bo cung version.

## 10. De xuat thu tu sua ngay

Thu tu thuc te de it rui ro:

1. Sua shortcut `Ctrl+Shift+S` va them test collision.
2. Them static commercial audit cho `fitz`, sau do refactor `sign_handwritten`.
3. Kich hoat token monitor nhe bang QTimer + cache status.
4. Local server allowed-doc registry.
5. Sua `save_edits_quiet()` docstring/behavior.
6. Doi object action polling sang QWebChannel bridge.
7. Lam Comments panel va annotation save status.
8. Lam Page organizer va Object inspector.
9. Dong bo docs/compliance va release checklist.

## 11. Danh gia tong the

3T Reader da vuot muc prototype: co cau truc module, co engine rieng, co license/update, co signing/OCR/AI va bo test dang tin cay cho nhieu logic nen. Diem manh lon nhat la huong di san pham Windows cho thi truong Viet Nam: USB token, offline grace, OCR/AI, local app, va kha nang tuy bien theo doanh nghiep.

Diem yeu lon nhat la do phuc tap dang don nhieu vao `app/window.py` va cac module action rat lon. Neu tiep tuc them tinh nang theo cach hien tai, toc do ban dau se nhanh nhung regression UI/action se tang. Nen dau tu som vao `DocumentSession`, `ActionRegistry`, panel phai theo context, va bridge typed cho JS/Python.

Ve thi truong, 3T Reader khong can sao chep day du Acrobat ngay lap tuc. Nen uu tien nhung workflow nguoi dung Viet Nam dung hang ngay: mo PDF nhanh, danh dau/comment de hieu, OCR tieng Viet, ky USB token on dinh, sua/chen thong tin don gian, va AI tom tat/trich xuat co trich dan. Khi cac workflow nay tron tru va co release compliance, ung dung co co hoi canh tranh tot o phan khuc doanh nghiep noi dia.
