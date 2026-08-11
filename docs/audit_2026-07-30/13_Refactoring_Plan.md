# 13 — Refactoring Plan

Đây là kế hoạch cho nợ kiến trúc **không khẩn cấp** — khác với `12_Fix_Roadmap.md` (vấn đề cụ thể cần sửa), file này bàn về tái cấu trúc dài hạn. **Không nên làm gấp, không xen vào đợt vá lỗi.** Ghi nhận để có kế hoạch, không phải chỉ thị hành động ngay.

## Nguyên tắc chung khi refactor app này

App đang chạy production, không có test suite gọi hàm thật (chỉ có string-assertion trên source, xem `02_Project_Statistics.md`). Bất kỳ refactor kiến trúc nào **PHẢI** đi kèm:
1. Viết test hành vi thật (không phải string-assertion) cho phần sắp refactor, TRƯỚC khi refactor.
2. Refactor từng module nhỏ, không đổi nhiều file cùng lúc.
3. Test thủ công trên app thật sau mỗi bước, không chỉ tin vào test tự động.

## Đề xuất 1 — Tách phần in ấn khỏi `PDFReaderApp`

**Hiện trạng**: `_open_pdfjs_print_preview` (464 dòng), `_do_print_pages` (169 dòng) sống trong `app/window.py`.

**Đề xuất**: tách thành `app/actions/print_ops.py` hoặc `app/print_dialog.py`, theo đúng pattern đã có ở các module `app/actions/*.py` khác (nhận `window` làm tham số, không cần đổi kiến trúc tổng thể).

**Vì sao ưu tiên đầu tiên**: đây là phần tách biệt rõ nhất khỏi phần còn lại của `PDFReaderApp` — ít phụ thuộc chéo nhất, rủi ro thấp nhất trong các lựa chọn refactor `window.py`.

**Không đề xuất**: refactor toàn bộ `window.py` cùng lúc — rủi ro cao không tương xứng lợi ích cho app quy mô này.

## Đề xuất 2 — Gộp logic gộp/xoay/tách PDF về 1 nguồn

**Hiện trạng**: `annotate.py` có `merge_pdf` (dùng `pikepdf.pages.extend()` thẳng), `pages.py` có `merge_pdfs_action` (dùng `get_pdf_engine().merge_pdfs()`) — 2 implementation độc lập cho cùng 1 tính năng.

**Đề xuất**: chọn 1 nguồn chân lý (khuyến nghị `get_pdf_engine()` vì đã là abstraction layer chính thức của app), chuyển `annotate.py` gọi qua đó, xóa implementation trùng.

**Rủi ro cần lưu ý**: 2 implementation có thể có hành vi khác nhau ở edge case (ví dụ xử lý PDF có mã hóa, có chữ ký số) — cần test kỹ trước khi hợp nhất, không giả định 2 bên tương đương.

## Đề xuất 3 — Gộp 7 dialog QSS về `styles/theme.py`

**Hiện trạng**: 7 dialog tự hard-code màu, chỉ 4/7 có nhánh dark/light đúng, 3/7 còn lại có bug hiển thị thật (đã liệt kê ở `05_UI_UX_Report.md`, nên sửa NGAY ở Sprint 2 của roadmap — không đợi refactor lớn).

**Đề xuất dài hạn** (sau khi Sprint 2 vá xong bug hiển thị): tạo 1 hàm/class style chung trong `styles/theme.py` mà cả 7 dialog gọi lại, xóa hoàn toàn QSS hard-code rải rác.

## Không đề xuất refactor (đã đánh giá, giữ nguyên)

- Coupling UI/business-logic (202 hàm nhận `window`) — chi phí tách rất lớn so với lợi ích thực tế ở quy mô app này, xem lý do đầy đủ ở `03_Architecture_Report.md`.
- PDF engine abstraction hiện tại (`get_pdf_engine()`) — đã là thiết kế tốt, không cần đổi.

## Ước tính effort tổng thể (không phải cam kết thời gian, chỉ tham khảo quy mô)

| Đề xuất | Quy mô | Rủi ro |
|---|---|---|
| Tách in ấn | Nhỏ-Trung bình | Thấp |
| Gộp merge/rotate/split | Trung bình | Trung bình (cần test kỹ edge case) |
| Gộp QSS dialog | Nhỏ | Thấp (sau khi bug hiển thị đã vá riêng) |
