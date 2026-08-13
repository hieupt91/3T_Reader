# Roadmap: gỡ bỏ phụ thuộc PyMuPDF (AGPL-3.0)

**Ngày viết:** 2026-08-13. **Bối cảnh:** xem `docs/QA_REPORT_2026-08-12.md` và báo cáo QA cùng ngày — mục B2 (Critical, rủi ro pháp lý).

## Vấn đề

`PyMuPDF` (từ bản 1.14 trở lên, gồm bản `1.27.2.2` dự án đang khai báo) do Artifex phát hành theo dual license: **AGPL-3.0** miễn phí, hoặc license thương mại trả phí. AGPL yêu cầu: nếu phân phối phần mềm có nhúng thư viện AGPL, **toàn bộ phần mềm kết hợp** phải công bố mã nguồn theo AGPL. 3T Reader là sản phẩm thương mại đóng nguồn, và đã xác nhận `pymupdf` (37MB) **nằm thật trong bản build đóng gói** (`dist/3T_Reader_Secure/_internal/pymupdf`) gửi cho khách hàng.

## Còn dùng ở đâu (sau khi dọn `app/pdf_text_editor.py` ngày 2026-08-13)

| File | Trạng thái |
|---|---|
| `app/actions/edit.py::_find_pdf_span` | Đang dùng thật — lấy font/size/màu/vị trí span PDF cho tính năng "Sửa text gốc" |
| `app/actions/edit.py::_page_is_scan_text` | Đang dùng thật — phát hiện trang là scan (font "glyphless") hay PDF vector thường |
| `packages/pdf_engine/pymupdf_engine.py` | Chỉ chạy nếu set `THREET_READER_PDF_ENGINE=pymupdf` — không dùng trong production (engine mặc định là `pypdfium2`), nhưng vẫn tồn tại trong code và trong khai báo `pyproject.toml` (`legacy-pymupdf`) |

## Lưu ý quan trọng — KHÔNG "đọc code MuPDF/PyMuPDF rồi viết lại"

Luật bản quyền bảo vệ cách triển khai cụ thể (thuật toán/cấu trúc/logic), không chỉ ý tưởng chức năng. Đọc source AGPL rồi viết lại theo đúng logic đó — dù đổi tên biến, đổi ngôn ngữ — vẫn có thể bị coi là **derivative work**, vẫn dính AGPL. Cách hợp pháp duy nhất để "viết lại độc lập" là **clean-room reverse engineering** (1 đội đọc code gốc chỉ viết ra đặc tả chức năng, đội thứ 2 chưa từng thấy code gốc chỉ dựa vào đặc tả để viết code mới) — không áp dụng quy trình này thì không nên tự tin là đã "sạch".

**Nguồn tham khảo an toàn thay thế:**
- Chuẩn PDF công khai **ISO 32000-2** (đặc tả, không phải code có bản quyền của ai — tự do đọc/tham khảo).
- **`pypdfium2`** (PDFium của Google, Apache-2.0/BSD, permissive) — đã là engine chính của app, tự do đọc/tham khảo/mở rộng. Có API đọc từng ký tự kèm toạ độ + font size (`get_fontsize`, `get_charbox`...); phần còn thiếu là tự viết logic gộp ký tự liền kề thành "span" — logic tự nghĩ dựa trên hiểu biết cấu trúc PDF, không chép từ MuPDF.
- **LibreOffice** — MPL-2.0 (nhẹ hơn AGPL nhiều, cho phép nhúng vào phần mềm đóng nguồn; chỉ ràng buộc file nào copy/sửa trực tiếp từ LO thì file đó phải giữ mở theo MPL). Khả thi hơn MuPDF, nhưng phải tra đúng license từng module cụ thể trước khi lấy — LO có nhúng cả code bên thứ 3 khác license, "mã nguồn mở" không đồng nghĩa "an toàn tuốt".

## 3 giai đoạn

### Giai đoạn 1 — Đã xong (2026-08-13)
- [x] Xóa `app/pdf_text_editor.py` (dead code, không nơi nào import, dùng `fitz` trực tiếp).

### Giai đoạn 2 — Xây song song (chưa bắt đầu)
- [ ] Viết `_find_pdf_span`/`_page_is_scan_text` bản mới dựa trên API `pypdfium2` + chuẩn ISO 32000-2, **không đọc code MuPDF/PyMuPDF trong lúc viết**.
- [ ] Test song song: so sánh kết quả bản mới vs bản cũ trên bộ file thật đa dạng (PDF vector, PDF scan có OCR, nhiều font/màu) trước khi thay thế — đặc biệt cẩn thận vì đây đúng vùng đang có bug đã biết (B8: vùng chọn nhiều định dạng chỉ giữ được 1 kiểu).

### Giai đoạn 3 — Gỡ bỏ hoàn toàn (chưa bắt đầu)
- [ ] Gỡ `import fitz` khỏi `app/actions/edit.py`.
- [ ] Xóa `packages/pdf_engine/pymupdf_engine.py`.
- [ ] Gỡ `PyMuPDF`/`legacy-pymupdf` khỏi `pyproject.toml`.
- [ ] Build lại `dist/`, xác nhận `_internal/pymupdf` không còn xuất hiện trong bản đóng gói.

## Lựa chọn song song (không loại trừ lẫn nhau)

Trong lúc chờ Giai đoạn 2-3 hoàn thành, có thể cân nhắc **mua license thương mại từ Artifex** để hết rủi ro pháp lý ngay trong lúc code đang migrate dần — không cần chờ code xong mới an toàn.
