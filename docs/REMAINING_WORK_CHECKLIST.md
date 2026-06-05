# 3T Reader — Remaining Work Checklist

> Các phần còn lại cần làm. Mỗi mục có: mô tả, file liên quan, cách làm chi tiết, cách verify.
>
> **Ưu tiên:** `P1` = quan trọng, `P2` = nên làm, `P3` = nice-to-have

---

## 1. TÁCH RIBBON BUILDER (P1)

**Mục tiêu:** Tách `_build_toolbar()` (280 dòng) từ `window.py` ra `app/ribbon_builder.py`

### Checklist:
- [ ] Tạo file `app/ribbon_builder.py`
- [ ] Tạo class `RibbonBuilder` nhận `window` là parent
- [ ] Move `_build_toolbar()` logic (window.py:577-860) vào `RibbonBuilder.build()`
- [ ] Move `_ic()` icon helper function
- [ ] Move `_ICON_COLORS` import
- [ ] Update `window.py` gọi `RibbonBuilder(self).build()` thay vì `_build_toolbar()`
- [ ] Verify ribbon hiển thị đúng
- [ ] Verify dark/light theme hoạt động
- [ ] Verify tất cả ribbon buttons click được
- [ ] Run tests: `pytest tests/test_smoke_platform.py -q`

### Files:
- Tạo: `app/ribbon_builder.py`
- Sửa: `app/window.py` (remove ~280 dòng)

### Cách làm:
```python
# app/ribbon_builder.py
class RibbonBuilder:
    def __init__(self, window):
        self.window = window
    
    def build(self) -> RibbonBar:
        """Build and return the ribbon bar with all tabs."""
        ribbon = RibbonBar(self.window)
        # ... move _build_toolbar() logic here
        return ribbon
```

---

## 2. TÁCH TAB MANAGER (P1)

**Mục tiêu:** Tách tab lifecycle từ `window.py` ra `app/tab_manager.py`

### Checklist:
- [ ] Tạo file `app/tab_manager.py`
- [ ] Tạo class `TabManager(QTabWidget)`
- [ ] Move `_build_tab_host()` logic
- [ ] Move `open_document()` logic
- [ ] Move `_close_tab()` logic
- [ ] Move `_show_tab_context_menu()` logic
- [ ] Move `_on_tab_changed()` logic
- [ ] Update `window.py` sử dụng `TabManager`
- [ ] Verify mở/đóng tab hoạt động
- [ ] Verify tab context menu hoạt động
- [ ] Run tests

### Files:
- Tạo: `app/tab_manager.py`
- Sửa: `app/window.py` (remove ~150 dòng)

---

## 3. TÁCH SEARCH PANEL (P2)

**Mục tiêu:** Tách search panel từ `window.py` ra `app/search_panel.py`

### Checklist:
- [ ] Tạo file `app/search_panel.py`
- [ ] Tạo class `SearchPanel(QFrame)`
- [ ] Move `_build_search_panel()` logic
- [ ] Move `show_search_panel()` / `hide_search_panel()`
- [ ] Move `_search_from_panel()` / `_reposition_search_panel()`
- [ ] Update `window.py`
- [ ] Verify Ctrl+F hoạt động
- [ ] Run tests

### Files:
- Tạo: `app/search_panel.py`
- Sửa: `app/window.py` (remove ~90 dòng)

---

## 4. TÁCH STATUS BAR (P2)

**Mục tiêu:** Tách status bar builder từ `window.py` ra module riêng

### Checklist:
- [ ] Tạo file `app/status_bar_builder.py`
- [ ] Tạo function `build_status_bar(window)`
- [ ] Move `_build_statusbar()` logic
- [ ] Update `window.py`
- [ ] Verify status bar hiển thị đúng
- [ ] Run tests

### Files:
- Tạo: `app/status_bar_builder.py`
- Sửa: `app/window.py` (remove ~50 dòng)

---

## 5. TÁCH MENU BAR (P2)

**Mục tiêu:** Tách menu bar builder từ `window.py` ra module riêng

### Checklist:
- [ ] Tạo file `app/menu_builder.py`
- [ ] Tạo function `build_menubar(window)`
- [ ] Move `_build_menubar()` logic
- [ ] Update `window.py`
- [ ] Verify menu bar hoạt động
- [ ] Run tests

### Files:
- Tạo: `app/menu_builder.py`
- Sửa: `app/window.py` (remove ~100 dòng)

---

## 6. MOVE UPDATE CHECK WORKER (P3)

**Mục tiêu:** Move `_UpdateCheckWorker` class từ `window.py` ra `app/updater.py`

### Checklist:
- [ ] Đọc `app/updater.py` hiện tại
- [ ] Move `_UpdateCheckWorker` class (window.py:187-216) vào `updater.py`
- [ ] Update import trong `window.py`
- [ ] Verify update check hoạt động
- [ ] Run tests

### Files:
- Sửa: `app/updater.py`, `app/window.py`

---

## 7. HARDCODED STRINGS AUDIT (P2)

**Mục tiêu:** Tìm và catalog tất cả hardcoded Vietnamese strings

### Checklist:
- [ ] Chạy script tìm hardcoded strings:
  ```bash
  grep -rn "[àáảãạăắằẵặấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọốồổỗộớờởỡợùúủũụứừửữựỳýỷỹỵđĐ]" app/ --include="*.py"
  ```
- [ ] Tạo file `docs/HARDCODED_STRINGS.md` với danh sách
- [ ] Phân loại: error messages, UI labels, tooltips, status messages
- [ ] Đánh dấu strings nào cần i18n, strings nào OK giữ nguyên
- [ ] Tạo i18n keys cho strings quan trọng nhất

### Files:
- Tạo: `docs/HARDCODED_STRINGS.md`
- Có thể sửa: `app/language_manager.py` (thêm keys)

---

## 8. WINDOWS CODE SIGNING (P1)

**Mục tiêu:** Ký digital signature cho Windows executable

### Checklist:
- [ ] Mua EV hoặc OV code signing certificate (DigiCert, Sectigo, etc.)
- [ ] Install certificate trên build machine
- [ ] Tạo script `scripts/sign_windows.py`:
  ```python
  # signtool sign /f cert.pfx /p password /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist/3TReader.exe
  ```
- [ ] Update Inno Setup script để sign installer
- [ ] Test: verify signature trong Windows Explorer → Properties → Digital Signatures
- [ ] Test: Windows SmartScreen không chặn

### Files:
- Tạo: `scripts/sign_windows.py`
- Sửa: `installer/setup.iss`

### Lưu ý:
- EV certificate cần hardware token (~$300-500/năm)
- OV certificate rẻ hơn nhưng vẫn cần verify business

---

## 9. GIẢM TESSERACT BUNDLE SIZE (P2)

**Mục tiêu:** Giảm kích thước `third_party/tesseract/` (~50+ DLLs)

### Checklist:
- [ ] Liệt kê tất cả DLLs trong `third_party/tesseract/`
- [ ] Xác định DLLs nào thực sự cần thiết:
  ```bash
  # Chạy app với Process Monitor để xem DLLs nào được load
  ```
- [ ] Xóa DLLs không cần thiết
- [ ] Test OCR hoạt động với reduced set
- [ ] Cập nhật PyInstaller spec nếu cần
- [ ] Hoặc: download Tesseract on-demand khi user bật OCR lần đầu

### Files:
- Sửa: `third_party/tesseract/`
- Có thể sửa: `app/actions/ocr.py` (thêm download logic)

---

## 10. AUDIT TOOLTIPS (P3)

**Mục tiêu:** Đảm bảo tất cả QAction có tooltip

### Checklist:
- [ ] Tìm tất cả `QAction` trong `window.py` không có `setToolTip()`:
  ```bash
  grep -n "QAction\|addAction" app/window.py | grep -v "setToolTip"
  ```
- [ ] Thêm tooltip cho mỗi QAction thiếu
- [ ] Verify tooltips hiển thị khi hover
- [ ] Run tests

### Files:
- Sửa: `app/window.py`

---

## 11. CẢI THIỆN WELCOME WIDGET (P3)

**Mục tiêu:** Cải thiện welcome tab khi mở app

### Checklist:
- [ ] Đọc `app/window.py` tìm `WelcomeWidget` class
- [ ] Thêm recent files list (hiện 5 file gần nhất)
- [ ] Thêm quick actions: Open, New, Recent
- [ ] Thêm version info
- [ ] Thêm "What's New" link
- [ ] Verify hiển thị đúng
- [ ] Run tests

### Files:
- Sửa: `app/window.py`

---

## 12. TẠO ADR DOCS (P3)

**Mục tiêu:** Architecture Decision Records cho các quyết định kiến trúc

### Checklist:
- [ ] Tạo thư mục `docs/adr/`
- [ ] Tạo `docs/adr/001-pdf-engine-choice.md` — Why PdfiumEngine over PyMuPDF
- [ ] Tạo `docs/adr/002-qwebchannel-bridge.md` — Why QWebChannel over direct JS
- [ ] Tạo `docs/adr/003-local-http-server.md` — Why local server for PDF.js
- [ ] Tạo `docs/adr/004-signing-architecture.md` — Why pyHanko for signing
- [ ] Tạo `docs/adr/005-ai-provider-abstraction.md` — Why multi-provider AI
- [ ] Update `docs/README.md` tham chiếu ADRs

### Files:
- Tạo: `docs/adr/` (5 files)

---

## 13. GENERATE API DOCS (P3)

**Mục tiêu:** Auto-generated API documentation cho `packages/`

### Checklist:
- [ ] Install Sphinx hoặc mkdocs:
  ```bash
  pip install sphinx sphinx-rtd-theme
  ```
- [ ] Tạo `docs/api/conf.py`
- [ ] Tạo `docs/api/index.rst`
- [ ] Generate docs:
  ```bash
  sphinx-apidoc -o docs/api packages/
  ```
- [ ] Build HTML:
  ```bash
  sphinx-build docs/api docs/api/_build
  ```
- [ ] Verify docs generated
- [ ] Thêm vào `.gitignore`: `docs/api/_build/`

### Files:
- Tạo: `docs/api/` (Sphinx config)

---

## ƯU TIÊN THỰC HIỆN

### Tuần 1 — God Object refactor (P1)
- [ ] #1: Tách ribbon_builder.py
- [ ] #2: Tách tab_manager.py

### Tuần 2 — Medium refactor (P2)
- [ ] #3: Tách search_panel.py
- [ ] #4: Tách status_bar_builder.py
- [ ] #5: Tách menu_builder.py

### Tuần 3 — External + Audit (P1+P2)
- [ ] #8: Code signing (cần certificate)
- [ ] #7: Hardcoded strings audit
- [ ] #9: Tesseract bundle size

### Tuần 4 — Polish (P3)
- [ ] #6: Move UpdateCheckWorker
- [ ] #10: Audit tooltips
- [ ] #11: Welcome widget
- [ ] #12: ADR docs
- [ ] #13: API docs

---

## ƯỚC TÍNH EFFORT

| # | Mục | Effort | Impact |
|---|------|--------|--------|
| 1 | ribbon_builder | 2-3 giờ | Giảm window.py 280 dòng |
| 2 | tab_manager | 2-3 giờ | Giảm window.py 150 dòng |
| 3 | search_panel | 1 giờ | Giảm window.py 90 dòng |
| 4 | status_bar | 0.5 giờ | Giảm window.py 50 dòng |
| 5 | menu_builder | 1 giờ | Giảm window.py 100 dòng |
| 6 | UpdateCheckWorker | 0.5 giờ | Small cleanup |
| 7 | Hardcoded strings | 2-3 giờ | i18n readiness |
| 8 | Code signing | 1 giờ + certificate | Windows SmartScreen fix |
| 9 | Tesseract size | 1-2 giờ | Giảm package size |
| 10 | Tooltips | 1 giờ | UX polish |
| 11 | Welcome widget | 1-2 giờ | UX improvement |
| 12 | ADR docs | 1 giờ | Documentation |
| 13 | API docs | 1 giờ | Documentation |
| **Tổng** | | **~15-20 giờ** | |

---

*Cập nhật: 2026-06-05*
