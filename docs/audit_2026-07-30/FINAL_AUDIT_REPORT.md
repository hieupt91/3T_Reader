# FINAL AUDIT REPORT — 3T Reader Phase 1 Windows

**Ngày**: 2026-07-30
**Phạm vi**: Enterprise software audit toàn diện — kiến trúc, code quality, UI/UX, hiệu năng, bảo mật, dependency, technical debt, bug hunt.
**Phương pháp**: 5 đợt điều tra sâu (2 thực hiện trước đó trong phiên làm việc, 3 thực hiện cho audit này), cộng 1 đợt xác minh/loại false-positive/gộp trùng lặp/tính lại ưu tiên trước khi phát hành báo cáo này.
**Trạng thái**: Audit-only — không có thay đổi code nào được thực hiện trong quá trình tạo 14 báo cáo này (các fix được nhắc tới ở phần "Đã xử lý" đã được thực hiện và deploy **trước khi** audit toàn diện này bắt đầu, trong cùng phiên làm việc).

---

## Mục lục

1. [Ghi chú phạm vi](#ghi-chú-phạm-vi)
2. [Đã xử lý trước audit này](#đã-xử-lý-trước-audit-này)
3. [Phát hiện Critical](#phát-hiện-critical)
4. [Phát hiện High](#phát-hiện-high)
5. [Phát hiện Medium](#phát-hiện-medium)
6. [Phát hiện Low / Informational](#phát-hiện-low--informational)
7. [Đã kiểm tra, xác nhận SẠCH](#đã-kiểm-tra-xác-nhận-sạch)
8. [Xác minh & loại false positive](#xác-minh--loại-false-positive)
9. [Điểm sức khỏe dự án](#điểm-sức-khỏe-dự-án)
10. [Roadmap tóm tắt](#roadmap-tóm-tắt)
11. [Danh sách 14 báo cáo chi tiết](#danh-sách-14-báo-cáo-chi-tiết)
12. [Phụ lục: toàn bộ file bị ảnh hưởng](#phụ-lục-toàn-bộ-file-bị-ảnh-hưởng)

---

## Ghi chú phạm vi

Checklist audit gốc người dùng cung cấp được viết cho ứng dụng mobile/Flutter. 3T Reader là ứng dụng **desktop Windows** (PySide6/Qt, chuột+bàn phím). Các mục không áp dụng (Tablet, Landscape, Touch targets, mobile gestures) được đánh dấu N/A kèm lý do trong từng báo cáo con, không bịa phát hiện để lấp đầy checklist.

## Đã xử lý trước audit này

11 vấn đề đã được tìm, sửa, test, và **deploy lên production (bản 1.0.27)** trong chính phiên làm việc, trước khi audit toàn diện 14-báo-cáo này được yêu cầu. Không liệt kê lại là "cần sửa" trong các mục dưới:

Crash/hiệu năng: race ghi-đè-file-lúc-thumbnail-render, `QThread.terminate()` (2 nơi), quét PKCS11 đồng bộ chặn UI, đọc outline PDF đồng bộ chặn UI, watermark nhiều trang chặn UI, module bị PyInstaller bỏ sót lúc đóng gói (gây crash mở app), OCR nền bỏ lỗi im lặng.
Bảo mật: API key AI mã hóa bằng key suy ra được → chuyển Windows Credential Manager, bộ cài iTaxViewer không kiểm tra checksum → thêm cơ chế sidecar hash.
UI: icon PDF không cập nhật ở Explorer Details view.

Chi tiết đầy đủ: `01_Executive_Summary.md`.

---

## Phát hiện Critical

### C1 — PyMuPDF (AGPL-3.0) đóng gói và sử dụng thật trong bản build production đã deploy

**Xác minh**: đã tự kiểm tra trực tiếp (không chỉ tin agent con) — `dist/3T_Reader_Secure/_internal/pymupdf/` tồn tại thật trong build vừa deploy; `app/actions/edit.py:2356,2570` có `import fitz` + `fitz.open(...)` dùng thật trong tính năng "Sửa text gốc" (`_find_pdf_span`, `_page_is_scan_text`, gọi từ `edit.py:2816,2822`). Xác nhận qua `git blame`: có sẵn từ 2026-07-07, không phải regression do phiên này.

**Vì sao Critical**: dự án tự tuyên bố đã gỡ PyMuPDF vì AGPL, chỉ còn 1 ngoại lệ đã biết — thực tế còn sót thêm. AGPL trong phần mềm thương mại đóng nguồn, không mua license Artifex, là vi phạm giấy phép thật, không phải rủi ro lý thuyết.

**Trạng thái**: đã báo cho chủ dự án; **quyết định**: ghi nhận vào báo cáo, xử lý sau (quyết định kinh doanh/pháp lý, không tự ý sửa).

**File**: `app/actions/edit.py`, `pyproject.toml` — chi tiết đầy đủ: `07_Security_Report.md` §Critical, `08_Dependency_Report.md` §C1.

---

## Phát hiện High

### H1 — Ghi file PDF không khóa đồng bộ nhất quán → mất dữ liệu âm thầm

`sign.py`/`edit.py`/`document_ops.py` không dùng `_PDF_SAVE_LOCK` mà `annotate.py`/`pages.py` dùng — nếu user bôi đen rồi lưu/ký trong cửa sổ debounce 250-520ms, 1 thao tác bị mất im lặng (last-writer-wins). File không hỏng (atomic replace), chỉ mất nội dung 1 thao tác.
**File**: `app/actions/sign.py`, `app/actions/edit.py`, `app/actions/document_ops.py`, `app/actions/_pdf_save.py`. Chi tiết: `10_Bug_List.md` §1.

### H2 — 2 nhà cung cấp AI (Gemini, HuggingFace) không hoạt động trong bản đóng gói

Thiếu `huggingface_hub`; `google.genai` có cài trong venv build nhưng vẫn không được đóng gói dù đã khai hiddenimports — cùng lớp lỗi đã sửa hôm nay cho `app.actions.annotate`.
**File**: `packages/ai/provider.py:273,458`, `3T_Reader.spec`. Chi tiết: `08_Dependency_Report.md` §H1.

### H3 — Vòng lặp chờ cài iTaxViewer không timeout, không nút hủy

Bộ cài bên thứ 3 treo sẽ khóa app window-modal vô thời hạn, không lối thoát trong app.
**File**: `app/actions/document_converter.py:1004-1039`. Chi tiết: `10_Bug_List.md` §3.

### H4 — 3 dialog hard-code màu dark-mode, không nhánh light-mode

Bug hiển thị thật (không chỉ code trùng lặp): mở License/OCR/Audit-log dialog khi app đang Light mode hiện bảng màu tối lệch tông.
**File**: `app/license_dialog.py`, `app/ocr_dialog.py`, `app/audit_log_dialog.py`. Chi tiết: `05_UI_UX_Report.md` §1.

---

## Phát hiện Medium

- **M1** — Cache token PKCS11 singleton không khóa, đọc/ghi từ 2 thread (`packages/signing/windows_provider.py`) — rủi ro chọn nhầm token khi nhiều USB ký số. `10_Bug_List.md` §2.
- **M2** — Dialog `license_dialog.py:169` kích thước cố định, rủi ro cắt nội dung lỗi dài (chưa xác minh trực quan). `05_UI_UX_Report.md` §2.
- **M3** — `pyqtdarktheme` là dependency chết hoàn toàn (0 import). `08_Dependency_Report.md` §M1.
- **M4** — `pyproject.toml` version lệch thủ công với `app/version.py`. `08_Dependency_Report.md` §M2.
- **M5** — `annotate.py`/`pages.py` trùng logic gộp/xoay/tách PDF bằng 2 engine khác nhau. `03_Architecture_Report.md`, `04_Code_Quality_Report.md`.

## Phát hiện Low / Informational

Đầy đủ ở từng báo cáo con (`05` §Low, `08` §Low, `09`). Tóm tắt: 0 dùng Qt Accessibility API, `assets/js/pdfjs_ui_hooks.js` dựa nhiều vào `setTimeout` polling (chưa xác nhận là bug), 8 asset SVG khả năng mồ côi, 2 stack HTTP client song song, God-object `window.py` (128 method), coupling UI/logic chặt (chấp nhận được ở quy mô hiện tại), duplicate `DownloadThread` ở `piper_tts_manager.py` (nghi vấn A3-class chưa xác nhận).

---

## Đã kiểm tra, xác nhận SẠCH

Danh sách đầy đủ ở từng báo cáo — liệt kê ở đây để tránh ai audit lại: license Ed25519 verify, self-updater (SHA256+chữ ký bắt buộc), local HTTP server (bind 127.0.0.1, chống path-traversal), `admin-config.json` không lọt git history, PIN ký số qua stdin, PFX password field, không auto-exec URI/JS trong PDF, DPI scaling (chỗ duy nhất cần thì đã làm đúng), hệ thống icon nhất quán, đệ quy đọc outline có try/except bọc an toàn, threading pattern ở `_start_update_check` và `annotate.py` đúng chuẩn, số học trang 0-index/1-index nhất quán ở mẫu kiểm tra, resource leak pikepdf/pypdfium2 (đều dùng `with` đúng cách), `_run_signing_task` có try/finally đúng.

---

## Xác minh & loại false positive

Theo yêu cầu "verify every finding, remove false positives, merge duplicates, recalculate priorities" trước khi phát hành báo cáo cuối:

1. **Tự xác minh trực tiếp C1** (không chỉ tin báo cáo agent con): chạy `ls`/`grep` thật trên `dist/3T_Reader_Secure/` và `app/actions/edit.py` — xác nhận đúng, không phải false positive.
2. **Gộp trùng lặp**: phát hiện "3 dialog light-mode bug" (UI/UX audit) và "7 dialog QSS trùng lặp" (code-quality audit trước đó) là **cùng 1 nhóm file, khác mức độ nghiêm trọng** — đã gộp thành 1 mục ở `04_Code_Quality_Report.md` với ghi chú rõ 3/7 có bug thật, 4/7 chỉ trùng code không ảnh hưởng UX. Không báo cáo 2 lần như 2 vấn đề riêng.
3. **Gộp trùng lặp**: "`DownloadThread` trùng lặp" xuất hiện ở cả code-quality audit lẫn security audit (dạng L3 "terminate() sót ở iTaxViewer") — phần `terminate()` đã sửa (commit `af91ad6`), phần "nghi vấn A3-class ở `piper_tts_manager.py`" vẫn mở, chỉ báo cáo 1 lần ở `04_Code_Quality_Report.md`, tham chiếu chéo từ `09_Technical_Debt.md`.
4. **Loại bỏ suy đoán không đủ bằng chứng**: "libshiboken crash A3" (từ audit trước) — vẫn giữ nguyên trạng thái "chưa xác nhận, không sửa" đúng theo quy tắc đã thống nhất, KHÔNG nâng thành finding chính thức trong audit này vì không có bằng chứng mới.
5. **Recalculate priority**: `pyqtdarktheme` ban đầu có thể bị đánh giá "High" chỉ vì là dependency — hạ xuống Medium sau khi xác nhận đây thuần túy là dead-weight, không có tác động chức năng/bảo mật nào.
6. **Recalculate priority**: H4 (3 dialog light-mode) được nâng từ "Medium" (nếu chỉ coi là code-quality) lên **High** trong risk assessment vì có bằng chứng cụ thể là bug hiển thị thật user thấy được, không chỉ là code smell — nhưng công sức sửa nhỏ (copy pattern có sẵn) nên xếp ưu tiên hành động ở Sprint 2, không phải Sprint 1.

---

## Điểm sức khỏe dự án

**Overall: 65/100** (ước tính ~70-75 nếu loại trừ accessibility và AGPL — 2 yếu tố có bối cảnh riêng, xem `14_Project_Health_Score.md`).

| Hạng mục | Điểm |
|---|---|
| Architecture | 62 |
| Maintainability | 63 |
| Scalability | 65 |
| Readability | 72 |
| Performance | 82 |
| Security | 70 |
| UI/UX | 70 |
| Accessibility | 25 |
| Testing | 58 |
| Code Quality | 68 |

---

## Roadmap tóm tắt

- **Sprint 0**: quyết định hướng PyMuPDF/AGPL (0 giờ kỹ thuật).
- **Sprint 1** (1-2 ngày): khóa ghi file thiếu nhất quán (H1), sửa 2 AI provider hỏng (H2).
- **Sprint 2** (1 ngày): timeout iTaxViewer (H3), 3 dialog light-mode (H4).
- **Sprint 3** (0.5-1 ngày): lock cache token (M1), rà `piper_tts_manager.py`.
- **Sprint 4** (0.5 ngày): dọn dependency chết, đồng bộ version, dọn asset mồ côi.
- **Sprint 5** (dài hạn, không gấp): tách in ấn khỏi god-object, gộp logic merge/rotate/split, gộp QSS dialog.

Chi tiết đầy đủ: `12_Fix_Roadmap.md`, `13_Refactoring_Plan.md`.

---

## Danh sách 14 báo cáo chi tiết

1. `01_Executive_Summary.md`
2. `02_Project_Statistics.md`
3. `03_Architecture_Report.md`
4. `04_Code_Quality_Report.md`
5. `05_UI_UX_Report.md`
6. `06_Performance_Report.md`
7. `07_Security_Report.md`
8. `08_Dependency_Report.md`
9. `09_Technical_Debt.md`
10. `10_Bug_List.md`
11. `11_Risk_Assessment.md`
12. `12_Fix_Roadmap.md`
13. `13_Refactoring_Plan.md`
14. `14_Project_Health_Score.md`

---

## Phụ lục: toàn bộ file bị ảnh hưởng

Danh sách file được tham chiếu là bằng chứng ở ít nhất 1 phát hiện trong 14 báo cáo trên (không tính file đã sửa/đóng trước audit này — xem `01_Executive_Summary.md` cho danh sách đó).

### Ứng dụng chính (`app/`)
- `app/window.py` — god-object, threading pattern
- `app/sidebar.py` — đệ quy outline, threading pattern
- `app/local_server.py` — đã audit bảo mật, sạch
- `app/license_dialog.py` — bug light-mode, dialog fixed-size
- `app/ocr_dialog.py` — bug light-mode
- `app/audit_log_dialog.py` — bug light-mode
- `app/ai_search_dialog.py` — tham chiếu pattern đúng (so sánh)
- `app/ai_chat_dialog.py`, `app/ai_summarize_dialog.py` — trùng lặp QSS (mức thấp hơn)
- `app/icon_utils.py`, `styles/icon_colors.py`, `styles/theme.py` — hệ thống icon/theme

### Action modules (`app/actions/`)
- `app/actions/annotate.py` — trộn domain, threading pattern đúng chuẩn
- `app/actions/edit.py` — **PyMuPDF/fitz (Critical)**
- `app/actions/sign.py` — thiếu khóa ghi file
- `app/actions/pages.py` — trùng logic với annotate.py
- `app/actions/document_ops.py` — thiếu khóa ghi file
- `app/actions/document_converter.py` — vòng lặp không timeout (iTaxViewer)
- `app/actions/piper_tts_manager.py` — `DownloadThread` trùng, nghi vấn chưa xác nhận
- `app/actions/auto_ocr.py`, `app/actions/ai_actions.py` — tham chiếu (không có finding mở mới)
- `app/actions/_pdf_save.py` — điểm cần mở rộng khóa (H1)

### Packages
- `packages/signing/windows_provider.py` — race cache token
- `packages/signing/__init__.py` — singleton provider
- `packages/ai/provider.py` — 2 AI provider hỏng trong build
- `packages/platform/secure_config.py`, `packages/license_client/credential_manager.py` — đã sửa trước audit này (tham chiếu)
- `packages/updater/update_client.py` — tham chiếu pattern đúng chuẩn (so sánh với iTaxViewer)

### Cấu hình / build
- `pyproject.toml` — PyMuPDF optional dep, version lệch, `pyqtdarktheme` chết
- `requirements.txt` — `pyqtdarktheme` chết
- `3T_Reader.spec` — hiddenimport `google.genai` sai
- `installer_script.iss` — đã sửa trước audit này (tham chiếu)
- `main_api.py` — backend VPS, đã audit bảo mật sơ bộ

### Assets
- `assets/icons/delete.svg`, `image_insert.svg`, `redo.svg`, `sidebar_hide.svg`, `sidebar_show.svg`, `text_insert.svg`, `theme_dark.svg`, `theme_light.svg` — khả năng mồ côi (Medium confidence)
- `assets/js/pdfjs_ui_hooks.js` — pattern setTimeout polling (chưa xác nhận bug)
