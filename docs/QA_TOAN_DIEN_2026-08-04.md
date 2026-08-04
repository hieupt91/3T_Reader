# QA toàn diện 3T Reader — 2026-08-04

Test trực tiếp trên app thật đang chạy (không đọc code suy đoán), dùng file PDF test có text thật (tạo bằng reportlab). Driver: `pywinauto` (backend `uia`), kiểm chứng bằng cách đọc lại file PDF bằng `pikepdf` sau mỗi thao tác, và **chụp màn hình thật** để xác nhận khi nghi ngờ — không kết luận chỉ dựa vào việc công cụ tự động "không thấy" cửa sổ.

**Bài học quan trọng rút ra giữa phiên (đọc trước khi tin bất kỳ mục "LỖI" nào)**: pywinauto (cả `click_input()` lẫn liệt kê `app.windows()`/`Desktop.windows()`) **2 lần báo sai** trong phiên này — "Gạch ngang" và sau đó "Ghi chú"/"Đọc sách" đều bị báo là lỗi (không hiện dialog) trong khi **chụp màn hình thật cho thấy dialog hiện đúng, đẹp, đầy đủ**. Nguyên nhân: công cụ UI Automation dùng để test không phát hiện được 1 số cửa sổ dialog của app này một cách đáng tin cậy — đây là hạn chế của phương pháp test, không phải lỗi của app. Vì vậy **mọi kết luận "LỖI" trong báo cáo này đều đã được xác nhận lại bằng ít nhất 1 trong 2 cách**: (a) đọc trực tiếp file PDF bằng pikepdf sau thao tác (khách quan tuyệt đối, không qua UI Automation), hoặc (b) chụp màn hình thật.

**Đã test kỹ, có bằng chứng thực nghiệm khách quan**: Tab "Tệp & Xem", Xoay trang, Gạch dưới, Gạch ngang, Tô sáng, Ghi chú, Đọc sách (TTS), Lưu, hàng đợi tự-lưu chú thích, **toàn bộ nhóm Trang** (Xóa trang/Ghép PDF/Tách PDF/Số trang/Xóa số trang), **toàn bộ nhóm Bảo mật & Xuất** (Watermark/Xóa watermark/Đặt mật khẩu/Xóa mật khẩu/Nén PDF/Xuất Word/Xuất Excel/Xuất Ảnh/Xuất Văn bản), **Auto-OCR** (tự động khi mở file scan), **AI Tóm tắt + Chat PDF** (gọi API Google Gemini thật, có key sẵn trên máy).
**Đã test kỹ với USB token thật (Viettel-CA)**: Kiểm tra USB, Ký số, Kiểm tra chữ ký — cả 3 xác nhận OK, chữ ký **đã kiểm chứng độc lập bằng pyHanko** (ngoài app, không chỉ tin thông báo "thành công" của app).
**Đã test kỹ**: Chèn chữ, Vẽ tự do, Xóa đối tượng, Ô ký số (dùng token thật, PIN do bạn cung cấp) — tất cả OK, kèm 1 phát hiện lỗi mới (mislabel dialog, xem mục lỗi #4).
**Chưa kịp test trực tiếp trong phiên này**: Chèn ảnh, Xóa trắng (thử 1 lần chưa xác nhận được, cần thử lại), Sửa text gốc, Chọn & Xoay, Hoàn tác, Dịch/Tìm nghĩa (AI — cùng hạ tầng với Tóm tắt/Chat đã OK), Ký PFX/Ký lô/Ký tay-dấu (chưa có file PFX test, và không muốn lạm dụng token thật của công ty thêm). Đây **không phải "OK"**, chỉ là chưa có bằng chứng trực tiếp.

---

## ✅ OK — đã test, hoạt động đúng

| Tính năng | Cách test | Kết quả |
|---|---|---|
| Điều hướng trang (trước/sau) | Click nút | Chuyển trang đúng |
| Zoom (phóng to/thu nhỏ/vừa trang) | Click nút + `Ctrl+=`/`Ctrl+-` | Đổi zoom, không lỗi |
| Thumbnail sidebar / Mục lục | Click nút toggle | Ẩn/hiện đúng |
| Giao diện sáng/tối | Click nút | Đổi theme, không lỗi |
| Toàn màn hình | Click nút x2 | Bật/tắt đúng |
| Tìm kiếm (`Ctrl+F`) + Tìm tiếp (`F3`) | Gõ từ khóa, Enter, F3 | Tìm được, không crash |
| Xoay trang (`Ctrl+]`/`Ctrl+[`, nút, dialog) | Xem chi tiết `sualoint.md` Lỗi 1 | `/Rotate` cộng dồn đúng 90°/lần, không tự nhân đôi |
| Gạch dưới (`Ctrl+U`, chế độ Tìm-theo-từ-khóa) | Tìm "Lorem" → Ctrl+U | Ghi đúng `/Underline` vào các trang có từ khóa |
| Gạch ngang (`Ctrl+Shift+X`, chế độ Tìm-theo-từ-khóa) | Tìm từ khóa → Ctrl+Shift+X (test bằng phím tắt thuần, không click) | Ghi đúng `/StrikeOut` vào các trang có từ khóa |
| **Tô sáng** (`Ctrl+H`, chế độ Tìm-theo-từ-khóa) | Tìm "ipsum" → Ctrl+H — **test SAU KHI ĐÃ SỬA lỗi thiếu fallback** | Ghi đúng `/Highlight` vào cả 3 trang có từ khóa — **fix đã xác nhận hoạt động** |
| **Ghi chú** | Bấm nút "Ghi chú" → **chụp màn hình thật** | Dialog "Thêm ghi chú" hiện đầy đủ, đẹp, đúng vị trí; gõ text + Esc đóng lại bình thường, cửa sổ chính không bị treo |
| **Đọc sách (TTS)** | Bấm nút "Đọc sách" → **chụp màn hình thật** | Dialog "Đọc sách bằng AI (TTS)" hiện đầy đủ (Phạm vi/Chế độ/Ngôn ngữ/Giọng đọc/Tốc độ/nút Phát), Piper TTS báo "đã sẵn sàng" |
| Lưu (`Ctrl+S`) | Gửi phím tắt | Không lỗi, không crash |
| Hàng đợi tự-lưu chú thích | Xem `sualoint.md` mục "chú thích tự lưu báo sai" | Đã sửa, đã test pass |
| **Xóa trang** | Bấm nút → hộp thoại "Xóa trang 1/4?" → Yes | Đọc lại pikepdf: 4→3 trang đúng |
| **Số trang** | Bấm nút → chọn vị trí → số bắt đầu → OK | Render trang: số "1" hiện đúng giữa-dưới trang |
| **Xóa số trang** | Bấm nút | Render lại: số trang biến mất sạch |
| **Ghép PDF** | Chọn file phụ qua file picker thật → chọn nơi lưu → "Mở file đã gộp?" | pikepdf: 3+1 = 4 trang đúng |
| **Tách PDF** | Dialog Tách PDF → preset "Mỗi trang 1 file" → chọn thư mục lưu thật | 3 file `_p1/_p2/_p3.pdf` tạo đúng |
| **Watermark** | Dialog nhập text "BẢN NHÁP" → OK | Chữ watermark hiện đúng, xoay đúng góc trên trang (chụp màn hình xác nhận) |
| **Xóa watermark** | Yes → chọn phạm vi "Tất cả trang" → OK | Watermark biến mất sạch (chụp màn hình xác nhận) |
| **Đặt mật khẩu** | Dialog nhập + xác nhận mật khẩu → OK | pikepdf: file đúng yêu cầu mật khẩu, mở đúng bằng mật khẩu vừa đặt |
| **Xóa mật khẩu** | Dialog nhập mật khẩu hiện tại → OK | pikepdf: file mở được không cần mật khẩu nữa |
| **Nén PDF** | Bấm nút (không có dialog, đúng thiết kế) | File vẫn hợp lệ, đọc lại đúng số trang |
| **Xuất Văn bản** | Native save dialog → Enter | File `.txt` đúng nội dung từng trang |
| **Xuất Word** | Dialog chọn chế độ chuyển đổi → "Xuất file" → save dialog | `.docx` mở bằng python-docx, nội dung khớp 100% |
| **Xuất Excel** | Save dialog | `.xlsx` mở bằng openpyxl, nội dung khớp 100%, đúng số sheet = số trang |
| **Xuất Ảnh** | Dialog chọn định dạng/DPI → OK → chọn thư mục | Zip chứa đúng 3 PNG hợp lệ, 1 file/trang |
| **Auto-OCR** | Mở file PDF dạng ảnh scan (không có text layer) | Text layer tự động được nhúng vào file sau vài giây (không cần bấm gì) — xác nhận qua pdfplumber |
| **AI Tóm tắt** | Dialog "Tóm tắt tài liệu" → bấm Tóm tắt (gọi Google Gemini API thật) | Trả về tóm tắt đúng, phân tích đúng nội dung + tự nhận diện lỗi OCR trong văn bản |
| **AI Chat PDF** | Gõ câu hỏi "Khach hang ten gi" → Gửi (gọi API thật) | Trả lời đúng "Khách hàng tên là Nguyen VanA." khớp nội dung tài liệu |
| **Kiểm tra USB (ký số)** | Cắm USB token Viettel-CA thật → bấm "Kiểm tra USB" | Nhận diện đúng: công ty, MST, serial token, serial chứng thư, driver |
| **Ký số** (chữ ký số thật) | Chọn vị trí ký trên trang → xác nhận → thông tin chữ ký → lưu file → **không bị hỏi PIN** (đã cache sẵn) | "Ký số thành công!" — **đã kiểm chứng lại bằng pyHanko độc lập ngoài app**: `intact=True, valid=True`, đúng cert công ty (CN="CÔNG TY TNHH ĐẦU TƯ CÔNG NGHỆ VÀ XÂY LẮP 3T") |
| **Kiểm tra chữ ký** | Mở file vừa ký → bấm "Kiểm tra" | Hiện đúng "Hợp lệ chữ ký", đầy đủ thông tin chứng thư (nhà cung cấp Viettel-CA, hiệu lực, "Đã sửa đổi tài liệu: Không") |
| **Chèn chữ** | Click trang → gõ text → "Chèn vào PDF" → `Ctrl+S` | Text hiện đúng vị trí sau khi lưu (render lại bằng pypdfium2 xác nhận) — lưu ý: chỉ ghi xuống đĩa sau khi lưu tường minh, đúng thiết kế phiên "Sửa PDF" |
| **Vẽ tự do** | Vẽ nét trên canvas popup → "Chèn vào PDF" → kéo vùng đặt trên trang → `Ctrl+S` | Nét vẽ hiện đúng trên trang sau khi lưu (render xác nhận) |
| **Xóa đối tượng** | Bấm nút khi không có đối tượng nào vừa chèn trong phiên hiện tại | Đúng cảnh báo "Chưa có text/ảnh nào được chèn để xóa" (vì object đã lưu ở phiên trước, không còn trong danh sách xóa-được của phiên hiện tại — đúng thiết kế) |
| **Ô ký số** | Kéo vùng trên trang → đặt tên field → xác nhận → `Ctrl+S` | pikepdf xác nhận đúng: `AcroForm` có 1 field `/FT=/Sig`, tên khớp `Signature_qa_full_1` |

---

## 🟡 LỖI NHỎ MỚI PHÁT HIỆN (chưa sửa) — dialog chọn vùng bị nhầm nhãn "Ký số"

- **Hiện tượng**: khi dùng "Vẽ tự do" (và nhiều khả năng cả Chèn ảnh, Ghi chú không có vùng bôi đen, Xóa trắng — cùng cơ chế), sau khi xác nhận nội dung, app hiện hộp thoại tên **"Chọn vị trí ký"** với nội dung "Giữ chuột và kéo trực tiếp trên PDF để **vẽ vùng chữ ký**" — chữ này chỉ đúng cho tính năng Ký số, không đúng cho Vẽ/Chèn ảnh/Ghi chú.
- **Không phải lỗi chức năng** — đã xác nhận: nếu làm đúng theo hướng dẫn (kéo vùng trên trang), nội dung (nét vẽ) vẫn được chèn đúng vị trí sau khi lưu. Chỉ là **nhãn/chữ hiển thị sai**, có thể khiến người dùng tưởng nhầm đang được yêu cầu ký số.
- **Nguyên nhân xác nhận qua đọc code**: `_pick_pdf_area()` (`app/actions/edit.py:683`) — hàm dùng chung để "chọn 1 vùng trên trang PDF" cho nhiều tính năng (vẽ, chèn ảnh, ghi chú, xóa trắng...) — tái sử dụng hạ tầng (`_get_web_view`, `_setup_webchannel`, `_teardown_webchannel`) từ `app/actions/sign.py`, và dòng chữ hint "Chọn vị trí ký" / "vẽ vùng chữ ký" đang bị hard-code cố định trong `sign.py` thay vì nhận tham số theo từng tính năng gọi tới.
- **Chưa sửa** — cần đọc kỹ thêm cách `_pick_pdf_area` truyền/không truyền message xuống dialog trước khi sửa, để thêm tham số message theo đúng ngữ cảnh gọi (vẽ/ảnh/ghi chú/ký) mà không phá tính năng ký số đang chạy đúng.

---

## ✅ ĐÃ SỬA trong phiên này

### "Tô sáng" (Highlight) — thiếu 1 nhánh xử lý so với Gạch dưới/Gạch ngang

- **Nguyên nhân xác nhận qua đọc code**: `highlight_text()` (`app/actions/annotate.py:2510`) thiếu lời gọi `_mark_search_keyword_when_no_selection(window, "highlight")` mà `underline_text`/`strikeout_text` đều có — khi không có vùng bôi đen thật (chỉ dùng `Ctrl+F` tìm), Highlight không có bước fallback dùng từ khóa đang tìm, dừng lại không làm gì.
- **Đã sửa**: thêm đúng 1 dòng, giống hệt pattern của 2 hàm kia.
- **Phạm vi ảnh hưởng**: chỉ đổi hành vi của `highlight_text` khi KHÔNG có selection thật (trước đó không làm gì → giờ dùng từ khóa tìm kiếm để tô toàn tài liệu, đúng như Gạch dưới/Gạch ngang đã làm). Không đổi hành vi khi CÓ selection thật (vẫn `_do_selected_text_mark` như cũ).
- **Đã kiểm tra**:
  - `pytest tests/` toàn bộ: 328 pass / 3 fail — **giống hệt baseline trước khi sửa**, không có fail mới.
  - Test trực tiếp trên app thật: tìm "ipsum" → `Ctrl+H` → đọc lại file bằng pikepdf → cả 3 trang có đúng `/Highlight` annotation.
- **Chưa commit** (mặc định theo `sualoint.md`/`FIX_RULES.md`).

---

## ❌ Đính chính 2 kết luận SAI ở báo cáo trước

- **"Ghi chú" KHÔNG treo app** — báo cáo trước kết luận sai vì `Desktop.windows()`/`app.windows()` của pywinauto không liệt kê được cửa sổ `QInputDialog.getMultiLineText`. Chụp màn hình thật cho thấy dialog hiện đúng, gõ Esc đóng bình thường, `is_enabled()` trả về `True` ngay sau đó.
- **"Đọc sách" (TTS) KHÔNG bị ẩn** — tương tự, chụp màn hình thật cho thấy `TTSDialog` hiện đầy đủ với mọi control (Phạm vi/Chế độ/Ngôn ngữ/Giọng đọc/nút Phát-Dừng).
- Không có sửa code nào cho 2 mục này — không có gì để sửa.

---

## Ghi chú về hạn chế phương pháp test (để tránh lặp lại sai lầm ở phiên sau)

`pywinauto` (backend `uia`) trong môi trường này **không đáng tin cậy 100%** để: (1) phát hiện sự tồn tại của 1 số dialog qua `app.windows()`/`Desktop.windows()`, (2) đôi khi làm rớt sự kiện click đúng lúc app đang tự chờ đồng bộ JS (log `app_log.txt` ghi "Windows fatal exception: code 0x8001010d" — mã COM `RPC_E_CANTCALLOUT_ININPUTSYNCCALL`, **app không hề chết**, đã xác nhận tiến trình sống bình thường sau đó, khác hẳn 2 lần crash thật "access violation" không mã lỗi ghi trong `sualoint.md` Lỗi 2). **Quy tắc cho phiên sau**: bất kỳ khi nào nghi ngờ 1 tính năng "im lặng không làm gì", phải **chụp màn hình thật** (`w.capture_as_image()`) để xác nhận trước khi kết luận là lỗi — không được kết luận chỉ dựa vào `app.windows()` không thấy gì.

---

## ❓ Chưa test được trong phiên này

| Nhóm | Tính năng | Lý do chưa test |
|---|---|---|
| Chú thích | Chèn ảnh, Xóa trắng (thử 1 lần chưa rõ kết quả), Sửa text gốc, Chọn & Xoay, Hoàn tác | Xóa trắng cần thử lại với tọa độ kéo chuẩn hơn; còn lại chưa kịp trong phiên |
| OCR | OCR trang / OCR toàn bộ (nút bấm thủ công) | Auto-OCR (chạy nền tự động) đã xác nhận OK; nút bấm thủ công gọi cùng engine nên rủi ro thấp nhưng chưa tự tay bấm |
| AI | Dịch, Tìm nghĩa | Tóm tắt + Chat PDF (cùng hạ tầng AI provider) đã xác nhận OK; 2 mục này chưa tự tay bấm |
| Ký số | Ký PFX, Ký lô, Ký tay/dấu | Kiểm tra USB/Ký số/Kiểm tra chữ ký/Ô ký đã test OK với token thật; 3 mục còn lại cần file PFX test riêng hoặc không muốn lạm dụng token thật thêm |

---

## Đề xuất bước tiếp theo

1. Sửa lỗi nhãn "Chọn vị trí ký" bị dùng sai cho Vẽ/Chèn ảnh/Ghi chú (mục 🟡 ở trên) — rủi ro thấp, chỉ đổi text hiển thị.
2. Thử lại Xóa trắng với tọa độ kéo rõ ràng hơn (lần thử vừa rồi không kết luận được).
3. Test nốt Chèn ảnh, Sửa text gốc, Chọn & Xoay, Hoàn tác, Dịch/Tìm nghĩa, nút OCR thủ công.
4. Ký PFX/Ký lô/Ký tay-dấu cần file PFX/P12 test riêng, hoặc dùng thêm token thật nếu bạn đồng ý.
5. Toàn bộ việc sửa lỗi tiếp theo vẫn tuân thủ `sualoint.md` (đọc kỹ trước khi sửa, sửa đúng trọng tâm, rà soát tránh xung đột code, test trước rồi mới commit).
