# 12 — Fix Roadmap

Lộ trình cho các vấn đề **còn mở** (chưa sửa) tính đến cuối phiên audit này. Ước tính thời gian dựa trên quy mô fix tương tự đã thực hiện trong chính phiên này (tham khảo thực tế, không phải ước lượng lý thuyết).

## Sprint 0 — Quyết định (không phải code, ưu tiên trước mọi sprint kỹ thuật)

**Thời gian**: 0 giờ kỹ thuật, cần 1 quyết định từ chủ dự án.

- Quyết định hướng xử lý PyMuPDF/AGPL (R1). Mọi sprint sau không phụ thuộc vào quyết định này, nhưng nên chốt sớm vì đây là rủi ro pháp lý duy nhất trong toàn bộ audit.

## Sprint 1 — Critical fixes

**Ước tính**: 1-2 ngày làm việc.

- R2: thêm khóa đồng bộ chung cho mọi điểm ghi file PDF (`sign.py`/`edit.py`/`document_ops.py`) — mở rộng `_PDF_SAVE_LOCK` vào `_pdf_save.py`.
- R3: sửa hiddenimport `google.genai` + thêm `huggingface_hub` vào build — khôi phục 2 nhà cung cấp AI.

## Sprint 2 — High Priority

**Ước tính**: 1 ngày làm việc.

- R4: thêm timeout + nút hủy cho vòng lặp cài iTaxViewer.
- R6: thêm nhánh light-mode cho 3 dialog (License, OCR, Audit-log) — copy pattern từ `ai_search_dialog.py`.

## Sprint 3 — Medium

**Ước tính**: 0.5-1 ngày làm việc.

- R5: thêm lock cho cache token PKCS11.
- Rà `piper_tts_manager.py`'s `DownloadThread` theo đúng pattern A2/A3 đã áp dụng — xác nhận nút "Đóng" có cần disable lúc đang tải hay không (cần điều tra thêm trước khi sửa, theo đúng quy tắc không suy đoán).

## Sprint 4 — Optimization

**Ước tính**: 0.5 ngày làm việc.

- Gỡ `pyqtdarktheme` khỏi `pyproject.toml`/`requirements.txt`.
- Đồng bộ version `pyproject.toml` ↔ `app/version.py` (script hóa hoặc bỏ comment gây hiểu nhầm).
- Dọn 8 asset SVG mồ côi (xác nhận lại trước khi xóa — kiểm tra cả `.qss` nếu có).
- Thống nhất 1 stack HTTP client (`requests`) thay vì 2 stack song song.

## Sprint 5 — Refactoring (xem chi tiết `13_Refactoring_Plan.md`)

**Ước tính**: nhiều sprint, không nên làm gấp — đưa vào roadmap dài hạn riêng, không xen vào các đợt vá lỗi.

- Tách phần in ấn ra khỏi `PDFReaderApp` (bước đầu cho việc giảm god-object).
- Gộp logic gộp/xoay/tách PDF về 1 engine duy nhất (hiện `annotate.py` và `pages.py` làm trùng bằng 2 cách khác nhau).
- Gộp 7 dialog QSS về dùng chung `styles/theme.py`.

## Ghi chú quan trọng

Roadmap này **không bao gồm lại** các fix đã hoàn thành trong chính phiên làm việc này (11 mục, xem `01_Executive_Summary.md`) — những mục đó đã ở production (bản 1.0.27).
