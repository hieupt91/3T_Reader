# Đánh Giá Trạng Thái 14 Lỗi

Ngày cập nhật: 2026-06-26

Tài liệu này ghi lại đánh giá hiện tại dựa trên code và các commit đã có trong dự án. Trạng thái dưới đây không thay thế test UI thực tế; các lỗi liên quan thao tác trực quan vẫn cần mở app và kiểm tra lại đúng luồng người dùng.

## Tổng Quan

- Đã có bản fix rõ ràng: 10/14 lỗi.
- Đã fix một phần hoặc cần test kỹ thêm: 3/14 lỗi.
- Chưa phải lỗi kỹ thuật rõ ràng, cần xác định yêu cầu: 1/14 lỗi.

## Bảng Đánh Giá

| # | Lỗi | Trạng thái | Căn cứ / ghi chú |
|---|---|---|---|
| 1 | Mục In: chế độ 1 trang sau khi chuyển qua nhiều trang/2 trang rồi quay lại bị sai | Đã fix, cần test lại UI | Có commit `10259c5 Fix print preview single-page mode and blank-page insert refresh`, sửa `app/window.py`, `app/sidebar.py`, `app/actions/pages.py`. |
| 2 | Chèn trang sau lỗi `Pdf.add_blank_page() got an unexpected keyword argument 'page_index'` | Đã fix | Code hiện tại trong `app/actions/pages.py` không còn gọi `add_blank_page(page_index=...)`; đang tạo blank page rồi insert vào `pdf.pages`. |
| 3 | UI khi kéo text chèn hiển thị sai nội dung bên dưới trang thay vì nội dung text đang kéo | Một phần / cần test kỹ | Có commit `8a96db7 Fix text edit preview scaling` và `01ed550` liên quan text object editing. Tuy nhiên worktree hiện vẫn còn file dirty liên quan `app/webchannel.py`, `assets/js/inline_text_bridge.js`, `packages/pdf_engine/pymupdf_engine.py`, nên cần test trực quan trước khi kết luận xong. |
| 4 | Vẽ tự do: cho phép vẽ trước rồi chọn vùng chèn kèm UI trực quan | Đã fix theo code | Có commit `33906e8 Reorder free draw placement flow`, sửa `app/actions/free_draw.py` và nối lại action trong `app/window.py`. |
| 5 | Chọn xoay cho phép người dùng thu phóng nội dung chèn xoay | Một phần / cần test kỹ | Code có các luồng resize/rotate cho text/image/object, nhưng đang cùng vùng ảnh hưởng với lỗi #3. Cần test trên UI với text, ảnh, chữ ký/đối tượng đã xoay để kết luận. |
| 6 | Xóa trang xong viewer trắng, thumbnail vẫn có, phải tắt mở lại | Đã fix | Có commit `b93668f Fix blank viewer after page deletion reload`, sửa reload sau thao tác trang trong `app/actions/_pdf_save.py`, `app/actions/annotate.py`, `app/actions/pages.py`. |
| 7 | Lỗi khi đánh số trang | Đã fix | Có commit `ff1fc0d Fix page numbering reload and restrict non-PDF numbering`, sửa `app/actions/document_ops.py` và reload document. |
| 8 | OCR trang/OCR tài liệu bị giật UI hoặc chồng overlay | Đã fix | Có commit `697ee62 Lỗi số 8`, sửa `app/actions/ocr.py` và `app/ocr_dialog.py`, chuyển hướng dùng dialog/overlay ổn định hơn. |
| 9 | Chat PDF chưa hiện trực quan câu hỏi, mất lịch sử khi câu dài | Có vẻ đã fix, cần test câu dài thực tế | Code hiện có lưu history trong `packages/ai/chat_pdf.py`, dialog render lại history trong `app/ai_chat_dialog.py`, và có test liên quan history. Cần test UI với câu dài trên 10 chữ để xác nhận không mất nội dung. |
| 10 | Dịch đổi ngôn ngữ lần đầu được, đổi ngôn ngữ khác thì load mãi | Đã fix | Có commit `5151c22 Fix bug 10`, sửa `app/ai_translate_dialog.py` và tránh treo QThread khi dịch nhiều lần. |
| 11 | “Tìm nghĩa” có chức năng gì | Chưa xác định là lỗi | Đây hiện là câu hỏi/chưa có yêu cầu kỹ thuật cụ thể. Cần xác định muốn giữ, đổi tên, ẩn, hoặc triển khai chức năng tra nghĩa. |
| 12 | Đọc sách chọn tự nhận diện ngôn ngữ nhưng chỉ đọc tiếng Anh | Đã fix | Có commit `16953aa Fix bug 12`, sửa `app/actions/piper_tts_manager.py`, tăng nhận diện tiếng Việt và thêm nhận diện Zh/Ko/Th. |
| 13 | Ký số: kiểm tra USB/ký số không có USB chỉ cần thông báo ngắn | Đã fix | Luồng ký số đã đổi thông báo ngắn: kiểm tra USB không thấy thì báo “Không tìm thấy USB ký số”, ký khi chưa có USB thì báo “Vui lòng kết nối USB ký số.” |
| 14 | Ký ô, ký tay: không load lại nội dung đọc nhưng khung viền ngoài vẫn reload | Một phần / cần test kỹ | Có commit `375a102 fix(signing): refresh signature viewer state`, sửa reload mềm/cache chữ ký trong `app/actions/_pdf_save.py`, `app/actions/sign.py`, `app/local_server.py`, `app/pdf_viewer.py`, `assets/js/pdfjs_ui_hooks.js`, `packages/signing/shared.py`. Cần test UI thực tế vì đây là luồng nhạy: ký ô, ký USB trực tiếp, ký tay, click kiểm tra chữ ký, giữ trang/scroll. |

## Kết Luận Hiện Tại

Đã xử lý được phần lớn các lỗi có commit rõ ràng. Các mục nên ưu tiên test/sửa tiếp là:

1. Lỗi #14: ký số/ký ô/ký tay phải hiển thị trực quan ngay, giữ vị trí, click kiểm tra được.
2. Lỗi #3: preview khi kéo text chèn phải hiển thị đúng nội dung text đang thao tác.
3. Lỗi #5: xoay + thu phóng nội dung chèn cần đồng nhất với UI preview và kết quả lưu.
4. Lỗi #9: Chat PDF cần test câu dài thực tế để xác nhận không reload mất lịch sử.
5. Lỗi #11: cần xác định rõ “Tìm nghĩa” là tính năng tra từ, giải thích văn bản, hay nên ẩn/đổi tên.

## Ghi Chú Bàn Giao Phase 9

Đã tạo tài liệu bàn giao runtime tại:

- `docs/ACTIVE_RUNTIME_HANDOFF.md`

Tài liệu này mapping các luồng chính:

- Edit text/image.
- Annotation/undo.
- Signing.
- Viewer reload/cache/temp.
- Page operations/page numbers.
- OCR, Chat PDF, Translate, TTS.
- Print.

Kết quả gate tự động mới nhất nằm trong:

- `docs/CODE_CLEANUP_PHASE8_REPORT.md`

Trạng thái gate hiện tại:

- `py_compile`: PASS.
- `tests/test_pdf_save_helpers.py`: `14 passed`.
- `tests/test_local_server.py`: `15 passed`.
- `tests/test_stability_contracts.py`: `26 passed, 2 failed`.
- Full suite: `232 passed, 6 failed, 24 skipped`.

Vì vậy trước khi build release/chốt bàn giao, cần xử lý hoặc chấp nhận rõ 6 failed tests trong Phase 8 report và phải test UI thủ công theo checklist trong `docs/ACTIVE_RUNTIME_HANDOFF.md`.

## Ghi Chú Theo FIX_RULES.md

- Mặc định không commit file này nếu chưa được yêu cầu commit riêng.
- Khi xử lý từng lỗi tiếp theo, chỉ sửa đúng lỗi đang báo.
- Trước khi sửa phải đọc kỹ luồng code liên quan.
- Khi xong từng lỗi phải báo rõ file đã sửa, phạm vi ảnh hưởng và phần đã kiểm tra.
