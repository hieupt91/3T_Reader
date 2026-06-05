# 3T Reader — Codebase Improvement Checklist

> Checklist cải thiện chi tiết cho dự án 3T Reader Phase 1 Windows.
> Mỗi mục có: file liên quan, mô tả vấn đề, cách sửa, mức ưu tiên.
>
> **Ưu tiên:** `P0` = blocker, `P1` = quan trọng, `P2` = nên làm, `P3` = nice-to-have

---

## 1. TÁCH GOD OBJECT — `window.py` (101KB)

`app/window.py` hiện tại là God Object chứa toàn bộ UI setup, event handling, state management.

### 1.1 Tách RibbonBuilder ra widget riêng

- [ ] **P1** — Tạo `app/ribbon_builder.py`
  - **Vấn đề:** `_build_toolbar()` trong `window.py:577-860` dài ~280 dòng, tạo toàn bộ ribbon tabs + actions
  - **Cách sửa:** Tạo class `RibbonBuilder(window)` nhận `window` là parent, trả về `RibbonBar` đã build xong. Move toàn bộ `_build_toolbar()` logic vào đây
  - **File ảnh hưởng:** `app/window.py`, `app/ribbon_bar.py`

### 1.2 Tách TabManager ra widget riêng

- [ ] **P1** — Tạo `app/tab_manager.py`
  - **Vấn đề:** Tab management logic (`_build_tab_host`, `open_document`, `_close_tab`, `_show_tab_context_menu`, `_on_tab_changed`) nằm rải rác trong `window.py:298-448`
  - **Cách sửa:** Tạo class `TabManager(QTabWidget)` encapsulate toàn bộ tab lifecycle
  - **File ảnh hưởng:** `app/window.py`

### 1.3 Tách SearchPanel ra widget riêng

- [ ] **P2** — Tạo `app/search_panel.py`
  - **Vấn đề:** `_build_search_panel()`, `show_search_panel()`, `hide_search_panel()`, `_search_from_panel()`, `_reposition_search_panel()` trong `window.py:483-571`
  - **Cách sửa:** Tạo class `SearchPanel(QFrame)` tự quản lý lifecycle
  - **File ảnh hưởng:** `app/window.py`

### 1.4 Tách StatusBarBuilder ra module riêng

- [ ] **P2** — Tạo `app/status_bar_builder.py`
  - **Vấn đề:** `_build_statusbar()` trong `window.py` chứa logic tạo status bar + language button + update check
  - **Cách sửa:** Extract thành function hoặc class riêng

### 1.5 Thay thế `_global_state` dict bằng dataclass

- [ ] **P1** — Tạo `app/tab_state.py`
  - **Vấn đề:** `window.py:238-244` dùng dict `_global_state` với keys `"source_path"`, `"display_path"`, `"web_view"`, `"search_query"`, `"temp_path"` — dễ gõ sai key, không có type safety
  - **Cách sửa:**
    ```python
    @dataclass
    class TabState:
        source_path: str | None = None
        display_path: str | None = None
        web_view: QWebEngineView | None = None
        search_query: str = ""
        temp_path: str | None = None
    ```
  - **File ảnh hưởng:** `app/window.py`, tất cả files dùng `window._state_or_global()`

### 1.6 Tách MenuBar builder

- [ ] **P2** — Move `_build_menubar()` ra module riêng
  - **Vấn đề:** Menu bar construction nằm trong window.py, trùng lặp chức năng với ribbon
  - **Cách sửa:** Tạo `app/menu_builder.py`

### 1.7 Tách UpdateCheckWorker

- [ ] **P3** — Move `_UpdateCheckWorker` class (`window.py:187-216`) ra `app/updater.py` (đã tồn tại)
  - **Vấn đề:** Class này đã có file riêng `app/updater.py` nhưng lại nằm trong window.py

---

## 2. TÁCH JS INLINE RA FILE RIÊNG

Nhiều file Python nhúng JavaScript dài, khó maintain.

### 2.1 PDF.js UI hooks

- [x] **P1** — Tạo `assets/js/pdfjs_ui_hooks.js`
  - **Vấn đề:** `pdf_viewer.py:68-200+` chứa `_PDFJS_UI_AND_HOOKS_JS` — JS dài ẩn toolbar, hook find state, inject CSS
  - **Cách sửa:** Move ra file `.js`, serve qua `local_server.py` hoặc load từ file

### 2.2 Area pick script

- [ ] **P1** — Tạo `assets/js/area_pick.js`
  - **Vấn đề:** `edit.py:34-200+` chứa `AREA_PICK_SCRIPT` — JS dài xử lý drag-to-select area trên PDF
  - **Cách sửa:** Tách ra file riêng, inject qua `runJavaScript`

### 2.3 Inline text/image bridge scripts

- [ ] **P2** — Tạo `assets/js/inline_text_bridge.js`, `assets/js/inline_image_bridge.js`
  - **Vấn đề:** `pdf_inline_editor.py` chứa nhiều JS inline cho text/image overlay
  - **Cách sửa:** Tách từng script ra file riêng

### 2.4 CSS strings

- [ ] **P2** — Tạo `assets/css/pdfjs_overrides.css`
  - **Vấn đề:** `PDFJS_HIDE_TOOLBAR_CSS` trong `window.py:87-103` và `pdf_viewer.py:68-80` — CSS inline trùng lặp
  - **Cách sửa:** File CSS riêng, inject 1 lần

### 2.5 Runtime polyfill

- [x] **P2** — Gộp `_PDFJS_RUNTIME_POLYFILL` trong `local_server.py:19-59` và `_MAP_POLYFILL_JS` trong `pdf_viewer.py:26-64`
  - **Vấn đề:** Cùng polyfill `Map.getOrInsert` + `Promise.withResolvers` xuất hiện 2 lần
  - **Cách sửa:** 1 file `assets/js/polyfill.js`, cả 2 nơi cùng load

---

## 3. CONSTANTS & THEMING

### 3.1 Icon color constants

- [x] **P1** — Tạo `styles/icon_colors.py`
  - **Vấn đề:** `window.py:107-184` chứa 2 dict `_ICON_COLORS` và `_ICON_COLORS_LIGHT` với ~30 entries mỗi cái — hardcode hex colors
  - **Cách sửa:**
    ```python
    # styles/icon_colors.py
    ICON_COLORS_DARK = { ... }
    ICON_COLORS_LIGHT = { ... }
    def get_icon_color(svg_file: str) -> str:
        return (ICON_COLORS_DARK if is_dark() else ICON_COLORS_LIGHT).get(svg_file, DEFAULT_COLOR)
    ```

### 3.2 StyleSheet constants

- [ ] **P2** — Tạo `styles/stylesheet.py`
  - **Vấn đề:** Inline stylesheet strings rải rác trong `window.py:652-673` (page_spin, zoom_spin), `ribbon_bar.py:22-60`
  - **Cách sửa:** Centralize tất cả stylesheet vào 1 module, dùng template string

### 3.3 Hardcoded strings

- [ ] **P2** — Audit hardcoded Vietnamese strings
  - **Vấn đề:** Nhiều string tiếng Việt hardcode trong code (VD: `"Tệp"`, `"Chú thích"`, `"Trang"`) thay vì dùng i18n system
  - **Cách sửa:** Đưa tất cả vào `language_manager` keys
  - **Files:** `window.py`, `ribbon_bar.py`, `sidebar.py`, tất cả dialog files

---

## 4. UNIT TESTS

### 4.1 PDF Engine tests

- [x] **P1** — Tạo `tests/test_pdf_engine.py`
  - **Vấn đề:** Không có unit test cho `PdfiumEngine` — watermark, merge, split, rotate, rebuild_with_ops
  - **Cần test:**
    - `create_blank_pdf` tạo file hợp lệ
    - `watermark_pdf` thêm watermark đúng vị trí
    - `delete_pages` xóa đúng trang
    - `rotate_pages` xoay đúng góc
    - `merge_pdfs` ghép đúng thứ tự
    - `split_pdf` tách đúng range
    - `rebuild_pdf_with_ops` overlay text/image đúng

### 4.2 Atomic save tests

- [x] **P1** — Tạo `tests/test_pdf_save_helpers.py` (mở rộng)
  - **Vấn đề:** `_pdf_save.py` có logic quan trọng (atomic copy, staged path, retry replace) nhưng test chưa đủ
  - **Cần test:**
    - `make_staged_pdf_path` tạo path đúng thư mục
    - `replace_file_with_retry` retry đúng số lần
    - `atomic_copy_file` copy đúng nội dung
    - `release_viewer_file_lock` không crash khi viewer None

### 4.3 Annotation operation queue tests

- [ ] **P1** — Tạo `tests/test_annotation_queue.py`
  - **Vấn đề:** `_AnnotationOpQueue` trong `annotate.py:60-100` có logic enqueue/flush phức tạp, chưa có test
  - **Cần test:**
    - enqueue + flush đúng thứ tự
    - flush với target_path filter
    - has_pending đúng state
    - concurrent flush không double-run

### 4.4 AI provider tests

- [x] **P2** — Tạo `tests/test_ai_provider.py` (mở rộng)
  - **Vấn đề:** `provider.py` có logic fallback qua 7 providers, auth error detection, quota error detection
  - **Cần test:**
    - `_is_auth_error_text` nhận đúng các loại auth error
    - `_is_quota_error_text` nhận đúng quota error
    - `_normalize_provider_name` alias đúng
    - `_friendly_error` format đúng
    - Mock API calls để test fallback chain

### 4.5 Local server security tests

- [x] **P1** — Tạo `tests/test_local_server_security.py`
  - **Vấn đề:** `local_server.py` serve files qua HTTP, cần verify path traversal protection
  - **Cần test:**
    - `GET /pdf?p=../etc/passwd` bị reject
    - `GET /pdf?p=C:\Windows\System32\config\SAM` bị reject
    - `GET /../../../etc/passwd` bị reject
    - Chỉ accept `.pdf` extension
    - Chỉ accept absolute paths

### 4.6 Single instance tests

- [x] **P2** — Tạo `tests/test_single_instance.py`
  - **Vấn đề:** `single_instance.py` dùng kernel32 mutex trên Windows, fcntl trên POSIX — cần test cả 2 path
  - **Cần test:**
    - Gọi 2 lần `acquire_single_instance()` — lần 2 trả False
    - Portable lock trên POSIX hoạt động đúng

### 4.7 License client tests

- [x] **P2** — Tạo `tests/test_license_client.py`
  - **Vấn đề:** `license_client/` có Protocol + models nhưng chưa có test cho `NotConfiguredLicenseClient`
  - **Cần test:**
    - `validate_cached()` trả `active=True` trong phase 0
    - `activate()` raise RuntimeError

---

## 5. BẢO MẬT

### 5.1 Local server path traversal

- [x] **P0** — Audit & fix `_serve_pdf()` trong `local_server.py:119-131`
  - **Vấn đề:** Kiểm tra `os.path.isabs(pdf_path) and pdf_path.lower().endswith(".pdf")` nhưng KHÔNG verify path nằm trong allowed directory. Attacker có thể đọc bất kỳ file `.pdf` nào trên máy
  - **Cách sửa:** Thêm whitelist directory hoặc reject paths ngoài user documents
  - **Code hiện tại:**
    ```python
    if not os.path.isabs(pdf_path) or not pdf_path.lower().endswith(".pdf"):
        self.send_error(400, "Invalid path")
        return
    if not os.path.isfile(pdf_path):
        self.send_error(404)
        return
    # THIẾU: kiểm tra pdf_path có nằm trong allowed directory không
    ```

### 5.2 API key storage

- [x] **P1** — Secure storage cho AI API keys
  - **Vấn đề:** `packages/ai/provider.py:81-101` lưu API keys vào `ai_config.json` plain text trong app data dir
  - **Cách sửa:** Dùng Windows DPAPI (`cryptprotectdata`) hoặc `keyring` library để encrypt
  - **File ảnh hưởng:** `packages/ai/provider.py`, `app/actions/ai_actions.py`

### 5.3 3T AI token storage

- [ ] **P1** — Secure token cho 3T AI
  - **Vấn đề:** `provider.py:385` lưu token vào `os.environ["3T_AI_TOKEN"]` — process-wide, visible trong `/proc`
  - **Cách sửa:** Lưu vào secure storage thay vì env var

### 5.4 Static file serving scope

- [x] **P2** — Restrict static file serving trong `local_server.py`
  - **Vấn đề:** `_serve_static()` serve bất kỳ file nào trong `pdfjs_root` — có thể expose source maps, debug files
  - **Cách sửa:** Whitelist chỉ cho phép `.html`, `.js`, `.css`, `.wasm`, `.properties`

---

## 6. CODE QUALITY

### 6.1 Remove unused imports

- [ ] **P2** — Audit unused imports
  - **Vấn đề:** `edit.py:1` import `asyncio` nhưng không dùng async ở đâu
  - **Cách sửa:** Chạy `ruff` hoặc `pylint` để detect unused imports

### 6.2 Fix bare/overly-broad exceptions

- [ ] **P2** — Audit exception handling
  - **Vấn đề:** Nhiều chỗ bắt `Exception` quá rộng, nuốt lỗi:
    - `window.py:267-271`: `load_ai_config()` wrapped trong bare except
    - `window.py:424-428`: audit log wrapped trong bare except
    - `single_instance.py:31`: mutex creation lỗi → fallback `return True`
  - **Cách sửa:** Catch specific exceptions, log nếu cần

### 6.3 Deduplicate polyfill code

- [ ] **P1** — Gộp duplicate polyfills
  - **Vấn đề:** `_PDFJS_RUNTIME_POLYFILL` trong `local_server.py:19-59` và `_MAP_POLYFILL_JS` trong `pdf_viewer.py:26-64` — cùng nội dung
  - **Cách sửa:** 1 file `assets/js/polyfill.js`, load từ cả 2 nơi

### 6.4 Text wrapping accuracy

- [x] **P2** — Fix `_draw_text_box()` trong `pdfium_engine.py:373-399`
  - **Vấn đề:** `max_chars = int(width / max(font_size * 0.55, 1))` — heuristic không chính xác với proportional fonts, có thể cắt sai từ
  - **Cách sửa:** Dùng `reportlab.paragraph.Paragraph` hoặc `canvas.drawCentredString` với proper text flow

### 6.5 Remove duplicate icon color dicts

- [x] **P1** — Gộp `_ICON_COLORS` và `_ICON_COLORS_LIGHT`
  - **Vấn đề:** 2 dict gần giống nhau trong `window.py:107-184`
  - **Cách sửa:** 1 dict base + transform function cho light/dark

---

## 7. BUILD & CI/CD

### 7.1 GitHub Actions CI

- [ ] **P1** — Tạo `.github/workflows/ci.yml`
  - **Vấn đề:** Không có CI pipeline, test chỉ chạy manual
  - **Cần:**
    - Run `pytest` trên mỗi push/PR
    - Lint với `ruff` hoặc `pylint`
    - Build PyInstaller smoke test
    - Matrix: Python 3.11, 3.12, 3.13

### 7.2 Code signing certificate

- [ ] **P1** — Windows code signing
  - **Vấn đề:** Executable chưa có digital signature → Windows SmartScreen chặn
  - **Cần:** EV hoặc OV code signing certificate, integrate vào Inno Setup build

### 7.3 Reduce package size

- [ ] **P2** — Giảm kích thước Tesseract bundle
  - **Vấn đề:** `third_party/tesseract/` chứa ~50+ DLLs, tăng size đáng kể
  - **Cách sửa:** Chỉ ship DLLs thực sự cần thiết, hoặc download on-demand khi user bật OCR

### 7.4 Dependency pinning

- [x] **P2** — Pin tất cả dependencies
  - **Vấn đề:** `requirements.txt` có một số deps dùng `>=` thay vì `==` (pytesseract, pdf2docx, pdfplumber, openpyxl)
  - **Cách sửa:** Pin exact versions trong requirements.txt, dùng `>=` chỉ trong pyproject.toml

---

## 8. UI/UX IMPROVEMENTS

### 8.1 Keyboard shortcuts documentation

- [ ] **P2** — Tạo `docs/KEYBOARD_SHORTCUTS.md`
  - **Vấn đề:** Shortcuts rải rác trong code (`Ctrl+O`, `Ctrl+S`, `Ctrl+H`, `F11`, etc.) nhưng không có docs tập trung
  - **Cách sửa:** Tổng hợp tất cả shortcuts, thêm vào Help menu

### 8.2 Tooltip consistency

- [ ] **P3** — Audit tooltips
  - **Vấn đề:** Một số action có tooltip chi tiết (VD: `"Chọn text/ảnh đã chèn → hiện nút ↻ Xoay, ✎ Sửa, × Xóa, ✥ Di chuyển"`), một số không có
  - **Cách sửa:** Đảm bảo tất cả QAction có tooltip mô tả rõ ràng

### 8.3 Welcome tab improvements

- [ ] **P3** — Cải thiện WelcomeWidget
  - **Vấn đề:** Welcome tab hiện tại chỉ có open/recent buttons
  - **Cách sửa:** Thêm recent files list, quick actions, version info

---

## 9. DOCUMENTATION

### 9.1 Architecture decision records

- [ ] **P3** — Tạo `docs/adr/` cho các quyết định kiến trúc quan trọng
  - **Vấn đề:** Quyết định chọn PdfiumEngine over PyMuPDF, QWebChannel bridge pattern, etc. chỉ nằm rải rác
  - **Cách sửa:** ADR format cho mỗi quyết định lớn

### 9.2 API documentation

- [ ] **P3** — Generate API docs
  - **Vấn đề:** Docstrings tiếng Việt tốt nhưng chưa có auto-generated docs
  - **Cách sửa:** Sphinx hoặc mkdocs cho `packages/` API

---

## 10. TECH DEBT CLEANUP

### 10.1 Remove legacy PyMuPDF code path

- [ ] **P2** — Audit `THREET_READER_PDF_ENGINE=pymupdf` code path
  - **Vấn đề:** `pymupdf_engine.py` vẫn tồn tại, `pyproject.toml` có optional `legacy-pymupdf` dependency
  - **Cách sửa:** Nếu đã quyết định dùng PdfiumEngine, xóa PyMuPDF code path

### 10.2 Clean up debug logs

- [x] **P2** — Xóa debug log files
  - **Vấn đề:** `debug_runtime.log`, `debug_runtime_heavy.log`, `debug_runtime_heavy2.log`, `debug_runtime_heavy3.log` nằm trong root
  - **Cách sửa:** Xóa files, thêm vào `.gitignore`

### 10.3 Clean up pytest temp files

- [x] **P3** — Xóa `pytest_tmp/` directory
  - **Vấn đề:** Temp files từ test runs nằm trong repo
  - **Cách sửa:** Xóa, thêm vào `.gitignore`

### 10.4 Consolidate `core/` into `packages/`

- [ ] **P2** — Move `core/pkcs11.py` và `core/recent.py` vào `packages/`
  - **Vấn đề:** `core/` chỉ có 2 files, kiến trúc đã chuyển sang `packages/`
  - **Cách sửa:** Move files, update imports

---

## SUMMARY BY PRIORITY

| Priority | Count | Items |
|----------|-------|-------|
| **P0** | 1 | Local server path traversal |
| **P1** | 12 | God object split, JS extraction, unit tests, API key security, CI/CD, code signing |
| **P2** | 18 | Search panel, CSS constants, more tests, code quality, build optimization |
| **P3** | 7 | Welcome tab, tooltips, ADR, API docs, temp cleanup |

---

## ESTIMATED EFFORT

| Category | Effort | Impact |
|----------|--------|--------|
| Tách God Object | 3-5 ngày | Giảm `window.py` từ 101KB xuống ~30KB |
| Tách JS inline | 1-2 ngày | Dễ maintain hơn, có syntax highlighting |
| Constants/Theme | 0.5-1 ngày | Dễ thay đổi giao diện |
| Unit Tests | 3-4 ngày | Coverage từ ~40% lên ~75% |
| Bảo mật | 1-2 ngày | Fix P0 + secure API keys |
| CI/CD | 1 ngày | Auto test + build |
| Code Quality | 1-2 ngày | Clean codebase |
| **Tổng** | **~12-17 ngày** | |

---

*Cập nhật: 2026-06-04*
