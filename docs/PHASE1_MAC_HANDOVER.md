# Phase 1 macOS → Windows Handover

> **Branch mac:** `phase1-mac` — 46 commits trên win  
> **Branch win:** `phase1-win`  
> **Tổng số file khác biệt:** 112 (64 file mới, 37 đã sửa, 3 đã xóa/đổi tên)  
> **Cập nhật lần cuối:** 2026-05-21  

---

## Cách sync nhanh

```bash
# 1. Đứng trên branch phase1-win
git checkout phase1-win

# 2. Chạy script tự động (trong thư mục gốc repo)
bash scripts/sync_from_mac.sh

# 3. Xem diff những file cần merge thủ công
bash scripts/sync_from_mac.sh --diff-only

# 4. Sau khi review xong → commit
git add .
git commit -m "sync: apply Phase 1 mac features to Windows"
```

---

## Tổng quan tính năng đã làm trên mac

### 1. UI/UX — Ribbon Bar (thay toolbar phẳng)

**File mới:**
- `app/ribbon_bar.py` — `RibbonBar`, `RibbonPanel`, `RibbonGroup`, `make_ribbon_btn()`

**File sửa:**
- `app/window.py` — toàn bộ toolbar được thay bằng ribbon (5 tab: Tệp, Xem, Chỉnh sửa, Công cụ, Ký số)

**Hành vi:**
- Tab style Word/Excel — highlight tab đang chọn với accent line
- Collapse button (∧/∨) — thu gọn/mở rộng panel
- Dark/light mode auto-apply qua `ribbon.set_theme(is_dark())`
- Icon màu theo theme: `_ICON_COLORS` (tối) / `_ICON_COLORS_LIGHT` (sáng)

---

### 2. UI/UX — Theme sáng/tối đầy đủ

**File sửa:**
- `styles/theme.py` — thêm `LIGHT_STYLESHEET` (2000+ dòng CSS)
- `app/icon_utils.py` — `svg_icon()` cache theo màu, hỗ trợ recolour
- `app/window.py` — `_refresh_icons()`, `_apply_toolbar_style()`, `_search_arrow_color()`

**Hành vi:**
- Tất cả icon SVG đổi màu khi toggle theme (dark: sáng/pastel, light: đậm/contrast cao)
- Toolbar background, search panel arrows, ribbon đều theo theme
- Tự detect macOS light/dark khi khởi động (AppleInterfaceStyle)

---

### 3. Chỉnh sửa inline (Inline PDF Editor)

**File mới:**
- `app/pdf_inline_editor.py` — `InlinePdfEditor`, JS bridge qua QWebChannel
- `app/insert_text_dialog.py` — `InsertTextDialog` (font, size, color picker)

**File sửa:**
- `app/actions/edit.py` — `insert_text_at_click()`, `insert_image_at_click()`

**Hành vi:**
- Click vào trang PDF → chọn vị trí → gõ text / chọn ảnh
- Overlay JS cho phép drag-resize trước khi commit vào PDF
- Dùng pikepdf + reportlab để ghi vào file thật

---

### 4. Tô sáng, Gạch, Xoá nội dung (Annotation)

**File mới:**
- `app/actions/annotate.py` — `highlight_text()`, `underline_text()`, `strikeout_text()`, `redact_text()`

**Hành vi:**
- Highlight: tô màu vàng vùng được chọn
- Underline/Strikeout: thêm annotation vào PDF
- Redact: xoá vĩnh viễn nội dung (xám hoặc đen)

---

### 5. Xử lý tài liệu (Document Ops)

**File mới:**
- `app/actions/document_ops.py` — watermark, password, compress, export images
- `app/actions/export.py` — export Word (.docx), Excel (.xlsx)
- `packages/document_core/converter.py` — `convert_pdf_to_docx()`, `convert_pdf_to_xlsx()`

**Hành vi:**
- Watermark: text đè lên tất cả trang
- Password: mã hoá PDF bằng pikepdf
- Compress: giảm kích thước file
- Export ảnh: mỗi trang → PNG/JPEG
- Export Word: dùng pdf2docx
- Export Excel: dùng pdfplumber + openpyxl

---

### 6. OCR tiếng Việt (Tesseract)

**File mới:**
- `app/actions/ocr.py` — `ocr_current_page()`, `ocr_full_document()`
- `app/ocr_dialog.py` — `OCRDialog` với progress + kết quả text
- `packages/ocr/__init__.py`, `packages/ocr/engine.py`

**File sửa:**
- `app/config.py` — thêm path Tesseract mặc định cho từng OS

**Hành vi:**
- Kiểm tra Tesseract + gói tiếng Việt khi OCR
- OCR 1 trang hoặc toàn bộ tài liệu (high-quality mode)
- Cảnh báo nếu > 50 trang
- Windows path mặc định: `C:\Program Files\Tesseract-OCR\tesseract.exe`

---

### 7. AI (Claude / OpenAI / Ollama)

**File mới:**
- `packages/ai/__init__.py`, `provider.py`, `chat_pdf.py`, `semantic_search.py`, `summarize.py`, `translate.py`
- `app/actions/ai_actions.py` — kết nối AI actions vào menu/ribbon
- `app/ai_chat_dialog.py` — Chat với PDF (streaming context)
- `app/ai_translate_dialog.py` — Dịch Việt↔Anh
- `app/ai_summarize_dialog.py` — Tóm tắt (provider + kiểu tóm tắt)
- `app/ai_search_dialog.py` — Semantic search (embeddings + cosine)

**Hành vi:**
- Auto-select provider: Claude → OpenAI → Ollama (local)
- Ollama offline: không cần API key, dùng `llama3.2:3b`
- Semantic search: chunk 500 ký tự, 80 overlap, cosine similarity
- API key lưu vào Keychain (macOS) / Credential Manager (Windows)

---

### 8. Ký số USB Token (PKCS#11)

**File mới:**
- `packages/signing/macos_provider.py` — tìm .dylib/.so (Homebrew, system, ~/Library)
- `app/actions/sign.py` — UI ký số đầy đủ (picker, preview, signature pad)
- `app/signature_pad.py` — `DrawingCanvas` vẽ chữ ký tay

**File sửa (Windows đã có):**
- `packages/signing/windows_provider.py` — tìm .dll trong System32/SysWOW64

**Hành vi:**
- Phát hiện USB token tự động khi cắm/rút
- Chọn vị trí ký: click vào trang PDF
- Preview điều chỉnh (drag + resize)
- Stamp kiểu Việt Nam: tên/MST/ngày tháng

---

### 9. License + Trial

**File mới:**
- `packages/license_client/credential_manager.py` — macOS Keychain / Windows Credential Manager
- `packages/license_client/fingerprint.py` — Device fingerprint
- `packages/license_client/keychain.py` — macOS Keychain wrapper
- `packages/license_client/token_verifier.py` — Ed25519 offline verification
- `packages/license_client/trial.py` — 30-day trial tracking
- `packages/license_client/vps_client.py` — VPS API calls
- `app/license_dialog.py` — `LicenseDialog` (format 3TR-[BPE]-XXXX-XXXX-XXXX)

**Hành vi:**
- Kiểm tra license khi khởi động (200ms delay)
- Trial 30 ngày: đếm ngày dùng, hiện countdown
- Kích hoạt online qua VPS `reader.3tcomputer.com`
- Verify offline bằng Ed25519 token (4 phần: body.sig.ed.pubkey)

---

### 10. Auto-Update

**File mới:**
- `app/update_dialog.py` — `UpdateDialog` (release notes + progress bar + install)
- `packages/updater/__init__.py`, `packages/updater/update_client.py` — Ed25519 manifest verification
- `packages/update_client/checker.py` — `check_for_update()`, `download_update()`

**File sửa:**
- `app/window.py` — `_auto_check_update()` (15s delay), `_show_update_dialog()`

**Hành vi:**
- Khởi động: sau 15s silent check VPS
- Nếu có bản mới: dialog với release notes + "Tải về ngay"
- Download với progress bar + SHA-256 verify
- macOS: `open <file.dmg>` | Windows: chạy `.exe` → app đóng

---

### 11. Audit Log

**File mới:**
- `packages/audit/__init__.py`, `packages/audit/logger.py`
- `app/audit_log_dialog.py` — `AuditLogDialog` (filter, search, export)

**Hành vi:**
- Ghi log mọi hành động: OPEN, PRINT, SIGN, OCR, AI, EXPORT, ...
- Thread-safe append
- Xem log trong app: menu Công cụ → Nhật ký hành động

---

### 12. Brightness Control

**File mới:**
- `app/actions/brightness.py` — `increase_brightness()`, `decrease_brightness()`

---

### 13. Welcome Screen + Sidebar cải tiến

**File mới:**
- `app/welcome_widget.py` — màn hình chào với logo + hướng dẫn khi chưa mở file
- `app/about_dialog.py` — dialog Giới thiệu

**File sửa:**
- `app/sidebar.py` — thumbnail threaded generation, bookmark/TOC
- `app/toolbar_prefs.py` — lưu/khôi phục trạng thái toolbar

---

### 14. Branding & Icon

**File mới:**
- `assets/logo_mark.svg`, `assets/logo.svg`, `assets/logo_full.svg`
- `assets/icon.ico` (Windows), `assets/3TReader.icns` (macOS)
- 18 SVG icons mới: brightness_up/down, delete_page, extract, highlight, insert_image, insert_text, merge_pdf, moon, redact, rotate_cw/ccw, save_as, sidebar, sign_draw, sun, trash

---

### 15. Legal / Compliance Documents

**File mới:**
- `EULA.md` — End-User License Agreement
- `PRIVACY_POLICY.md` — Chính sách quyền riêng tư
- `SETUP_WINDOWS.md` — Hướng dẫn dev setup Windows
- `docs/INLINE_EDITOR_GUIDE.md` — Hướng dẫn inline editor
- `docs/LICENSE_CLIENT_GUIDE.md` — Hướng dẫn kết nối license
- `docs/UI_BRANDING_GUIDE.md` — Hướng dẫn UI/branding
- `docs/VPS_DEPLOY_GUIDE.md` — Hướng dẫn triển khai VPS

---

## Files KHÔNG được override (Win-specific)

| File | Lý do |
|---|---|
| `packages/signing/windows_provider.py` | Tìm .dll trong System32 — khác mac |
| `installer/windows/3T_Reader_Setup.iss` | Inno Setup config cho Windows |
| `installer/windows/3T_Reader_win.spec` | PyInstaller spec Windows |
| `tests/test_smoke_windows.py` | Test Windows-specific |
| `app/platform_ui.py` | Ctrl vs ⌘ shortcut labels |

## Files cần merge thủ công (M — tồn tại cả 2 bên)

| File | Lý do cần thận trọng |
|---|---|
| `app/window.py` | Cốt lõi app — win có thể có code riêng |
| `main.py` | macOS dùng `defaults read AppleInterfaceStyle` |
| `app/config.py` | VPS URL đã sync, kiểm tra thêm |
| `styles/theme.py` | LIGHT_STYLESHEET cần apply toàn bộ |
| `packages/qt_compat/__init__.py` | Kiểm tra import order |
| `pyproject.toml` + `requirements.txt` | Merge dependencies |
| `3T_Reader.spec` | Mac spec khác win |

---

## Dependency mới cần cài thêm

```txt
# requirements.txt — thêm nếu chưa có
pdf2docx>=0.5.8
pdfplumber>=0.11.0
openpyxl>=3.1.0
pytesseract>=0.3.13
Pillow>=10.0.0
numpy>=1.24.0
anthropic>=0.25.0
openai>=1.30.0
requests>=2.28.0
```

```bash
pip install pdf2docx pdfplumber openpyxl pytesseract Pillow numpy anthropic openai requests
```

---

## Kiểm tra sau khi sync

```bash
# Chạy smoke tests
python -m pytest tests/test_smoke_platform.py -v

# Kiểm tra import không bị lỗi
python -c "from app.window import PDFReaderApp; print('OK')"

# Kiểm tra ribbon bar
python -c "from app.ribbon_bar import RibbonBar; print('OK')"

# Kiểm tra AI modules
python -c "from packages.ai.provider import ask_claude; print('OK')"
```
