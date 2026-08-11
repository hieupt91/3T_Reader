# 11 — Risk Assessment

Chỉ liệt kê các vấn đề **CHƯA xử lý** (các vấn đề đã sửa trong phiên này xem bảng ở `01_Executive_Summary.md`). Mỗi mục đầy đủ theo format yêu cầu.

---

## R1 — PyMuPDF (AGPL) đóng gói trong bản build thương mại

- **Mô tả**: `app/actions/edit.py` dùng `fitz.open()` thật (2 hàm), PyInstaller đóng gói kèm `pymupdf/` vào bản `.exe` đã deploy.
- **Nguyên nhân gốc**: việc "gỡ PyMuPDF vì AGPL" trước đây không triệt để — sót 2 điểm dùng ngoài ngoại lệ đã biết (`sign_handwritten`).
- **Vì sao xảy ra**: `pyproject.toml` chỉ khai `legacy-pymupdf` là optional, nhưng môi trường build thực tế có cài PyMuPDF nên PyInstaller tự phát hiện qua static analysis và đóng gói theo.
- **File liên quan**: `app/actions/edit.py:2356,2570`, `pyproject.toml:39`.
- **Ước tính tác động**: pháp lý/kinh doanh — vi phạm giấy phép AGPL nếu không mua license thương mại hoặc mở nguồn.
- **Tác động user**: không trực tiếp (tính năng vẫn hoạt động), rủi ro hoàn toàn ở phía doanh nghiệp.
- **Rủi ro regression nếu sửa**: cao nếu thay engine — cần đảm bảo `pypdfium2`/`pikepdf` có khả năng tương đương cho `_find_pdf_span`/`_page_is_scan_text`, chưa được đánh giá.
- **Hướng giải quyết đề xuất**: quyết định kinh doanh trước (mua license hay thay engine), không phải việc kỹ thuật thuần.
- **Ước tính công sức**: quyết định = 0 giờ kỹ thuật; nếu chọn thay engine = trung bình-lớn (cần thiết kế lại 2 hàm + test kỹ với nhiều loại PDF scan).
- **Phụ thuộc**: không phụ thuộc kỹ thuật nào khác, chỉ chờ quyết định.
- **Priority**: **Cao nhất về mức độ cần quyết định, không nhất thiết cao nhất về khẩn cấp kỹ thuật.**

---

## R2 — Ghi file PDF không khóa đồng bộ nhất quán (mất dữ liệu âm thầm)

- **Mô tả**: `sign.py`/`edit.py`/`document_ops.py` không dùng `_PDF_SAVE_LOCK` mà `annotate.py`/`pages.py` dùng.
- **Nguyên nhân gốc**: khóa được thêm cục bộ khi sửa 1 lớp bug cụ thể (chú thích/rotate) trước đây, không được nâng lên thành quy ước bắt buộc cho toàn bộ điểm ghi file.
- **Vì sao xảy ra**: thiếu 1 điểm trung tâm bắt buộc mọi hàm ghi file phải qua (tương tự cách A1 đã làm với `is_loading()` guard).
- **File liên quan**: `app/actions/sign.py`, `app/actions/edit.py`, `app/actions/document_ops.py`, `app/actions/_pdf_save.py`.
- **Ước tính tác động**: mất dữ liệu người dùng âm thầm (1 lần lưu/ký/chú thích bị ghi đè mất) trong kịch bản 2 thao tác ghi gần nhau về thời gian.
- **Tác động user**: Cao nếu xảy ra (mất công sức vừa làm), nhưng tần suất thực tế thấp (cần đúng lúc 2 thao tác chồng lấn trong cửa sổ vài trăm ms).
- **Rủi ro regression nếu sửa**: thấp — mở rộng phạm vi khóa đã có sẵn, cùng pattern đã dùng, không phải thiết kế mới.
- **Hướng giải quyết đề xuất**: đưa `_PDF_SAVE_LOCK` (hoặc tương đương) vào `_pdf_save.py` như 1 guard chung, giống cách A1 đã làm.
- **Ước tính công sức**: nhỏ-trung bình (tương tự quy mô fix A1 đã làm trong phiên này).
- **Phụ thuộc**: không.
- **Priority**: **High** — nên làm sớm, rủi ro sửa thấp, tác động mất dữ liệu là loại lỗi nghiêm trọng nhất với user dù hiếm gặp.

---

## R3 — 2 nhà cung cấp AI (Gemini, HuggingFace) không hoạt động trong bản đóng gói

- **Mô tả**: thiếu thư viện trong bản build dù đã khai hiddenimports.
- **Nguyên nhân gốc**: hiddenimport không khớp cấu trúc module thật của package namespace (cùng lớp lỗi đã sửa cho `app.actions.annotate` hôm nay).
- **File liên quan**: `packages/ai/provider.py:273,458`, `3T_Reader.spec`.
- **Ước tính tác động**: tính năng hỏng cho 2/7 nhà cung cấp AI.
- **Tác động user**: chọn Gemini/HuggingFace sẽ lỗi; Gemini có fallback message rõ ràng, HuggingFace chưa xác nhận có hay không.
- **Rủi ro regression nếu sửa**: thấp — chỉ chỉnh cấu hình build, không đổi logic.
- **Hướng giải quyết đề xuất**: cài `huggingface_hub` vào venv build + sửa hiddenimport `google.genai` đúng path thật.
- **Ước tính công sức**: nhỏ.
- **Phụ thuộc**: cần rebuild + test thật với từng provider sau khi sửa.
- **Priority**: **High** — ảnh hưởng trực tiếp tính năng user đang cố dùng, sửa rẻ.

---

## R4 — Vòng lặp chờ cài iTaxViewer không timeout/không hủy

- **Mô tả**: `_run_itax_installer_silent` có thể treo vô hạn nếu bộ cài bên thứ 3 treo.
- **Nguyên nhân gốc**: thiếu timeout + cố ý bỏ nút hủy (`setCancelButton(None)`).
- **File liên quan**: `app/actions/document_converter.py:1004-1039`.
- **Ước tính tác động**: khóa app hoàn toàn (window-modal), không lối thoát trong app.
- **Tác động user**: hiếm gặp (phụ thuộc hành vi bộ cài bên thứ 3) nhưng nghiêm trọng khi xảy ra (phải kill process qua Task Manager).
- **Rủi ro regression nếu sửa**: thấp — thêm timeout + nút hủy, không đổi luồng cài đặt chính.
- **Hướng giải quyết đề xuất**: thêm timeout hợp lý (vd 3-5 phút) + cho phép hủy, tương tự pattern đã áp dụng cho 2 luồng tải trong cùng file.
- **Ước tính công sức**: nhỏ.
- **Phụ thuộc**: không.
- **Priority**: **Medium-High**.

---

## R5 — Cache token PKCS11 singleton không khóa

- **Mô tả**: race nhẹ giữa UI thread và worker nền khi cùng làm mới cache token.
- **File liên quan**: `packages/signing/windows_provider.py:632-645`.
- **Ước tính tác động**: lãng phí tài nguyên (quét trùng), hoặc chọn nhầm token khi có nhiều USB ký số.
- **Tác động user**: thấp-trung bình, chỉ ảnh hưởng user có nhiều USB ký số cắm cùng lúc.
- **Hướng giải quyết đề xuất**: thêm `threading.Lock` quanh đọc/ghi `_tokens_cache`.
- **Ước tính công sức**: nhỏ.
- **Priority**: **Medium**.

---

## R6 — 3 dialog thiếu nhánh light-mode

- **Mô tả**: `license_dialog.py`, `ocr_dialog.py`, `audit_log_dialog.py` hiện màu tối bất kể theme.
- **File liên quan**: 3 file trên.
- **Tác động user**: rõ ràng, dễ thấy, ảnh hưởng trải nghiệm nhưng không mất chức năng.
- **Hướng giải quyết đề xuất**: thêm nhánh `is_dark()` giống `ai_search_dialog.py` đã làm đúng.
- **Ước tính công sức**: nhỏ (copy pattern có sẵn).
- **Priority**: **Medium-High** (dễ sửa, tác động thấy rõ).

---

## Mục Medium/Low còn lại (công sức nhỏ, không phân tích đầy đủ 12 mục để tránh phình báo cáo)

`pyqtdarktheme` dependency chết, `pyproject.toml` version lệch, 8 asset SVG mồ côi, `class DownloadThread` trùng ở `piper_tts_manager.py` chưa rà theo A3 — tất cả **Priority: Low**, gộp vào đợt dọn dẹp chung (`13_Refactoring_Plan.md`), không cần risk-assessment riêng từng mục.

## Ma trận tổng hợp

| ID | Mức độ | Priority | Công sức | Regression risk |
|---|---|---|---|---|
| R1 PyMuPDF/AGPL | Critical | Chờ quyết định | 0 (quyết định) / TB-lớn (nếu thay engine) | Cao nếu thay engine |
| R2 Khóa ghi file | High | High | Nhỏ-TB | Thấp |
| R3 AI provider hỏng | High | High | Nhỏ | Thấp |
| R4 Timeout iTaxViewer | High | Medium-High | Nhỏ | Thấp |
| R5 Race cache token | Medium | Medium | Nhỏ | Thấp |
| R6 Dialog light-mode | Medium(UX)/High(dễ sửa) | Medium-High | Nhỏ | Thấp |
