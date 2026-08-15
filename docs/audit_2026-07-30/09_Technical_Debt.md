# 09 — Technical Debt

Phân loại theo 6 nhóm yêu cầu. Mỗi mục tham chiếu báo cáo chi tiết tương ứng, không lặp lại toàn bộ nội dung.

## Architecture debt

- God-object `PDFReaderApp` (`app/window.py`, 3.734 dòng, 128 method) — `03_Architecture_Report.md`.
- `annotate.py` trộn domain annotation + page-ops, trùng logic với `pages.py` bằng 2 engine khác nhau — `03_Architecture_Report.md`.
- Coupling UI/business-logic chặt (202 hàm nhận `window` trực tiếp) — chấp nhận được ở quy mô hiện tại, không phải nợ cần trả ngay — `03_Architecture_Report.md`.

## Code debt

- 75% khối `except Exception:` là `pass` im lặng (đa số hợp lý, 1 trường hợp nguy hiểm đã sửa) — `04_Code_Quality_Report.md`.
- `class DownloadThread` trùng lặp 2 nơi, 1 nơi có nghi vấn nhẹ chưa xác nhận (A3-class) — `04_Code_Quality_Report.md`.
- 7 dialog tự hard-code QSS thay vì dùng `styles/theme.py` chung — `04_Code_Quality_Report.md`, `05_UI_UX_Report.md`.
- `pymupdf`/`fitz` còn sót lại dù dự án tuyên bố đã gỡ vì AGPL — vừa là nợ code vừa là nợ pháp lý, xem mục Security debt.

## Performance debt

- Đã trả phần lớn trong chính phiên này (PKCS11 scan, outline PDF, watermark — `06_Performance_Report.md`).
- Còn lại: vòng lặp chờ cài iTaxViewer không timeout (Medium), cache token PKCS11 không khóa (Low) — `06_Performance_Report.md`, `10_Bug_List.md`.

## UI debt

- 3 dialog thiếu nhánh light-mode (bug hiển thị thật, không chỉ nợ) — `05_UI_UX_Report.md`.
- 0 sử dụng Qt Accessibility API — nợ thấp ưu tiên, phụ thuộc định hướng thị trường tương lai — `05_UI_UX_Report.md`.

## Security debt

- **PyMuPDF/AGPL vẫn sống trong bản build** — nợ nghiêm trọng nhất toàn bộ audit, đã báo cáo riêng, chờ quyết định chủ dự án — `07_Security_Report.md`, `08_Dependency_Report.md`.
- 2 nhà cung cấp AI (Gemini, HuggingFace) không hoạt động trong bản đóng gói — nợ đóng gói/build, không phải lỗ hổng bảo mật, nhưng là bug thật ảnh hưởng user — `08_Dependency_Report.md`.
- Ghi file PDF không khóa đồng bộ nhất quán giữa các module (`sign.py`/`edit.py`/`document_ops.py` không dùng `_PDF_SAVE_LOCK`) — rủi ro mất dữ liệu âm thầm, không phải rủi ro bảo mật theo nghĩa tấn công nhưng nghiêm trọng với user — `10_Bug_List.md` §1.

## Maintainability debt

- `pyproject.toml` version lệch thủ công với `app/version.py` — nợ quy trình release — `08_Dependency_Report.md`.
- `pyqtdarktheme` dependency chết — nợ dọn dẹp nhỏ — `08_Dependency_Report.md`.
- 8 asset SVG khả năng mồ côi — nợ dọn dẹp nhỏ — `08_Dependency_Report.md`.

## Tổng nợ theo mức độ ưu tiên trả

1. **Phải quyết định sớm** (không phải "sửa gấp" mà là "cần 1 quyết định rõ ràng"): PyMuPDF/AGPL.
2. **Nên sửa trong 1-2 sprint tới**: khóa ghi file thiếu nhất quán, 2 AI provider hỏng trong bản build, 3 dialog light-mode bug, timeout cài iTaxViewer.
3. **Có thể để dành cho đợt dọn dẹp riêng, không khẩn**: god-object, duplicate QSS/DownloadThread, dependency chết, asset mồ côi, accessibility.
