# 03 — Architecture Report

## Kiến trúc tổng thể

```
main.py → single-instance guard → QApplication → PDFReaderApp (QMainWindow, app/window.py)
                                                    ├─ app/ribbon_bar.py (6 tab: Tệp&Xem/Chú thích/Trang/Bảo mật&Xuất/OCR&AI/Ký số)
                                                    ├─ app/sidebar.py (ThumbnailSidebar, BookmarkSidebar)
                                                    ├─ app/pdf_viewer.py → QWebEngineView chạy PDF.js (third_party/pdfjs/)
                                                    ├─ app/actions/*.py (business logic, ~20 module theo tính năng)
                                                    ├─ packages/pdf_engine/ (pypdfium2 + pikepdf)
                                                    ├─ packages/signing/ (PKCS11 + PFX)
                                                    ├─ packages/ocr/ (Tesseract)
                                                    ├─ packages/ai/ (đa nhà cung cấp: Claude/OpenAI/Groq/OpenRouter/Gemini/HF/Ollama)
                                                    ├─ packages/license_client/ (VPS + Ed25519 offline verify)
                                                    └─ app/local_server.py (HTTP local, phục vụ PDF.js)
```

Backend VPS (`main_api.py`, `vps_*.py` ở repo root) là bản copy phẳng của FastAPI backend thật chạy trên VPS — không phải kiến trúc app desktop, không đánh giá sâu ở đây (xem `07_Security_Report.md` cho phần backend).

## Phát hiện

### [High] God-object: `PDFReaderApp` (`app/window.py`)

**Bằng chứng**: 3.734 dòng, **128 method, 123 thuộc tính `self.X` riêng biệt**, 41 import ở đầu file. Một class duy nhất gánh: xây menu (`_build_menubar_impl`, 296 dòng), xây toolbar (`_build_toolbar_impl`, 363 dòng), **in ấn** (`_open_pdfjs_print_preview`, **464 dòng — 1 method**; `_do_print_pages`, 169 dòng), quản lý tab, i18n (`_apply_language_texts`, 177 dòng), theo dõi USB token định kỳ, update-check, drag&drop, context menu, theme toggle.

**Tác động**: mọi thay đổi nhỏ đều tăng rủi ro side-effect chéo giữa các domain không liên quan (in ấn không nên phụ thuộc cùng class với theo dõi USB token). Test thực (gọi hàm + assert kết quả, không phải string-matching) gần như bất khả thi vì mọi thứ đọc/ghi state qua `self`.

**Mức độ ưu tiên sửa**: Có giá trị, nhưng **KHÔNG nên refactor toàn bộ 1 lần** — rủi ro rất cao cho app thương mại đang chạy production, không có test thật để bảo vệ khỏi regression trong lúc tách. Nếu làm, ưu tiên tách phần in ấn (`_open_pdfjs_print_preview`) ra module riêng trước — tách biệt rõ nhất, ít phụ thuộc chéo nhất với phần còn lại của class.

### [Medium] `app/actions/annotate.py` chứa nhiều domain không liên quan tới "annotation"

**Bằng chứng**: file có `rotate_page_cw/ccw`, `_rotate_page`, `delete_current_page` (page ops), `merge_pdf`, `extract_pages` (document ops) — **trùng chức năng với `app/actions/pages.py`** (`rotate_pages_action`, `merge_pdfs_action`, `split_pdf_action`) nhưng cài đặt **độc lập, khác engine**: `annotate.py::merge_pdf` dùng `pikepdf.pages.extend()` thẳng, còn `pages.py::merge_pdfs_action` dùng `get_pdf_engine().merge_pdfs()`.

**Tác động**: 2 đường code khác nhau cho cùng 1 tính năng "gộp PDF" → sửa bug ở 1 nơi dễ quên nơi kia. Nợ kỹ thuật thật, chưa gây bug cụ thể được xác nhận, nhưng rủi ro tăng dần theo thời gian.

### [Low-Medium] Coupling UI/logic chặt, ảnh hưởng trực tiếp khả năng test

**Bằng chứng**: 202 hàm trong `app/actions/*.py` nhận `window` làm tham số và đọc/ghi trực tiếp `window.viewer`, `window.sidebar`, `window.status`, `window.current_path`.

**Đánh giá**: đây là nguyên nhân gốc khiến test suite (41 file, 325 test case) phải dùng `inspect.getsource()` + so khớp chuỗi thay vì gọi hàm thật — không phải test suite viết ẩu, mà vì business logic không tách được khỏi Qt. **Không đáng sửa ngay** — đây là tradeoff hợp lý cho app quy mô 1 người/nhóm nhỏ; refactor tách business-logic-khỏi-UI toàn bộ là công sức rất lớn so với lợi ích thực tế hiện tại. Ghi nhận để biết giới hạn, không phải việc cần làm gấp.

### [Informational] Điểm kiến trúc tốt, đáng ghi nhận

- `app/actions/_pdf_save.py`: điểm trung tâm hóa việc ghi file PDF (staged-file + atomic replace) — pattern đúng, được hầu hết action module dùng lại (trừ khoảng trống mô tả ở `10_Bug_List.md` §1 về khóa đồng bộ).
- `_run_signing_task` (`sign.py:172-208`): pattern `try/finally` đảm bảo dọn `_signing_thread` và resume token-monitor dù thành công hay lỗi — đúng chuẩn.
- `ThumbnailLoader`/`_OutlineLoader` (`app/sidebar.py`): pattern threading nền + signal đúng cách, có comment tự giải thích rõ ràng lý do (bound-method thay vì lambda để Qt suy đúng thread affinity) — hiếm thấy mức độ tự-document này trong 1 codebase quy mô nhỏ.
- PDF engine đã tách interface qua `packages/pdf_engine/` (`get_pdf_engine()`), cho phép thay pypdfium2/pikepdf mà không sửa call site — kiến trúc plugin hợp lý, dù việc `edit.py` vẫn dùng thẳng `fitz` ở 2 chỗ phá vỡ tính nhất quán này (xem `07`, `08`).

## SOLID / Clean Architecture — đánh giá tổng quan

- **Single Responsibility**: vi phạm rõ nhất ở `PDFReaderApp` và `annotate.py` (trên).
- **Dependency Inversion**: tương đối tốt ở tầng PDF engine (`get_pdf_engine()`), kém ở tầng action-vs-window (action module phụ thuộc trực tiếp cụ thể `window` object, không qua interface/protocol).
- **Open/Closed**: khó đánh giá không có ví dụ cụ thể về việc mở rộng tính năng đã khó khăn thế nào — không có bằng chứng trực tiếp, không đưa ra kết luận suy đoán.

## Kết luận

Kiến trúc app hoạt động tốt cho quy mô hiện tại, có vài điểm thiết kế tốt đáng giữ lại (PDF engine abstraction, pattern threading nền có document rõ). Nợ kiến trúc lớn nhất (`window.py` god-object) là có thật nhưng rủi ro refactor cao hơn lợi ích ngắn hạn — nên để dành cho 1 đợt tái cấu trúc có kế hoạch riêng (xem `13_Refactoring_Plan.md`), không xen vào các đợt vá lỗi.
