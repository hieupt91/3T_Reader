# 3T Reader - Deep Technical Audit

## 1. Muc dich tai lieu

Tai lieu nay duoc viet de ban giao ky thuat o muc rat sau cho nguoi doc moi. Muc tieu:

- Giai thich du an hien dang co gi.
- Mo ta kien truc, luong xu ly, thu vien, module, asset, test, script, backend, cap phep, update, AI, OCR, ky so.
- Chi ra cai gi da hoan thien, cai gi dang la no ky thuat, cai gi chi la vendor/generated artifact.
- Giup ky thuat khac co the doc 1 file nay de nhanh chong nam toan canh truoc khi sua code.

Tai lieu nay duoc tong hop tu:

- Source code hien tai trong repo.
- Test code hien tai.
- Tai lieu nam trong `docs.zip`.
- Quan sat cau truc asset, vendor, generated docs va cac script build/deploy.

## 2. Tong quan du an

`3T Reader` la ung dung desktop doc va thao tac PDF, trong code hien tai nham vao Windows la chinh, co dau vet ho tro macOS va Linux o mot so lop nen. Ung dung khong chi la viewer PDF ma la mot bo cong cu tong hop gom:

- Doc PDF.
- Dieu huong, zoom, thumbnail, bookmark, search.
- Annotate: highlight, underline, strikeout, sticky note, free draw.
- Chinh sua doi tuong tren PDF: text, image, hinh chu nhat, redact, watermark, page ops.
- OCR bang Tesseract.
- AI chat, summarize, translate, semantic search.
- Ky so USB token, PFX, ky tay/stamp, batch sign.
- Export/conversion sang Word, Excel, image, text va chuyen doi tu file Office/Image/XML sang PDF.
- Cap phep phan mem va check update co xac minh chu ky.

Ve van hanh, du an gom 2 khoi lon:

- Desktop app: `main.py`, thu muc `app/`, `packages/`.
- Backend/API/VPS logic: `main_api.py`, `vps_*`, mot so script deploy/cap nhat.

## 3. Tinh trang tai lieu cu so voi code hien tai

Trong `docs.zip`, cac file markdown mo ta mot kien truc cu hon:

- Noi `PyQt5 + QWebEngine`.
- Noi `PyMuPDF` giu vai tro lon hon.
- Mo ta mot so huong dan mang tinh tong hop.

Code hien tai khac o nhieu diem quan trong:

- UI binding hien tai da chuyen sang `PySide6` thong qua lop `packages.qt_compat`.
- Engine PDF mac dinh hien tai la `pypdfium2 + pikepdf + reportlab`, con `PyMuPDF` la nhanh thay the/legacy cho mot so tac vu.
- Luong viewer hien tai dua rat nang vao `PDF.js` phuc vu render va local HTTP server.
- Nhieu contract kien truc duoc khoa bang test, dac biet quanh viewer, local server, webchannel, update, license.

Vi vay, khi ky thuat moi doc du an:

- Tin code hien tai va test hien tai truoc.
- Dung `docs.zip` nhu tai lieu lich su/bo sung, khong xem la source of truth.

## 4. Cau truc thu muc cap cao

### 4.1 Thu muc chinh

- `main.py`: entrypoint desktop app.
- `main_api.py`: FastAPI app cho backend web/license/update/admin.
- `app/`: UI desktop, viewer, actions, dialog, ribbon, sidebars, server noi bo.
- `packages/`: cac package nghiep vu va nen.
- `tests/`: test regression, security, architecture contract, engine behavior.
- `third_party/pdfjs/`: bo PDF.js duoc dong goi local.
- `assets/`: icon, js hooks, css overrides, hinh giao dien.
- `scripts/`: script audit, sign, export source, fix cache.
- `docs.zip`: tai lieu dong goi va Sphinx generated docs.
- nhieu file script goc repo cho build/deploy/thu nghiem.

### 4.2 Thu muc `app/`

La tang UI va orchestration. Nhung file quan trong nhat:

- `window.py`: cua so chinh, dieu phoi tong the.
- `pdf_viewer.py`: viewer PDF dua tren `QWebEngineView` + PDF.js.
- `local_server.py`: local HTTP server phuc vu PDF.js va PDF file.
- `webchannel.py`: dang ky cac bridge object giua Python va JavaScript.
- `sidebar.py`, `annotation_sidebar.py`, `signature_sidebar.py`: panel ben trai/phai.
- `ribbon_bar.py`, `ribbon_builder.py`, `menu_builder.py`, `status_bar_builder.py`: shell UI.
- `actions/`: toan bo action nghiep vu theo nhom.
- `language_manager.py`: i18n, language pack.
- `welcome_widget.py`: man hinh welcome khi chua mo file.
- `updater.py`, `update_dialog.py`: UI check/cap nhat.
- `ai_*_dialog.py`: dialog AI.

### 4.3 Thu muc `packages/`

Chia theo domain:

- `packages.pdf_engine`: doc/render/sua PDF.
- `packages.platform`: path, font, secure config, recent, single instance.
- `packages.license_client`: kich hoat, validate, offline token, trial, fingerprint.
- `packages.signing`: provider ky so, chia theo Windows/macOS, shared logic.
- `packages.ocr`: OCR engine.
- `packages.ai`: provider, chat, summarize, translate, semantic search.
- `packages.document_core`: converter/export runner.
- `packages.updater`: signed update client.
- `packages.update_client`: compatibility wrapper cho import path cu.
- `packages.qt_compat`: lop import PySide6 thong nhat cho UI.

## 5. Kien truc runtime desktop

### 5.1 Entry point `main.py`

Trach nhiem:

- Khoi dong app desktop.
- Xu ly mot so worker mode qua command-line:
  - `--usb-sign-worker`
  - `--export-worker`
  - probe/list PKCS11 worker
- Xu ly truong hop subprocess cua Qt WebEngine (`--type=...`) de khong di vao logic app chinh.
- Bat `faulthandler` log crash vao `app_log.txt`.
- Tao/rang buoc single-instance.
- Khoi tao `QApplication`.
- Chon font, icon, theme.
- Chay check license ban dau.
- Neu co file PDF tu command line hoac tu secondary instance gui sang thi mo len.

### 5.2 Single-instance

Code chinh: `packages.platform.single_instance`.

Hanh vi:

- Windows: dung mutex/socket localhost de giu 1 instance chinh.
- Instance thu hai khong mo app moi ma chuyen path PDF cho instance dau.
- Co test cho hanh vi nay (`tests/test_single_instance.py`).

### 5.3 Cua so chinh `app/window.py`

`PDFReaderApp` la trung tam orchestration.

Trach nhiem:

- Tao tab manager va nhieu tab tai lieu.
- Quan ly viewer hien tai.
- Khoi tao ribbon/menu/statusbar/welcome screen.
- Quan ly sidebars:
  - thumbnail
  - bookmark
  - annotation
  - signature
- Quan ly trang thai theo tung tab qua `_tabs_data`.
- Mo dong tai lieu, cleanup temp path, luu, save as, navigation, print.
- Dam bao flush queue annotation truoc cac tac vu nang.
- Dong bo trang thai page/zoom/current file len UI.
- Theo doi token/license/update va background timers.

Luu y:

- `app/tab_state.py` co dataclass-like container, nhung phan lon code van dua vao dictionary `_tabs_data`.
- Day la dau hieu co no ky thuat: typed state da co huong di, nhung migration chua xong.

## 6. Viewer PDF

### 6.1 Nen tang viewer

Viewer khong render PDF truc tiep bang Qt native. No dung:

- `QWebEngineView` de embed Chromium.
- `PDF.js` chay trong WebEngine.
- local HTTP server de phuc vu `viewer.html`, assets va file PDF.

Code chinh:

- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/webchannel.py`
- `assets/js/pdfjs_ui_hooks.js`

### 6.2 Vi sao can local HTTP server

PDF.js trong Chromium/WebEngine bi gioi han khi doc file local va asset local theo cach thuan. Local server duoc dung de:

- stream PDF qua HTTP localhost.
- stream static assets cua PDF.js.
- chen polyfill vao js/mjs khi can.
- cung cap endpoint metadata cho signature hit-test.
- kiem soat security khi truy cap file.

### 6.3 `app/local_server.py`

Day la module rat quan trong.

Trach nhiem chinh:

- Chay server `127.0.0.1`.
- Phuc vu:
  - `/pdf?p=...`
  - `/sigmeta?p=...`
  - file static ben `third_party/pdfjs`
- Kiem tra security:
  - chi chap nhan path tuyet doi
  - chi file `.pdf` cho endpoint PDF
  - chan `..`
  - path phai duoc register vao whitelist theo session
  - static file phai dung extension allowlist
- Co cache display bytes / signature probes / signature click targets.
- Co logic chuan hoa file PDF de viewer dung an toan hon.

Logic dang chu y:

- Co flatten/strip signature widget de tranh PDF.js crash.
- Co tao metadata de JS co the hit-test thong tin signature.
- Co test rieng ve security va contract:
  - `tests/test_local_server.py`
  - `tests/test_local_server_security.py`

### 6.4 `app/pdf_viewer.py`

`PDFViewerWidget` la wrapper cua `QWebEngineView`.

No lam cac viec:

- Tao page/profile cho WebEngine.
- Dang ky `QWebChannel`.
- Inject script/css:
  - `assets/js/polyfill.js` tai `DocumentCreation`
  - `pdfjs_overrides.css` tai `DocumentReady`
  - `assets/js/pdfjs_ui_hooks.js` tai `DocumentReady`
  - script theme dong tai `DocumentReady`
- Load `viewer.html` cua PDF.js thong qua local server.
- Theo doi page/zoom hien tai bang polling JS moi 150ms.
- Lay page count tu backend PDF engine, khong phu thuoc hoan toan vao PDF.js.
- Ho tro `goto_page`, zoom, selection, overlay, soft reload.

### 6.5 Soft reload

`reload_soft()` la mot trong nhung phan kho nhat cua du an.

Muc tieu:

- Khi user sua file va can cap nhat viewer, tranh hard reload toan trang vi gay nhap nhay/man hinh trang/mat context.

Cach lam:

- clone canvas hien tai thanh mot freeze overlay.
- neu co overlay object edit tam thi co the xoa/ve lai.
- fetch bytes PDF moi.
- goi `PDFViewerApplication.open(...)` trong JS.
- restore scroll/page state.
- doi event `pagerendered`, roi fade overlay.

He qua:

- UX tot hon.
- Nhung logic phuc tap, rat de regression.
- Day la ly do co nhieu test contract viewer.

### 6.6 JS hooks `assets/js/pdfjs_ui_hooks.js`

Day la file cau noi giua app va PDF.js.

No dang:

- an phan chrome khong can cua PDF.js.
- nap `qrc:///qtwebchannel/qwebchannel.js`.
- tao helper `window.__3tWithBridge`.
- doc va cache selection payload.
- theo doi page state.
- xu ly click signature widget va fallback hit-test qua `sigmeta`.
- ho tro ctrl+drag panning.
- clear overlays o cac event khoi tao tai lieu/trang.

Test regression dang khoa chat nhung ky vong nay.

### 6.7 WebChannel `app/webchannel.py`

Thiet ke o day kha quan trong:

- Khong thuong xuyen tao `new QWebChannel` rieng cho tung tool.
- Dung shared/stable proxy objects.

Cac bridge object duoc duy tri:

- `pageStateBridge`
- `noteToolsBridge`
- `areaPickBridge`
- `sigPickBridge`
- `sigPreviewBridge`
- `signatureInfoBridge`
- `inlineTextBridge`
- `inlineImageBridge`
- `objectActionBridge`
- `editExistingTextBridge`

`register_webchannel_object()` thay target Python dang sau stable proxy object. Day la cach giu JS on dinh trong khi tool mode thay doi.

## 7. Chuc nang annotate va edit

### 7.1 Annotate

Code chinh: `app/actions/annotate.py`.

Chuc nang:

- highlight
- underline
- strikeout
- sticky note
- free draw lien ket voi luong khac

Kien truc:

- Dung `_AnnotationOpQueue` de debounce va auto-save.
- Truoc cac tac vu lon nhu rotate/delete/merge/close tab se flush queue.
- Selection duoc doc tu JS payload `__3tReadSelectionPayload`.
- Viewer co overlay tam, sau do moi ghi xuong PDF.

Y nghia:

- UX nhanh hon.
- Giam tan suat ghi file.
- Tang do phuc tap vi co queue, pending op, flush point.

### 7.2 Edit PDF

Code chinh: `app/actions/edit.py`.

Day la mot file rat lon, gom:

- insert text
- insert image
- draw rectangle
- redact
- chon doi tuong da them de move/resize/rotate/delete/edit
- existing text edit
- area pick
- overlay object

Kien truc:

- Duy tri danh sach ops (`text`, `image`, `rect`, `redact`, ...)
- live preview qua `viewer.update_ops()`
- save se dung PDF engine backend de sinh file moi
- sau save:
  - `viewer.reload_soft()` neu phu hop
  - neu khong thi `viewer.load_pdf()` / hard reload

Luu y quan trong:

- "edit existing text" khong phai sua text goc trong content stream mot cach semantically exact.
- No ve ban chat la redact/noi de che text cu roi chen text moi.
- Nguoi tiep quan du an can hieu ro dieu nay de tranh ky vong sai.

### 7.3 Inline editors

Code:

- `app/pdf_inline_editor.py`
- `assets/js/inline_text_bridge.js`
- `assets/js/inline_image_bridge.js`

Chuc nang:

- Hien overlay text/image tam thoi ngay tren viewer.
- Co drag/resize/rotate/confirm/cancel.
- Dung bridge de dong bo state giua JS va Python.

### 7.4 Save pipeline

Code:

- `app/actions/_pdf_save.py`

Logic quan trong:

- `release_viewer_file_lock()` load `about:blank` vao WebEngine truoc khi thay file.
- Ghi ra temp file stage.
- `os.replace` co retry.
- Phan biet soft reload va hard reload.

Ly do:

- WebEngine/Chromium thuong giu file handle.
- Neu khong nha lock hop ly, save tren Windows rat de loi.

## 8. Sidebar va UI shell

### 8.1 Sidebar

Code:

- `app/sidebar.py`
- `app/annotation_sidebar.py`
- `app/signature_sidebar.py`

`sidebar.py` gom:

- thumbnail loader background
- lazy load thumbnail dang visible
- cache signature/doc state
- context menu thao tac trang

### 8.2 Ribbon

Code:

- `app/ribbon_bar.py`
- `app/ribbon_builder.py`

Hien trang:

- co thanh ribbon kieu Office.
- `RibbonBuilder` hien van la adapter, phan compose chi tiet van nam nhieu trong `PDFReaderApp._build_toolbar_impl`.
- Tinh nang nay da chay, nhung ve mat clean architecture thi chua tach het.

### 8.3 Menu / status / welcome

- `app/menu_builder.py`: adapter goi `window._build_menubar_impl()`.
- `app/status_bar_builder.py`: status bar don gian.
- `app/welcome_widget.py`: man hinh welcome, recent files, CTA, cards, "what's new".

Nhan xet:

- Nhieu file shell UI dang o trang thai "refactor dang do". Da co file adapter, nhung implementation lon van o `window.py`.

## 9. PDF engine layer

### 9.1 Tong quan

Code: `packages/pdf_engine/`.

Thanh phan:

- `base.py`: interface/abstraction `PdfDocument`, `PdfEngine`, `RenderedPage`.
- `pdfium_engine.py`: engine mac dinh.
- `pymupdf_engine.py`: nhanh legacy/alternate.
- `__init__.py`: chon engine mac dinh, co env override.

### 9.2 Engine mac dinh: Pdfium + PikePDF + ReportLab

`PdfiumEngine` hien la huong chinh.

Su dung:

- `pypdfium2`: open/render/page count/text page muc co ban.
- `pikepdf`: thao tac cau truc PDF.
- `reportlab`: tao overlay text/graphics.

No lam:

- render page
- merge/split/delete/rotate
- watermark
- page ops
- overlay text/image/rect
- rebuild output

Diem dang chu y:

- co xu ly font path de support tieng Viet.
- semantics rotation duoc dao/doi cho hop voi preview browser/CSS.

### 9.3 Nhanh PyMuPDF

`packages/pdf_engine/pymupdf_engine.py`

Vai tro:

- fallback/legacy path
- mot so thao tac redact/text/image co cach thuc rieng

Nhan xet:

- Codebase khong con "fitz-first". Test cung co xu huong khoa khong de mot so path dung `fitz` tung tung.

## 10. OCR

Code: `packages/ocr/engine.py`, `app/actions/ocr.py`, `app/ocr_dialog.py`

Kha nang:

- tim Tesseract executable va `tessdata`
- co the tim tu env, bundled path, system path
- OCR page hoac ca document
- su dung `pytesseract`
- ket hop `pypdfium2` de render page/image neu can

Tinh chat:

- OCR la tinh nang co tich hop that, khong phai placeholder.
- Co test `tests/test_ocr_engine.py`.

## 11. AI subsystem

### 11.1 Tong quan

Code: `packages/ai/`, `app/ai_*`

Tinh nang:

- chat voi PDF
- summarize tai lieu
- dich
- semantic search
- settings/dialog task runner

### 11.2 AI provider

Code: `packages/ai/provider.py`

Ho tro nhieu provider:

- Anthropic/Claude
- OpenAI
- Groq
- OpenRouter
- Gemini
- HuggingFace
- Ollama

Hanh vi:

- thu provider theo config
- phan biet auth error va quota error
- key auth loi co the bi clear
- quota key thi khong xoa vo toi va

### 11.3 Chat PDF

Code: `packages/ai/chat_pdf.py`, `app/ai_chat_dialog.py`

Pipeline:

- trich text PDF bang `pdfplumber`
- fallback `pypdfium2`
- fallback OCR cache neu can
- wrap noi dung PDF thanh untrusted content
- luu lich su hoi dap trong cache dir

Dialog chat:

- non-modal
- co "always on top"
- close thi hide, khong huy lich su ngay
- dung background task wrapper (`app/ai_task_runner.py`)

### 11.4 Summarize

Code:

- `packages/ai/summarize.py`
- `app/ai_summarize_dialog.py`

Kha nang:

- summarize text
- summarize PDF toi da mot so trang
- co mode contract extraction

Van de dang thay:

- file source `packages/ai/summarize.py` co dau hieu mojibake/encoding loi trong string tieng Viet.
- Chuc nang van ton tai, nhung day la no ky thuat can sua.

### 11.5 Translate

Code: `packages/ai/translate.py`

Co:

- heuristic language detection
- Google Translate fallback
- AI translate
- offline dictionary support

### 11.6 Semantic search

Code:

- `packages/ai/semantic_search.py`
- `app/ai_search_dialog.py`

Pipeline:

- cat chunk text
- goi OpenAI embeddings `text-embedding-3-small`
- luu `json + npy` cache index
- cosine similarity bang `numpy`

Han che:

- hien tai hard-code OpenAI cho embeddings
- can `OPENAI_API_KEY`
- khong su dung da-provider nhu chat/summarize

Day la tinh nang da co, nhung chua "enterprise-grade abstraction".

## 12. Ky so va bao mat tai lieu

### 12.1 Tong quan

Code:

- `app/actions/sign.py`
- `packages/signing/`
- mot so dialog/sidebar/sign UI files

Kha nang:

- USB token signing
- PFX signing
- hand signature / stamp image
- batch signing
- signature info / verify-related UI

### 12.2 Kien truc ky so

UI:

- Chon vi tri ky tren viewer.
- Preview tem/chu ky ngay tren PDF.js.
- Confirm roi moi ky that.

Backend:

- USB sign tren Windows co subprocess worker de tranh van de teardown trong Qt/thread.
- Provider duoc tach theo OS.

### 12.3 Windows signing provider

Code: `packages/signing/windows_provider.py`

Logic lon:

- env override
- scan registry uninstall keys
- scan vendor directories
- generic DLL scanning
- bitness check
- subprocess probing

Nhan xet:

- Day la mot khoi code thuc chien de "tim thay driver/dll PKCS11 trong doi thuc", khong phai abstraction dep ma vo dung.
- Rat gan voi nhu cau thuc te USB token tai Windows.

### 12.4 Shared signing helpers

Code: `packages/signing/shared.py`

Co:

- helper doc certificate detail
- tao stamp style
- atomic replace file da ky
- logic ho tro shape/noi dung stamp

## 13. License, trial, update

### 13.1 License client

Code:

- `packages/license_client/vps_client.py`
- `packages/license_client/token_verifier.py`
- `packages/license_client/models.py`
- `packages/license_client/fingerprint.py`
- `packages/license_client/credential_manager.py`
- `packages/license_client/keychain.py`
- `packages/license_client/trial.py`

Pipeline:

- client kich hoat/validate/heartbeat/deactivate voi VPS.
- uu tien verify offline token Ed25519 neu co.
- neu token offline hop le van co the co background revalidation.
- co grace period.

### 13.2 Fingerprint thiet bi

`packages/license_client/fingerprint.py`

Logic:

- Windows uu tien `MachineGuid`.
- neu khong co thi fallback MAC + hostname + platform + machine.
- hash SHA-256 roi cat 32 ky tu.

### 13.3 Credential storage

Windows:

- uu tien `keyring`
- fallback DPAPI encrypted payload file trong `%APPDATA%`

macOS:

- su dung `security` CLI / Keychain

Trial:

- `packages/license_client/trial.py`
- 30 ngay
- luu `first_launch`, `last_seen_at`
- Windows dung credential manager + file fallback
- macOS dung Keychain

### 13.4 Update client

Code:

- `packages/updater/update_client.py`
- `packages/update_client/checker.py`
- `packages/update_client/manifest.py`

Hanh vi:

- goi `/api/v1/update/check`
- nhan manifest update
- verify chu ky manifest bang Ed25519
- verify SHA-256 cua file update
- moi cho download/cai dat tiep

Y nghia:

- update subsystem co quan tam den trust chain, khong chi la "goi URL va tai file".

## 14. Platform layer

### 14.1 `packages/platform/paths.py`

Tra ve app data dir, cache dir, log dir. Duoc nhieu subsystem dung.

### 14.2 `packages/platform/fonts.py`

Tim font system phu hop:

- Windows: `arial`, `segoeui`, `tahoma`, `times`
- bold variants
- macOS/Linux co candidate list rieng
- co helper `get_vietnamese_font_path()` vi PDF text overlay can font co ho tro tieng Viet.

### 14.3 `packages/platform/secure_config.py`

Dung machine-derived Fernet key de ma hoa cac gia tri nhay cam:

- OpenAI API key
- Anthropic API key
- va cac token lien quan

### 14.4 `packages/platform/recent.py`

Quan ly danh sach recent files. Duoc `welcome_widget.py` su dung.

## 15. Document conversion va export

### 15.1 Chuyen doi file khac sang PDF

Code: `app/actions/document_converter.py`

Kha nang:

- image -> PDF
- Office -> PDF qua LibreOffice module
- XML -> PDF hoac iTaxViewer path
- co the tai module bo sung tu server neu thieu

### 15.2 Export

Code:

- `app/actions/export.py`
- `packages/document_core/export_runner.py`
- `packages/document_core/converter.py`

Ho tro:

- PDF -> DOCX
- PDF -> XLSX
- PDF -> image
- PDF -> text

Kien truc:

- uu tien subprocess cho export de isolate crash
- frozen build co the co nhanh in-process tuy truong hop

`converter.py` co nhieu mode:

- `pdf2docx`
- `pdfplumber`
- page-image-based layout
- table/word extraction sang Excel

## 16. Backend/API/VPS side

### 16.1 `main_api.py`

Day la FastAPI app phia server.

Co nhieu endpoint/chuc nang:

- landing/support/privacy/terms
- admin/staff auth
- order management
- license activation/validation/heartbeat/deactivation
- update manifest endpoints
- release upload/config/admin assets/dashboard/devices/pricing

Nhan xet:

- Backend dang co logic that su, khong chi la demo.
- Nhung code co ve gom nhieu vai tro trong mot file.
- De maintain lau dai, can tach bounded context ro hon.

### 16.2 `vps_*`

Nhung file goc:

- `vps_license_service.py`
- `vps_order_service.py`
- `vps_models.py`
- `vps_schemas.py`
- `vps_server_temp.py`

Y nghia:

- repo nay khong chi dong vai tro desktop client.
- No dang giu mot phan logic backend/infra/deploy cho he sinh thai Reader.

## 17. Da ngon ngu (i18n)

Code: `app/language_manager.py`

Kha nang:

- chon language code qua `QSettings`
- built-in translation dictionary cho nhieu ngong ngu
- download language pack json tu VPS/CDN URLs
- luu local language pack
- validate payload language pack

Nhan xet quan trong:

- file nay cung co dau hieu mojibake o nhieu string non-ASCII.
- he thong i18n da ton tai va co logic hoan chinh.
- nhung chat luong encoding/nguon string can duoc lam sach.

## 18. Thu vien va dependency

### 18.1 Theo `pyproject.toml`

Dependencies chinh:

- `PySide6==6.11.0`
- `pyqtdarktheme==0.1.7`
- `pypdfium2==5.7.0`
- `pikepdf==10.5.1`
- `reportlab==4.4.5`
- `pyHanko==0.34.1`
- `python-pkcs11==0.9.4`
- `cryptography==46.0.7`
- `Pillow==12.2.0`
- `requests==2.33.1`
- `pytesseract>=0.3.13`
- `pdf2docx>=0.5.8`
- `pdfplumber>=0.11.0`
- `openpyxl>=3.1.0`
- `numpy>=1.24.0`

Optional deps:

- `anthropic`
- `openai`
- `PyMuPDF`
- `PyKCS11`
- `pyinstaller`
- `sphinx`

### 18.2 Theo `requirements.txt`

Co them/khac nho:

- `pyttsx3==2.90`
- `pywin32==306 ; sys_platform == 'win32'`

Y nghia:

- `pyproject.toml` la source of truth gan hon.
- `requirements.txt` la snapshot thuc thi/co the phu vu mot workflow cu.

## 19. Asset va vendor

### 19.1 `third_party/pdfjs`

Day la bo vendor runtime lon.

Quan sat:

- 168 file `.bcmap`
- 113 file `.ftl`
- 77 file `.svg`
- 5 file `.mjs`
- 3 file `.wasm`
- them `.ttf`, `.pfb`, `.css`, `.html`, `.js`, `.json`, `.gif`

Vai tro:

- viewer core
- localization
- font/cmap support
- rendering components phu tro

Nguyen tac:

- khong nen sua vendor nay tuy tien neu khong biet ro patch point.
- app da uu tien patch qua local server injection, CSS override, JS hook, bridge.

### 19.2 `assets/`

Chu yeu gom:

- SVG icon UI
- PNG icon/image
- JS bridge/hook
- CSS override
- icon app (`.ico`, `.icns`)

### 19.3 `docs.zip`

Khong phai file vo nghia.

Ben trong co:

- 4 file markdown tong hop
- Sphinx source docs
- Sphinx generated HTML
- generated `_modules/...` HTML cho source packages

Nen xem nhu:

- tai lieu ban giao cu
- generated docs package-level

Khong nen xem no la source code runtime.

## 20. Test suite va design contracts

Day la mot diem rat quan trong cua du an.

Nhieu test khong chi test output ma con khoa kien truc.

Da doc cac file test quan trong:

- `tests/test_viewer_annotation_regressions.py`
- `tests/test_stability_contracts.py`
- `tests/test_pdf_engine.py`
- `tests/test_pdf_pipeline.py`
- `tests/test_ai_provider.py`
- `tests/test_license_client.py`
- `tests/test_update_client.py`
- `tests/test_local_server.py`
- `tests/test_local_server_security.py`
- `tests/test_single_instance.py`
- `tests/test_ocr_engine.py`
- `tests/test_ai_chat_pdf.py`
- `tests/test_language_manager.py`

Nhung dieu test dang khoa:

- QWebChannel phai song theo model shared bridge.
- inline tool scripts khong duoc tao channel rieng mot cach vo ky luat.
- selection payload va event ten nao phai ton tai.
- local server security contracts.
- update client phai di qua signed manifest path.
- mot so path khong duoc quay lai kieu cu.
- print preview/viewer contracts.

Neu sua code ma bo qua test contracts, rat de "fix 1 cho, vo 3 cho".

## 21. Script, build, deploy, release

### 21.1 Scripts trong `scripts/`

- `scripts/sync_from_mac.sh`
- `scripts/sign_windows.py`
- `scripts/fix_vps_reader_cache.py`
- `scripts/export_source_code_for_copyright.py`
- `scripts/audit_tesseract_bundle.py`
- `scripts/audit_hardcoded_strings.py`

### 21.2 File build/deploy o root

Co nhieu script van hanh:

- `build_mac.sh`
- `build_secure.py`
- `deploy_final.py`
- `deploy_test.py`
- `direct_deploy.py`
- `direct_deploy2.py`
- `sftp_deploy.py`
- `update_vps_config.py`
- `installer_script.iss`
- `3T_Reader.spec`

### 21.3 Y nghia

Repo nay khong phai source app "sach dep toi gian".

No dang la working repository gom:

- app runtime
- backend runtime
- build script
- deploy script
- thu nghiem/utility script
- test artifact

Nguoi tiep quan nen phan biet:

- source production
- script operations
- scratch/test files

## 22. File test artifact, generated artifact, binary blob

Repo co nhieu file:

- `.pdf` thu nghiem
- `.png` screenshot/output
- `.txt` test nho
- logs (`app_log.txt`, `import.log`, ...)
- `docs.zip`

Chung co the co gia tri:

- tai hien bug
- fixture thu cong
- minh hoa render/font/redact

Nhung khong phai moi file deu la "source can maintain".

## 23. Tinh nang da lam den muc nao

### 23.1 Da co that va da di vao code thuc chien

- Viewer PDF.js embed trong WebEngine.
- Local HTTP server phuc vu PDF va asset.
- Multi-tab desktop app.
- Thumbnail/bookmark/annotation sidebar.
- Annotate co queue save.
- Edit text/image/rect/redact theo model overlay + backend rewrite.
- Save pipeline co file-lock workaround.
- OCR.
- AI chat/summarize/translate/semantic search.
- License activate/validate/trial/offline token.
- Signed update check/download verify.
- USB token sign, PFX sign, hand sign/stamp, batch sign.
- Export/conversion.
- Recent files, welcome screen, ribbon UI.
- I18n built-in + downloaded language pack.

### 23.2 Da co nhung chua "sach kien truc"

- `window.py` van om qua nhieu vai tro.
- `edit.py` va `sign.py` rat lon, maintenance cost cao.
- Adapter files (`menu_builder.py`, `ribbon_builder.py`) da co, nhung implementation van nam o class lon.
- tab state typed migration chua hoan tat.

### 23.3 Dang co no ky thuat / rui ro

- Mojibake/encoding loi trong mot so source string (`language_manager.py`, `summarize.py`, mot so UI file).
- Semantic search hard-code OpenAI embeddings.
- Backend `main_api.py` co nhieu concern trong cung mot file.
- Repo co nhieu script hoc/thu nghiem/ops song song, de gay nham file nao con su dung file nao da cu.
- vendor/generated artifact song chung voi source, can ky luat khi diff/review.

## 24. Nhung diem ky thuat dac biet can nho

1. Viewer khong phai widget PDF native. Moi logic viewer can nghi den:
   - PDF.js
   - local server
   - webchannel
   - JS hooks
   - soft reload

2. Save tren Windows bi anh huong boi file lock cua WebEngine. Khong duoc "don gian os.replace" ma bo qua release lock path.

3. Edit existing text khong phai text-object semantic edit. No gan voi redact + overlay text moi.

4. Kien truc bridge JS/Python da duoc test khoa. Dung pha cach tu y bang nhieu `QWebChannel` rieng.

5. Update va license deu co trust chain Ed25519. Dung don gian hoa mot cach vo tinh bo verify.

6. Signing Windows la vung code thuc dung cho USB token. Dung refactor dep ma lam mat compatibility voi driver/dll thuc te.

## 25. De xuat cach tiep quan cho ky thuat moi

Thu tu doc de vao du an nhanh:

1. Doc file nay.
2. Doc:
   - `main.py`
   - `app/window.py`
   - `app/pdf_viewer.py`
   - `app/local_server.py`
   - `app/webchannel.py`
3. Doc cac action lon:
   - `app/actions/edit.py`
   - `app/actions/annotate.py`
   - `app/actions/sign.py`
   - `app/actions/_pdf_save.py`
4. Doc:
   - `packages/pdf_engine/pdfium_engine.py`
   - `packages/license_client/vps_client.py`
   - `packages/updater/update_client.py`
   - `packages/signing/windows_provider.py`
5. Doc test contracts:
   - `tests/test_stability_contracts.py`
   - `tests/test_viewer_annotation_regressions.py`
   - `tests/test_local_server_security.py`

Neu sua:

- sua viewer: doc ca JS hook + server + test.
- sua save/edit: doc `_pdf_save.py` + engine + viewer reload.
- sua license/update: doc verifier + tests.
- sua AI: doc provider + dialogs + cache behavior.

## 26. Danh gia tong ket

Day la mot codebase da co san pham that, co do phuc tap that, va da giai quyet nhieu bai toan thuc chien:

- embed PDF.js trong desktop app
- thao tac PDF tren Windows
- OCR/AI
- ky so USB token
- cap phep/update co verify

No khong phai codebase "gon dep sach se". No la codebase dang song, co nhieu patch thuc dung, co adapter dang tach dan, co vendor/runtime asset lon, co generated docs, co script ops, co no ky thuat ro rang.

Neu ky thuat moi tiep quan voi ky vong "refactor nhanh cho dep" thi de gay vo he thong. Cach dung hon la:

- ton trong test contract,
- hieu cac workaround da ton tai vi ly do thuc te,
- refactor tung lop nho,
- tach state/module dan dan,
- va giu nguyen trust chain cua signing/update/license.

## 27. Phu luc nhanh: cac file chinh can biet

Desktop runtime:

- `main.py`
- `app/window.py`
- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/webchannel.py`

Actions:

- `app/actions/edit.py`
- `app/actions/annotate.py`
- `app/actions/sign.py`
- `app/actions/export.py`
- `app/actions/document_converter.py`
- `app/actions/_pdf_save.py`

Core packages:

- `packages/pdf_engine/pdfium_engine.py`
- `packages/pdf_engine/pymupdf_engine.py`
- `packages/license_client/vps_client.py`
- `packages/signing/windows_provider.py`
- `packages/updater/update_client.py`
- `packages/ocr/engine.py`
- `packages/ai/provider.py`
- `packages/ai/chat_pdf.py`

Contracts/tests:

- `tests/test_stability_contracts.py`
- `tests/test_viewer_annotation_regressions.py`
- `tests/test_local_server.py`
- `tests/test_local_server_security.py`
- `tests/test_pdf_engine.py`

Van hanh/build:

- `main_api.py`
- `3T_Reader.spec`
- `installer_script.iss`
- `build_secure.py`
- `deploy_final.py`
- `direct_deploy2.py`
- `scripts/*`

