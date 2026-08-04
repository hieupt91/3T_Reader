# QA toàn diện 3T Reader — 2026-08-04

Test trực tiếp trên app thật đang chạy (không đọc code suy đoán), dùng file PDF test có text thật (tạo bằng reportlab). Driver: `pywinauto` (backend `uia`), kiểm chứng bằng cách đọc lại file PDF bằng `pikepdf` sau mỗi thao tác, và **chụp màn hình thật** để xác nhận khi nghi ngờ — không kết luận chỉ dựa vào việc công cụ tự động "không thấy" cửa sổ.

**Bài học quan trọng rút ra giữa phiên (đọc trước khi tin bất kỳ mục "LỖI" nào)**: pywinauto (cả `click_input()` lẫn liệt kê `app.windows()`/`Desktop.windows()`) **2 lần báo sai** trong phiên này — "Gạch ngang" và sau đó "Ghi chú"/"Đọc sách" đều bị báo là lỗi (không hiện dialog) trong khi **chụp màn hình thật cho thấy dialog hiện đúng, đẹp, đầy đủ**. Nguyên nhân: công cụ UI Automation dùng để test không phát hiện được 1 số cửa sổ dialog của app này một cách đáng tin cậy — đây là hạn chế của phương pháp test, không phải lỗi của app. Vì vậy **mọi kết luận "LỖI" trong báo cáo này đều đã được xác nhận lại bằng ít nhất 1 trong 2 cách**: (a) đọc trực tiếp file PDF bằng pikepdf sau thao tác (khách quan tuyệt đối, không qua UI Automation), hoặc (b) chụp màn hình thật.

**Đã test kỹ, có bằng chứng thực nghiệm khách quan**: Tab "Tệp & Xem", Xoay trang, Gạch dưới, Gạch ngang, Tô sáng, Ghi chú, Đọc sách (TTS), Lưu, hàng đợi tự-lưu chú thích, **toàn bộ nhóm Trang** (Xóa trang/Ghép PDF/Tách PDF/Số trang/Xóa số trang), **toàn bộ nhóm Bảo mật & Xuất** (Watermark/Xóa watermark/Đặt mật khẩu/Xóa mật khẩu/Nén PDF/Xuất Word/Xuất Excel/Xuất Ảnh/Xuất Văn bản), **Auto-OCR** (tự động khi mở file scan), **AI Tóm tắt + Chat PDF** (gọi API Google Gemini thật, có key sẵn trên máy).
**Đã test kỹ với USB token thật (Viettel-CA)**: Kiểm tra USB, Ký số, Kiểm tra chữ ký, **Ký lô** (2 file cùng lúc) — cả 4 xác nhận OK, chữ ký **đã kiểm chứng độc lập bằng pyHanko** (ngoài app, không chỉ tin thông báo "thành công" của app).
**Đã test kỹ**: Chèn chữ, Vẽ tự do, Xóa đối tượng, Ô ký số, Chèn ảnh, Xóa trắng, Hoàn tác, Chọn & Xoay, Ký tay/dấu, **Dịch** (AI dịch thuật, gọi Gemini thật), **Tìm nghĩa** (báo lỗi đúng chuẩn khi thiếu OpenAI key, không crash), **OCR trang**, **OCR toàn bộ** (nhận dạng đúng 100%), **Ký PFX** (xác nhận đúng — app đúng đắn từ chối chứng thư tự-ký không có chuỗi tin cậy khi LTV bật, đã kiểm chứng bằng cách gọi thẳng hàm ký, không phải bug) — **tất cả OK**, kèm 1 lỗi nhỏ đã tìm thấy và sửa xong (dialog nhầm nhãn "Ký số" cho Vẽ tự do).
**Chưa test được**: Sửa text gốc (công cụ tự động không tạo được text-selection thật trong PDF.js, cần test tay), Tìm nghĩa thực tế tìm kiếm (cần OpenAI API key riêng, máy chỉ có Gemini key). Đây **không phải "OK"**, chỉ là chưa có bằng chứng trực tiếp.

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
| **Chèn ảnh** | Chọn file ảnh qua file picker thật → xem preview → xoay/đặt → "Đặt ảnh vào PDF" → `Ctrl+S` | Ảnh chèn đúng vị trí, đúng nội dung (render lại xác nhận) |
| **Xóa trắng** | Bật chế độ → kéo vùng đè lên text thật → `Ctrl+S` | Text bị xóa trắng sạch đúng vùng đã chọn (render lại xác nhận) |
| **Hoàn tác** | Chèn text mới (chưa lưu) → bấm Hoàn tác | Text vừa chèn biến mất đúng, không ảnh hưởng các object đã lưu trước đó |
| **Chọn & Xoay** | Chèn text mới → bật chế độ → click vào text | Hiện đúng bộ nút thao tác (di chuyển/xoay/sửa/xóa) trên object vừa chọn |
| **Ký tay/dấu** | Chọn "Vẽ tay" → vẽ nét trên canvas → đặt lên PDF → kéo vùng đặt → xác nhận → `Ctrl+S` | Nét chữ ký lưu đúng vị trí (render lại xác nhận). Đây là **con dấu hình ảnh**, không phải chữ ký số mật mã (không tạo `/AcroForm` — đã xác nhận qua pikepdf) — khác với "Ký số"/"Ô ký số" |
| **Dịch (AI)** | Nhập "Hello world, this is a test." → chọn "Tiếng Việt" → "Dịch ngay" (gọi Gemini thật) | Tự nhận diện đúng nguồn (English), dịch đúng: "Chào thế giới, đây là một bài kiểm tra." |
| **Tìm nghĩa (Semantic Search)** | Bấm "Xây dựng Index" khi máy chỉ có Gemini key (không có OpenAI key) | Báo lỗi đúng, rõ ràng: "Semantic search cần OPENAI_API_KEY. Vào menu AI → Cài đặt AI để nhập key." — không crash, không treo |
| **OCR trang** (nút thủ công) | Bấm "OCR trang" trên file có text thật | "Hoàn thành 1 trang — ~22 từ nhận dạng được", nội dung OCR khớp 100% văn bản gốc |
| **OCR toàn bộ** (nút thủ công) | Bấm "OCR tài liệu" trên file 3 trang | "Hoàn thành 3 trang — ~36 từ nhận dạng được", 100% tiến độ, nội dung khớp đúng cả 3 trang |
| **Ký PFX** | Tạo chứng thư tự-ký (self-signed) bằng `cryptography` để test độc lập, không đụng token thật → chọn vị trí → chọn file PFX → nhập mật khẩu → xác nhận | GUI báo lỗi "Ký từ file chứng thư thất bại" — **đã xác minh đây là hành vi ĐÚNG**: gọi thẳng hàm ký (`sign_pdf_with_pkcs12`) với đúng `enable_ltv=True` (cấu hình LTV thật đang bật trên máy) cho ra **chính xác cùng lỗi** `InvalidCertificateError: certificate ... is self-signed` — app đúng đắn từ chối chứng thư không có chuỗi tin cậy khi LTV bật (bảo mật đúng). Gọi lại với `enable_ltv=False` thì ký thành công, file hợp lệ (có `/AcroForm`) — xác nhận cơ chế ký PFX hoạt động đúng |
| **Ký lô** | Tạo 2 file PDF trong 1 thư mục → "Ký lô" → chọn vị trí trên file đang mở → chọn thư mục nguồn → chọn thư mục đích → nhập PIN token thật | "Ký số hàng loạt thành công 2 tài liệu!" — **cả 2 file kiểm chứng độc lập bằng pyHanko**: `intact=True, valid=True` |

---

## ✅ ĐÃ SỬA — dialog chọn vùng "Vẽ tự do" bị nhầm nhãn "Ký số"

- **Hiện tượng**: dùng "Vẽ tự do" → vẽ xong → app hiện hộp thoại **"Chọn vị trí ký"** / "Giữ chuột và kéo trực tiếp trên PDF để **vẽ vùng chữ ký**" — chữ này chỉ đúng cho tính năng Ký số.
- **Không phải lỗi chức năng** — nội dung (nét vẽ) vẫn chèn đúng vị trí, chỉ sai nhãn hiển thị, dễ gây hiểu lầm đang được yêu cầu ký số.
- **Nguyên nhân đúng (đã sửa lại kết luận ban đầu — lần đầu tôi chỉ nhầm sang `_pick_pdf_area`, đọc kỹ lại mới ra đúng chỗ)**: `app/actions/free_draw.py:41` gọi thẳng `_pick_signature_placement()` (`app/actions/sign.py`) — hàm vốn chỉ dùng cho 5 luồng ký số thật (Ký PFX, Ký token, Ký hàng loạt...) — để chọn vùng đặt hình vẽ trên trang, dùng chung `SignaturePickPrompt` với tiêu đề/hướng dẫn hard-code cứng cho ký số.
- **Đã sửa**: thêm 2 tham số tùy chọn `prompt_title`/`prompt_instruction` vào `SignaturePickPrompt.__init__` và `_pick_signature_placement()` (mặc định giữ nguyên chữ ký số y hệt cũ — 5 nơi gọi thật cho Ký số không đổi 1 dòng nào). `free_draw.py` truyền riêng: `"Chọn vị trí chèn"` / `"Giữ chuột và kéo trực tiếp trên PDF để đặt vùng chèn hình vẽ."`.
- **Phạm vi ảnh hưởng**: chỉ đổi chữ hiển thị cho đúng 1 luồng gọi (Vẽ tự do). 5 luồng Ký số thật (`sign.py` dòng 1938, 2044, 2199, 2524, 2828) không truyền tham số mới nên giữ nguyên hành vi/chữ hiển thị cũ 100%.
- **Đã kiểm tra**:
  - `pytest tests/` toàn bộ: 328 pass / 3 fail — đúng baseline (1 fail phát sinh lúc đầu là do process rác từ crash test trước đó chiếm khóa single-instance, đã xác nhận không liên quan code sửa — kill process xong chạy lại sạch).
  - Test trực tiếp trên app thật: Vẽ tự do → dialog hiện đúng "Chọn vị trí chèn" (không còn "chữ ký") → hoàn tất đặt vùng → `Ctrl+S` → render lại bằng pypdfium2 xác nhận nét vẽ vẫn chèn đúng vị trí như trước khi sửa.
- **Chưa commit** (mặc định theo `sualoint.md`/`FIX_RULES.md`).

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
| Chú thích | Sửa text gốc | Cần bôi đen text thật trong PDF.js — công cụ UI Automation không tạo được text-selection thật (đã thử 2 cách khác nhau, đều bị "Chưa chọn văn bản") |
| AI | Tìm nghĩa (bước tìm kiếm thực tế) | Đã xác nhận báo lỗi đúng khi thiếu OpenAI key; chưa test được bước tìm kiếm thật vì máy chỉ có Gemini key, không có OpenAI key |

---

## Đề xuất bước tiếp theo

1. Test tay "Sửa text gốc" (bôi đen thật bằng chuột) — công cụ tự động không làm được, cần bạn tự thử.
2. Nếu muốn test đầy đủ Tìm nghĩa, cần thêm OpenAI API key vào Cài đặt AI.
3. Theo dõi crash (Lỗi 2) trong sử dụng thực tế — đã áp dụng mitigation (tắt auto-GC), test dồn dập 20 phút không tái hiện được nhưng cần thời gian dài hơn mới xác nhận chắc chắn (xem `sualoint.md`).
4. Toàn bộ việc sửa lỗi tiếp theo vẫn tuân thủ `sualoint.md` (đọc kỹ trước khi sửa, sửa đúng trọng tâm, rà soát tránh xung đột code, test trước rồi mới commit).

---

## Tổng kết phiên QA 2026-08-04

Đã test **gần như toàn bộ** tính năng của 3T Reader trực tiếp trên app thật (không đọc code suy đoán), qua nhiều vòng:
- **~45 tính năng xác nhận OK** trải khắp 6 tab ribbon (Tệp & Xem, Chú thích, Trang, Bảo mật & Xuất, OCR & AI, Ký số) — gồm cả toàn bộ nhóm Ký số (USB token thật + Ký PFX + Ký lô), đã kiểm chứng độc lập bằng pyHanko cho mọi trường hợp ký.
- **2 lỗi thật tìm thấy — cả 2 đã sửa xong, test lại pass**: thiếu nhánh Tô sáng theo từ khóa; dialog Vẽ tự do nhầm nhãn "chữ ký".
- **1 vấn đề ổn định đã điều tra sâu + áp dụng mitigation**: crash `Qt6Core.dll`/`sizedFree` (93 lần từ 05/2026) — xác định đúng nguyên nhân (GC chạy sai thread, lỗi kinh điển PySide6/Qt) qua Windows Event Log + `pefile`, đã áp dụng fix (tắt auto-GC, `gc.collect()` định kỳ trên main thread), test dồn dập 20 phút không tái hiện được — **cần theo dõi thực tế dài hạn mới xác nhận chắc chắn hết lỗi**.
- **Chỉ còn 2 mục chưa test**, cả 2 đều ngoài khả năng của công cụ test tự động hoặc thiếu tài nguyên bên ngoài: Sửa text gốc (giới hạn PDF.js text-selection qua automation), Tìm nghĩa thật (thiếu OpenAI key).
