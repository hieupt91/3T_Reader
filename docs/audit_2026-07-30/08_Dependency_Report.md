# 08 — Dependency Report

## [Critical] C1 — PyMuPDF (AGPL) đóng gói thật trong bản build đã deploy

Xem `07_Security_Report.md` cho tóm tắt tình huống pháp lý. Chi tiết kỹ thuật:

- Khai báo chỉ ở nhóm optional `legacy-pymupdf` trong `pyproject.toml:39` (KHÔNG nằm trong `dependencies` gốc, KHÔNG trong `requirements.txt`) — nhưng `pip install`ed thật trong `.venv` dùng để chạy `build_secure.py`, nên PyInstaller phân tích tĩnh phát hiện `import fitz` thật trong `app/actions/edit.py:2352` (`_find_pdf_span`) và `edit.py:2566` (`_page_is_scan_text`) rồi đóng gói kèm.
- 2 hàm này được gọi thật từ tính năng user-facing "Sửa text gốc" ở `edit.py:2816` và `edit.py:2822` — **không phải code chết**.
- Xác nhận trực tiếp: `dist/3T_Reader_Secure/_internal/pymupdf/` tồn tại trong bản build vừa deploy.

**Hướng xử lý**: quyết định pháp lý/kinh doanh (mua license Artifex hoặc thay bằng pypdfium2/pikepdf đã dùng ở phần lớn app) — không tự ý sửa.

## [High] H1 — 2 nhà cung cấp AI không hoạt động trong bản đã đóng gói

**File**: `packages/ai/provider.py:273` (`from huggingface_hub import InferenceClient`), `provider.py:458` (`from google.genai import types`).

- `huggingface_hub` **không cài** trong `.venv` dùng để build, **không có** trong `dist/3T_Reader_Secure/_internal/`.
- `google-genai` **có cài** trong `.venv` dev nhưng **vẫn không được đóng gói** dù `3T_Reader.spec` đã khai `'google.genai'` trong `hiddenimports` — khả năng cao là **cùng lớp bug** đã tìm và sửa hôm nay cho `app.actions.annotate` (hiddenimport không khớp đúng cấu trúc module thật của package namespace), lần này ở 1 package bên thứ 3 khác.
- OpenAI/Anthropic/Groq/OpenRouter **không bị ảnh hưởng** — gọi thẳng REST API qua `requests`, không cần SDK riêng.

**Tác động user**: chọn nhà cung cấp AI là HuggingFace hoặc Gemini sẽ lỗi. Gemini có fallback message thân thiện sẵn (`provider.py:492`: "Chưa cài google-genai: pip install google-genai") — degrade rõ ràng chứ không crash. HuggingFace chưa xác minh hết đường lỗi, khả năng cao raise ImportError không bắt.

**Hướng xử lý**: thêm `huggingface_hub`/sửa hiddenimport cho `google-genai` đúng path module thật trong `.venv` build, hoặc tạm ẩn 2 provider này khỏi UI nếu chưa sẵn sàng phát hành.

## [Medium] M1 — `pyqtdarktheme==0.1.7` là dependency chết hoàn toàn

Khai báo ở `pyproject.toml:16` và `requirements.txt:5`, **0 import** ở bất kỳ đâu trong `app/`, `packages/`, `main.py` (đã grep cả `pyqtdarktheme` lẫn tên import `qdarktheme`), không xuất hiện trong `3T_Reader.spec`. App dùng module tự viết `styles/theme.py` thay thế hoàn toàn. Ngoài ra đây cũng là package khá cũ/ít được bảo trì (Medium confidence, chưa kiểm tra registry trực tiếp). Chỉ tốn dung lượng cài đặt và bề mặt xung đột version, không có chức năng gì.

**Hướng xử lý**: gỡ khỏi `pyproject.toml` và `requirements.txt`.

## [Medium] M2 — `pyproject.toml` version lệch với `app/version.py`

`pyproject.toml:4` ghi `version = "1.0.25"` trong khi `app/version.py` (nguồn chân lý theo đúng comment của chính `pyproject.toml`) hiện là `"1.0.27"` — xác nhận việc đồng bộ là thủ công và không thực sự được làm đều đặn.

**Hướng xử lý**: script hóa việc đồng bộ vào quy trình release, hoặc bỏ comment gây hiểu nhầm.

## Low / Informational

| # | Phát hiện | Confidence |
|---|---|---|
| L1 | 2 stack HTTP client song song (`urllib.request` ở `document_converter.py` vs `requests` ở `license_client/`, `updater/`) cho cùng loại việc — trùng lặp nhẹ, không phải bug | High |
| L2 | `ai`/`legacy-pykcs11` optional groups đối chiếu ổn — `openai`/`anthropic` không cần thiết ở tầng pip vì dùng `requests` thẳng, khớp đúng những gì đã đóng gói. `legacy-pykcs11` (`PyKCS11==1.5.18`) chưa rà được có còn import ở đâu không — chưa xác nhận, cần pass riêng | Low |
| L3 | Version pinning / CVE — không kết luận được đáng tin cậy chỉ bằng đọc code (`cryptography==46.0.7`, `requests==2.33.1`, `Pillow==12.2.0`, `PySide6==6.11.0` không có bản nào trông rõ ràng là cũ/EOL, nhưng cần chạy `pip-audit`/`safety` thật để chắc chắn) | Low |
| L4 | 8 file asset SVG khả năng không dùng: `delete.svg`, `image_insert.svg`, `redo.svg`, `sidebar_hide.svg`, `sidebar_show.svg`, `text_insert.svg`, `theme_dark.svg`, `theme_light.svg` — không tìm thấy tên file lẫn tên gốc (không đuôi) ở bất kỳ đâu trong `app/`, `packages/`, `styles/`. Đã loại trừ khả năng false-positive do dynamic-construction dạng `f"icons/{name}.svg"` cho 8 file này | Medium |
| L5 | Không tìm thấy chỗ nào bypass helper ghi file chung `_pdf_save.py` bằng `os.replace()`/`shutil.move()` thô trong `app/actions/*.py` — tin tốt, xác nhận việc trung tâm hóa ghi file (fix A1) không có lỗ hổng | High |
| L6 | Rà quét lớn 1 file (`window.py`) cho code comment-out lớn — không tìm thấy. Chưa quét hết toàn bộ codebase | Medium |
| L7 | Rà unused-function hệ thống trên 5 file lớn nhất (`window.py`, `annotate.py`, `edit.py`, `sign.py`, `local_server.py`) **chưa hoàn thành** trong thời gian audit — ghi nhận rõ là chưa làm, không báo cáo kết quả "sạch" giả | — |

## Tổng kết

| Mức độ | Số lượng |
|---|---|
| Critical | 1 |
| High | 1 |
| Medium | 2 |
| Low/Informational | 7 |
