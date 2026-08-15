# 02 — Project Statistics

Số liệu lấy trực tiếp từ `git ls-files` + `wc -l` trên working tree tại thời điểm audit (không tính `.venv/`, `dist/`, `build/`). Nguồn: lệnh shell chạy trực tiếp, độ tin cậy cao (không phải ước lượng).

## Tổng quan file

| Loại | Số lượng |
|---|---|
| Tổng file tracked bởi git | 847 |
| File Python (`.py`) | 213 |
| File SVG (icon) | 69 |
| File Markdown (docs) | 56 |
| File PDF (test fixtures) | 24 |
| File PNG | 17 (16 trong `assets/`) |
| File JS | 5 |
| File YAML | 2 |
| File Inno Setup (`.iss`) | 2 |

## Lines of Code (Python)

| Module | LOC |
|---|---|
| `app/` | 31.408 |
| `packages/` | 8.389 |
| `tests/` | 5.756 |
| root-level `.py` (scripts, backend flat copies) | 4.232 |
| `core/` | 41 |
| `scripts/` | 436 |
| **Tổng Python LOC** | **~50.771** |

## 20 file lớn nhất (dòng)

| # | File | LOC | Ghi chú |
|---|---|---|---|
| 1 | `app/window.py` | 3.734 | God-object — xem `03_Architecture_Report.md` |
| 2 | `app/actions/annotate.py` | 3.186 | Trộn nhiều domain (annotation + rotate + merge) — xem `03` |
| 3 | `app/actions/edit.py` | 3.065 | Chứa fitz/PyMuPDF usage — xem `07`, `08` |
| 4 | `app/actions/sign.py` | 2.906 | |
| 5 | `app/local_server.py` | 1.728 | Đã audit bảo mật kỹ, sạch |
| 6 | `packages/signing/shared.py` | 1.477 | |
| 7 | `main_api.py` | 1.245 | Bản copy phẳng của VPS backend |
| 8 | `app/actions/document_ops.py` | 1.145 | |
| 9 | `app/actions/document_converter.py` | 1.141 | |
| 10 | `app/actions/tts_dialog.py` | 1.052 | |
| 11 | `packages/signing/windows_provider.py` | 907 | |
| 12 | `app/language_manager.py` | 796 | |
| 13 | `app/ai_translate_dialog.py` | 756 | |
| 14 | `app/actions/pages.py` | 682 | |
| 15 | `app/actions/ai_actions.py` | 666 | |
| 16 | `app/pdf_viewer.py` | 663 | |
| 17 | `app/pdf_inline_editor.py` | 623 | |
| 18 | `packages/ai/provider.py` | 617 | |
| 19 | `packages/ai/translate.py` | 605 | |
| 20 | `app/license_dialog.py` | 569 | Dialog light-mode bug — xem `05` |

**Trung bình LOC/file** (213 file .py, ~50.771 dòng): **~238 dòng/file** — hợp lý nếu bỏ 4 file khổng lồ đầu bảng (window.py, annotate.py, edit.py, sign.py chiếm ~13.000 dòng, 26% tổng LOC app+packages chỉ trong 4 file).

## Class/method size (ước lượng, không phải phân tích AST đầy đủ)

- `PDFReaderApp` (`app/window.py`): **128 method, 123 thuộc tính `self.X` riêng biệt** — xác nhận qua audit kiến trúc, xem `03_Architecture_Report.md`.
- Method dài nhất tìm được: `_open_pdfjs_print_preview` (`app/window.py`) — **464 dòng, 1 method duy nhất**.

## Test coverage (ước lượng)

| Chỉ số | Giá trị |
|---|---|
| File test (`tests/*.py`) | 41 |
| Test case (pytest collect) | **325** |
| LOC test / LOC nguồn (app+packages, ~39.800 dòng) | 5.756 / 39.800 ≈ **14.5%** |
| Phong cách test chủ đạo | `inspect.getsource()` + assert chuỗi văn bản (không gọi hàm thật, không cần QApplication chạy) |

**Diễn giải quan trọng** (đã xác nhận qua audit kiến trúc): tỷ lệ LOC test/nguồn thấp KHÔNG có nghĩa test suite "lười" — 202 hàm trong `app/actions/*.py` nhận `window` và đọc/ghi trực tiếp `window.viewer`/`window.sidebar`/`window.status`, khiến logic nghiệp vụ không tách được khỏi Qt để unit-test độc lập không cần app thật chạy. Test suite thích nghi bằng cách kiểm tra source string thay vì gọi hàm — một triệu chứng của coupling chặt, không phải nguyên nhân.

## Dependency

| Nhóm | Số lượng |
|---|---|
| Runtime dependencies (`pyproject.toml` base) | 16 |
| Optional dependency groups | 4 (`ai`, `legacy-pymupdf`, `legacy-pykcs11`, `build`) |
| Platform-specific (`pywin32`, win32 only) | 1 |

Chi tiết đầy đủ + vấn đề tìm được: `08_Dependency_Report.md`.

## Asset

| Loại | Số lượng | Ghi chú |
|---|---|---|
| SVG icon | 69 | ~8 file khả năng không được dùng (Medium confidence) — xem `08_Dependency_Report.md` §L4 |
| PNG | 16 (`assets/`) | Phần lớn là icon nhiều size (`icon_16.png`...`icon_1024.png`) cho build macOS/Windows, không phải asset chết |

## Cyclomatic complexity (ước lượng định tính)

Không chạy công cụ đo cyclomatic complexity chuyên dụng (ngoài phạm vi thời gian audit). Ước lượng định tính dựa trên độ dài method + số nhánh `except`/`if` quan sát được khi đọc code: **cao nhất ở `app/window.py`, `app/actions/annotate.py`, `app/actions/sign.py`** — cả 3 đều có method vượt 150-460 dòng với nhiều nhánh lồng nhau. Khuyến nghị nếu muốn số liệu chính xác: chạy `radon cc` hoặc `mccabe` trên `app/` — không có trong audit này vì yêu cầu công cụ ngoài, không nằm trong phạm vi "chỉ đọc code".
