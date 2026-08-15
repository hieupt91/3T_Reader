# Báo cáo đánh giá toàn diện lỗi dự án 3T Reader

Ngày lập: 03/07/2026  
Phạm vi: `C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win`  
Nguồn dữ liệu chính: `C:\Users\HieuPC\Downloads\Test Case 3T Reader.xlsx`, mã nguồn dự án, `BAO_CAO_LOI_TESTCASE.md`, `BAO_CAO_BAO_MAT_HA_TANG.md`

## 1. Tóm tắt điều hành

File test case ghi nhận 41 testcase, trong đó TC01-TC26 đang ở trạng thái Pass và TC27-TC41 đang Fail. Nhóm Fail còn lại tập trung vào 5 vùng rủi ro chính: annotation/search UI, chỉnh sửa PDF gốc, đồng bộ trạng thái sau thao tác file, OCR/AI trên PDF scan, in ấn/license.

Đánh giá theo mức độ:

| Mức độ | Testcase | Số lượng | Ý nghĩa kỹ thuật |
|---|---:|---:|---|
| Critical | TC33, TC34, TC37, TC38 | 4 | Có thể làm mất khả năng xem tài liệu, mất lịch sử thao tác, hoặc chặn luồng AI chính |
| High | TC27, TC30, TC32, TC41 | 4 | Ảnh hưởng trực tiếp đến tính đúng, trải nghiệm sửa PDF và license |
| Medium | TC28, TC31, TC36, TC39, TC40 | 5 | Sai lệch giao diện hoặc chất lượng xử lý nhưng còn workaround |
| Low | TC29, TC35 | 2 | Tối ưu trải nghiệm/quản lý file |

Kết luận kỹ thuật: dự án đã có nhiều cơ chế nền tốt như queue lưu annotation, soft reload, cache lịch sử Chat PDF, staged save và wrapper reload tài liệu. Tuy nhiên các lỗi Fail cho thấy thiếu một lớp điều phối trạng thái tập trung giữa `PDFViewerWidget`, sidebar thumbnail, PDF.js preview, annotation overlay và backend file operations. Đây là nguyên nhân gốc lặp lại ở nhiều lỗi: thao tác đã ghi dữ liệu thành công nhưng UI không reload đúng, hoặc UI đổi trạng thái nhưng backend/session không nhận đủ ngữ cảnh.

## 2. Bằng chứng kiểm thử từ Excel

TC27-TC41 là 15 testcase Fail ngày 29/06/2026, người kiểm thử Ngô Quốc Anh (AGDev). Nội dung lỗi:

| TC | Mức độ | Lỗi | Kết quả thực tế |
|---|---|---|---|
| TC27 | High | Thiếu nút xóa annotation bôi vẽ | Không có nút/tùy chọn xóa trực quan cho tô sáng/gạch dưới/gạch ngang |
| TC28 | Medium | Highlight Ctrl+F không được clear | Màu highlight vẫn còn sau khi đóng/xóa ô tìm kiếm |
| TC29 | Low | Hover ghi chú không rõ vùng áp dụng | Không có viền/tô sáng khi rê chuột vào ghi chú |
| TC30 | High | Sửa text gốc chập chờn | Click sửa nhiều vùng text không nhất quán |
| TC31 | Medium | Preview chèn chữ sai font/italic | Text mới bị italic mặc định, đổi font không tác dụng ngay |
| TC32 | High | Undo nhiều nét vẽ lag/không cập nhật | Data đã xóa nhưng màn hình còn hiển thị nét cũ |
| TC33 | Critical | Thumbnail biến mất sau đặt mật khẩu | Sidebar thumbnail mất sau khi mã hóa PDF |
| TC34 | Critical | Màn hình đen sau xóa mật khẩu | PDF không reload đúng sau khi giải mã |
| TC35 | Low | Xuất nhiều ảnh không đóng gói | Ảnh rải rác trong thư mục đích |
| TC36 | Medium | OCR kém với font phức tạp | Nhận diện sai/lỗi font trên tài liệu scan/font lạ |
| TC37 | Critical | Tắt luôn nổi làm mất lịch sử Chat PDF | Nút đóng đơ và lịch sử chat bị xóa |
| TC38 | Critical | Tóm tắt file scan không tự OCR | Báo không có văn bản thay vì chạy OCR ngầm |
| TC39 | Medium | In chế độ 2 trang không chuyển đúng | Bấm trang sau trong preview 2 trang không dịch chuyển |
| TC40 | Medium | Preview in ngang không đổi hình | Chọn Landscape nhưng preview không phản ánh tỷ lệ ngang |
| TC41 | High | Sai ngày kích hoạt license sau cài lại | Ngày kích hoạt/hạn dùng lệch so với lịch sử key |

## 3. Phân tích nguyên nhân gốc theo kiến trúc

### 3.1. Lớp UI PDF.js và Python backend chưa có contract trạng thái rõ ràng

Các module như `app/pdf_viewer.py`, `app/window.py`, `app/actions/annotate.py`, `app/actions/document_ops.py` tương tác với PDF.js qua JavaScript injection, QWebChannel và reload mềm. Cách này linh hoạt nhưng dễ phát sinh lỗi khi thiếu một contract chung: thao tác nào thay đổi file vật lý, thao tác nào chỉ thay đổi overlay, thao tác nào cần invalidate cache, thao tác nào cần reload sidebar.

Ví dụ:

- `app/actions/annotate.py:313` đã có `_schedule_annotation_undo_flush()` để batch undo, nhưng TC32 cho thấy refresh visible layer vẫn chưa đủ ổn định khi người dùng undo liên tiếp.
- `app/actions/document_ops.py` đặt/xóa mật khẩu dùng `replace_document_with_staged(...)`, nhưng TC33-TC34 cho thấy sau thao tác bảo mật cần đảm bảo viewer, thumbnail sidebar, annotation sidebar và local server cache cùng nhận path mới.
- `app/window.py:1329` `_set_page()` chỉ set `currentPageNumber`; TC39 cho thấy chế độ facing/spread cần logic bước nhảy 2 trang.

### 3.2. Dữ liệu PDF gốc khó sửa trực tiếp, cần pipeline nhận diện span ổn định hơn

Sửa text gốc không giống chèn text mới. Code hiện có `_find_pdf_span(...)` và logic edit existing ở `app/actions/edit.py:2473`, sau đó tạo operation redact + insert. Cách này phụ thuộc vào bounding box, baseline, font family và việc map tọa độ PDF.js sang PDF point. Chỉ cần sai lệch nhỏ về span box, rotation hoặc font fallback là click sửa sẽ lúc được lúc không.

### 3.3. OCR/AI đang tách rời thay vì có fallback chain thống nhất

`packages/ai/summarize.py:77` chỉ đọc text bằng `pdfplumber` và nếu không có text thì trả lỗi tại `packages/ai/summarize.py:92`. Trong khi đó `packages/ai/chat_pdf.py` đã có cache OCR qua `load_ocr_text_cache(...)`, còn `packages/ocr/engine.py` có OCR Tesseract. Điều này tạo ra hành vi không đồng nhất: Chat PDF có thể tận dụng OCR cache, nhưng Summarize PDF scan lại fail.

### 3.4. License server cấp ngày theo lần activate thay vì mốc kích hoạt gốc

`vps_license_service.py:92-99` tạo payload mới với `issued_at = now` và `expires_at = now + duration` mỗi lần activate. Nếu người dùng cài lại app hoặc fingerprint thay đổi, mốc thời gian bị reset/lệch. Đây là nguyên nhân trực tiếp của TC41.

### 3.5. Rủi ro bảo mật hạ tầng cần xử lý song song với lỗi chức năng

Báo cáo bảo mật cũ nêu đúng nhóm rủi ro nghiêm trọng: credential deploy hardcode, file mật khẩu cục bộ, `AutoAddPolicy()`, admin config chứa password hash. Kiểm tra nhanh mã nguồn xác nhận còn dấu hiệu như `paramiko.AutoAddPolicy()` trong `deploy_final.py`, `sftp_deploy.py`, `check_vps.py`, và `admin-config-update.json` chứa `password_hash`. Không nên tiếp tục build/release thương mại trước khi rotate credential và đưa secrets ra khỏi repo.

## 4. Phân tích chi tiết 15 testcase Fail và đề xuất sửa

### TC33 - Thumbnail biến mất sau khi đặt mật khẩu PDF

Mức độ: Critical  
Module liên quan: `app/actions/document_ops.py`, `app/actions/_pdf_save.py`, `app/sidebar.py`, `app/window.py`

Nguyên nhân khả dĩ:

- Sau khi `set_pdf_password()` save staged file và gọi `replace_document_with_staged(...)`, PDF.js có thể reload file mới nhưng `ThumbnailSidebar` chưa chắc được re-bind path hoặc reset `_loaded_pages`.
- Sidebar thumbnail dùng lazy loading và token nội bộ. Nếu path/cache không đổi đúng thời điểm, các thumbnail cũ bị clear nhưng job mới không được kích hoạt.
- Tài liệu mã hóa sau save cần reopen theo trạng thái mới; nếu viewer còn giữ stream cũ hoặc local server cache chưa invalidate, sidebar dễ rơi vào trạng thái rỗng.

Đề xuất sửa:

- Bổ sung hàm hậu xử lý chung sau mọi thao tác thay file: `refresh_document_surfaces(window, path, page, invalidate_cache=True)`.
- Hàm này phải gọi theo thứ tự: invalidate PDF cache, `viewer.load_pdf(...)`, `sidebar.load_thumbnails(...)`, `sidebar.highlight_page(...)`, `annotation_sidebar.load_annotations(...)`.
- Với đặt mật khẩu, sau khi lưu thành công nên hiển thị thông báo rõ: file đã mã hóa, nếu cần xem tiếp không cần nhập lại trong phiên hiện tại nhưng viewer phải dùng path đã thay thế.

Tiêu chí nghiệm thu:

- Sau khi đặt mật khẩu, sidebar vẫn còn đủ số trang.
- Click thumbnail chuyển đúng trang.
- Đóng/mở lại file yêu cầu password như kỳ vọng.

### TC34 - Màn hình PDF đen sau khi xóa mật khẩu

Mức độ: Critical  
Module liên quan: `app/actions/document_ops.py`, `app/actions/_pdf_save.py`, `app/local_server.py`

Nguyên nhân khả dĩ:

- Luồng `remove_pdf_password()` mở file bằng password, save file không mã hóa rồi gọi reload. Nếu PDF.js vẫn trỏ tới stream/cache cũ hoặc path tạm bị xóa quá sớm, canvas có thể render đen.
- Việc thay file đang mở trên Windows dễ gặp lock/chậm flush. Nếu reload xảy ra trước khi file mới thật sự ổn định, PDF.js nhận nội dung lỗi.
- `display_path`, `temp_path`, `source_path` chưa được chuẩn hóa sau khi giải mã.

Đề xuất sửa:

- Sau `replace_document_with_staged(...)`, trì hoãn reload bằng `QTimer.singleShot(100-200ms)` và kiểm tra file tồn tại, size > 0, mở được bằng `pikepdf.open(path)`.
- Invalidate local server cache trước khi PDF.js load lại.
- Không xóa staged/temp path cho tới khi viewer báo `document_loaded`.
- Nếu PDF.js báo lỗi, fallback về `viewer.load_pdf(path, zoom="100", page=current_page)` thay vì soft reload.

Tiêu chí nghiệm thu:

- Xóa password xong PDF hiển thị bình thường ngay, không cần đóng/mở lại.
- Thumbnail, số trang và page hiện tại được giữ.
- Không còn màn hình đen ở file nhiều trang và file có ảnh scan.

### TC37 - Tắt luôn nổi làm mất lịch sử và treo nút Chat PDF

Mức độ: Critical  
Module liên quan: `app/ai_chat_dialog.py`, `packages/ai/chat_pdf.py`

Bằng chứng code:

- `app/ai_chat_dialog.py:207-218` đổi `WindowStaysOnTopHint` bằng `setWindowFlags(flags)`, sau đó show/raise lại dialog.
- `packages/ai/chat_pdf.py` đã có `_save_history()` và `_load_history()`, tức lịch sử đã có nền lưu trữ.

Nguyên nhân khả dĩ:

- Trên Qt, `setWindowFlags()` có thể recreate native window. Nếu event close/hide hoặc rebuild UI xảy ra sai thứ tự, dialog có thể mất focus, nút close không nhận event hoặc state UI bị reset.
- Lịch sử backend có lưu nhưng UI có thể bị clear/rebuild không đúng session identity.
- `closeEvent()` đang ignore và hide. Khi kết hợp với đổi flags, event lifecycle dễ xung đột.

Đề xuất sửa:

- Thay đổi “luôn nổi” theo cách không phá hủy state: lưu geometry, scroll, input text, session id trước khi set flags; sau show thì gọi `_rebuild_chat()` từ session hiện tại.
- Không tạo `PDFChatSession` mới khi chỉ đổi flag luôn nổi.
- Tách `hide chat`, `clear history`, `change flags` thành ba action riêng. Chỉ nút “Xóa lịch sử” mới được gọi `_session.reset()`.
- Thêm test thủ công: bật luôn nổi, gửi câu hỏi, tắt luôn nổi, đóng/mở lại panel, kiểm tra lịch sử vẫn còn.

Tiêu chí nghiệm thu:

- Tắt/bật luôn nổi không xóa QTextEdit.
- Nút đóng panel hoạt động sau mọi lần toggle.
- Lịch sử vẫn còn sau khi đóng/mở dialog cùng PDF.

### TC38 - Không tự OCR trước khi tóm tắt PDF scan

Mức độ: Critical  
Module liên quan: `packages/ai/summarize.py`, `packages/ocr/engine.py`, `app/ocr_dialog.py`, `packages/ai/chat_pdf.py`

Bằng chứng code:

- `packages/ai/summarize.py:77-100` chỉ dùng `pdfplumber.extract_text()`.
- Nếu `parts` rỗng, code trả lỗi “Tài liệu không có văn bản” tại dòng 92-93.
- `packages/ocr/engine.py:225-239` đã có hàm render page và OCR bằng Tesseract.

Nguyên nhân gốc:

- Summarize chưa có fallback OCR.
- OCR cache đã tồn tại ở Chat PDF nhưng chưa được tái sử dụng cho Summarize.

Đề xuất sửa:

- Tạo hàm chung `extract_pdf_text_with_ocr_fallback(pdf_path, max_pages, min_chars=50, allow_ocr=True)`.
- Thứ tự xử lý: pdfplumber -> pypdfium textpage -> OCR cache -> OCR trực tiếp các trang đầu -> save OCR cache.
- UI cần thông báo: “PDF dạng scan, đang OCR trước khi tóm tắt...” và chạy trong worker thread để không treo UI.
- Cho phép cấu hình OCR tự động hoặc hỏi người dùng nếu file dài.

Tiêu chí nghiệm thu:

- PDF scan 1-5 trang tóm tắt được mà không cần chạy OCR thủ công.
- Nếu thiếu Tesseract/vie.traineddata, dialog báo rõ thiếu thành phần nào.
- Không block main thread khi OCR.

### TC27 - Thiếu nút xóa annotation bôi vẽ

Mức độ: High  
Module liên quan: `app/actions/annotate.py`, `app/webchannel.py`, PDF.js annotation/overlay layer

Hiện trạng:

- Code có undo stack và `_remove_overlay_mark(...)`, nhưng testcase yêu cầu xóa trực tiếp một nét đã chọn, không phải chỉ undo nét cuối.
- Sticky note có logic xóa theo context menu, nhưng highlight/underline/strikeout chưa có UX tương đương.

Đề xuất sửa:

- Mỗi mark overlay cần lưu `mark_id`, `annot_ids`, page và rect vào DOM dataset.
- Khi click/hover mark, hiện mini toolbar cạnh vùng chọn: `Xóa`, `Đổi màu`, `Chi tiết`.
- Thêm bridge slot Python `deleteTextMark(mark_id)` hoặc `deleteAnnotationById(annot_id)`.
- Backend xóa cả overlay trong memory và annotation vật lý trong PDF bằng `/NM`.
- Sau khi xóa, push operation vào undo stack để có thể khôi phục.

Tiêu chí nghiệm thu:

- Click highlight hiện nút thùng rác.
- Xóa đúng một mark, không xóa nhầm mark khác cùng trang.
- Lưu file, đóng mở lại vẫn không còn annotation đã xóa.

### TC30 - Sửa text gốc chập chờn

Mức độ: High  
Module liên quan: `app/actions/edit.py`, `packages/pdf_engine/pymupdf_engine.py`, PDF.js coordinate bridge

Bằng chứng code:

- Edit existing text dùng `_find_pdf_span(...)` tại `app/actions/edit.py:2473`.
- Operation kết quả là redact vùng cũ và insert text mới tại `app/actions/edit.py:2500-2515`.

Nguyên nhân khả dĩ:

- Hit-test span theo bounding box quá chặt hoặc chưa xét tolerance theo zoom/rotation.
- PDF có ligature, font embedded, text split thành nhiều span nhỏ, hoặc baseline không trùng vùng click.
- `font_family` fallback không nhất quán giữa preview và ghi file thật.

Đề xuất sửa:

- Xây text index theo page trước khi edit: word/span/line với tolerance y, baseline và rotation.
- Khi click, chọn span theo điểm gần nhất trong bán kính tolerance thay vì chỉ intersect box.
- Với line có nhiều span liền nhau, cho phép sửa theo word hoặc line tùy mode.
- Log debug có cấu trúc: page, click point, matched span, distance, font, baseline, redact box.
- Thêm bộ test PDF mẫu: text đơn giản, text nhiều cột, font embedded, tiếng Việt, rotated page, scan không text.

Tiêu chí nghiệm thu:

- Click cùng một vùng text 10 lần nhận cùng một span.
- Không sửa nhầm dòng phía trên/dưới.
- Text tiếng Việt sau sửa không lỗi dấu.

### TC32 - Undo nhiều nét vẽ lag và không cập nhật màn hình

Mức độ: High  
Module liên quan: `app/actions/annotate.py`, `app/local_server.py`, `app/pdf_viewer.py`

Bằng chứng code:

- Đã có `_schedule_annotation_undo_flush(window, target_path, delay_ms=320)` tại `app/actions/annotate.py:313`.
- `undo_last_annotation()` gọi `_schedule_annotation_undo_flush(...)` tại `app/actions/annotate.py:1440` và `1467`.

Đánh giá:

- Lỗi không phải thiếu debounce hoàn toàn, mà debounce/refresh hiện tại chưa đủ để đồng bộ overlay với PDF reload khi undo liên tiếp.
- Có khả năng overlay DOM vẫn giữ mark đã xóa trong lúc file đã được cập nhật.

Đề xuất sửa:

- Tách undo thành 2 pha: cập nhật overlay ngay lập tức, save PDF chạy nền/batch sau.
- Không reload toàn PDF cho từng undo; chỉ reload khi batch flush xong hoặc khi user rời trang/save.
- Dùng revision id cho overlay state. Khi reload PDF.js, chỉ render overlay nếu revision hiện tại còn active.
- Nếu queue đang flush, disable tạm nút undo hoặc gom nhiều undo vào một transaction.

Tiêu chí nghiệm thu:

- Undo 20 nét liên tiếp không treo UI.
- Nét biến mất ngay khi bấm undo.
- Sau save/reopen, trạng thái đúng như màn hình.

### TC41 - Sai lệch ngày kích hoạt license khi cài lại

Mức độ: High  
Module liên quan: `vps_license_service.py`, `main_api.py`, `packages/license_client/*`

Bằng chứng code:

- `vps_license_service.py:92-99` tạo `issued_at` và `expires_at` mới theo thời điểm activate hiện tại.
- `_find_reusable_device_id(...)` có logic tái sử dụng theo machine name/platform, nhưng payload vẫn bị ghi lại bằng mốc thời gian mới.

Nguyên nhân gốc:

- Model license chưa có `first_activated_at` ở cấp license key hoặc cấp device identity bền vững.
- `expires_at` đang phụ thuộc lần activate mới thay vì mốc gốc.

Đề xuất sửa:

- Mở rộng `LicenseRecord`: thêm `first_activated_at`, `term_started_at`, `term_expires_at`.
- Khi activate lần đầu: set các mốc này.
- Khi activate lại cùng key/device: giữ nguyên `first_activated_at` và `term_expires_at`; chỉ update `last_seen_at`, `app_version`, `machine_name`.
- Nếu cần gia hạn, tạo endpoint admin riêng `renew_license()` thay vì implicitly reset khi activate.
- Migration dữ liệu cũ: nếu record chưa có `first_activated_at`, lấy min của các `active_devices[*].issued_at`.

Tiêu chí nghiệm thu:

- Cài lại app và active key cũ không làm đổi ngày kích hoạt gốc.
- Hạn dùng không tăng ngoài ý muốn.
- Admin dashboard hiển thị rõ ngày kích hoạt gốc và lần active gần nhất.

### TC28 - Highlight Ctrl+F không clear khi đóng thanh tìm kiếm

Mức độ: Medium  
Module liên quan: `app/search_panel.py`, `app/actions/document.py`, PDF.js findController

Bằng chứng code:

- `hide_search_panel(window)` tại `app/search_panel.py:94-95` chỉ gọi `window.search_panel.hide()`.
- Không thấy thao tác clear query/find highlight khi đóng panel.

Đề xuất sửa:

- Khi đóng search panel hoặc search input rỗng, gọi JS reset find controller:
  - Clear `window.search_query`.
  - Dispatch `find` với query rỗng hoặc gọi command PDF.js tương ứng.
  - Remove class highlight nếu PDF.js không tự clear.
- Gắn phím Esc cùng behavior với nút đóng.

Tiêu chí nghiệm thu:

- Đóng search panel làm mất highlight tạm.
- Annotation highlight thật không bị xóa nhầm.
- Mở lại search panel không tự highlight query cũ nếu user đã clear.

### TC31 - Preview chèn chữ sai font và italic mặc định

Mức độ: Medium  
Module liên quan: `app/pdf_inline_editor.py`, `assets/js/inline_text_bridge.js`

Bằng chứng code:

- Panel có `font_changed` signal và getter italic/font tại `app/pdf_inline_editor.py:300-320`.
- JS overlay tạo textarea với CSS mặc định `font-family:Arial,sans-serif;font-size:14px` trong `assets/js/inline_text_bridge.js`.

Nguyên nhân khả dĩ:

- State font trên panel chưa được push vào textarea ngay khi tạo overlay.
- Font combo thay đổi nhưng JS preview không cập nhật hoặc mapping font family không hợp lệ.
- Italic default có thể đến từ CSS kế thừa hoặc state panel chưa reset.

Đề xuất sửa:

- Khởi tạo explicit style: `fontStyle = 'normal'`, `fontWeight = '400'`, `fontFamily = selectedFont`.
- Khi panel emit `font_changed`, JS phải cập nhật textarea đang active ngay lập tức.
- Khi bắt đầu tool mới, reset state panel về normal nếu không phải edit existing text.
- Test với Arial, Times New Roman, font tiếng Việt và italic on/off.

Tiêu chí nghiệm thu:

- Text preview ban đầu không italic.
- Đổi font thấy thay đổi ngay trong overlay.
- Kết quả sau commit giống preview.

### TC36 - OCR kém với font phức tạp

Mức độ: Medium  
Module liên quan: `packages/ocr/engine.py`, `app/ocr_dialog.py`

Bằng chứng code:

- `ocr_pil_image(...)` chỉ scale ảnh khi high_quality, chưa có grayscale/threshold/deskew tại `packages/ocr/engine.py:210-217`.
- `ocr_pdf_page(...)` truyền `high_quality=False` vào `ocr_pil_image(...)` dù hàm nhận tham số high_quality tại `packages/ocr/engine.py:239`.

Đề xuất sửa:

- Sửa `ocr_pdf_page()` để truyền đúng `high_quality=high_quality`.
- Thêm preprocessing pipeline: grayscale, autocontrast, denoise nhẹ, adaptive threshold, deskew nếu phát hiện nghiêng.
- Cho phép chọn PSM theo loại tài liệu: `6` cho block văn bản, `3` cho trang đầy đủ, `11` cho sparse text.
- Cài và kiểm tra `vie.traineddata` bản chất lượng tốt.

Tiêu chí nghiệm thu:

- OCR font tiếng Việt phức tạp tăng word count và giảm ký tự lỗi.
- Không làm giảm chất lượng OCR tài liệu văn bản thông thường.

### TC39 - Không chuyển trang khi in ở chế độ hiển thị 2 trang

Mức độ: Medium  
Module liên quan: `app/window.py`

Bằng chứng code:

- Preview có mode `facing` tại `app/window.py:1386-1389`.
- Nút Next luôn gọi `_set_page(page_spin.value() + 1)` tại `app/window.py:1443`.

Nguyên nhân:

- Ở spread/facing mode, một lần chuyển cần nhảy 2 trang để sang cặp kế tiếp.

Đề xuất sửa:

- Lưu `preview_mode` hiện tại trong closure.
- Nếu mode là `facing`, nút Next tăng 2 và Prev giảm 2.
- Cập nhật page spin theo trang trái của cặp đang xem.

Tiêu chí nghiệm thu:

- Chế độ một trang: Next tăng 1.
- Chế độ hai trang: Next chuyển từ 1-2 sang 3-4, Prev ngược lại.
- Trang cuối lẻ không vượt quá tổng số trang.

### TC40 - Preview in ngang không đổi hiển thị

Mức độ: Medium  
Module liên quan: `app/window.py`, `QPrinter`, PDF.js preview

Bằng chứng code:

- `_set_orientation(...)` tại `app/window.py:1427-1431` chỉ set orientation trên `printer_holder`.
- Preview PDF.js không nhận thay đổi tỷ lệ/rotation tương ứng.

Nguyên nhân:

- Orientation là cấu hình máy in, không tự làm PDF.js canvas đổi aspect ratio.

Đề xuất sửa:

- Khi chọn Landscape/Portrait, cập nhật trạng thái preview UI và render khung giấy giả lập với aspect ratio tương ứng.
- Nếu dùng PDF.js làm preview, cần thêm overlay page container mô phỏng giấy in hoặc reload preview bằng render server-side theo printer page layout.
- Nút Landscape phải check state và trigger `_fit_page()` lại để người dùng thấy thay đổi.

Tiêu chí nghiệm thu:

- Click Ngang làm preview đổi sang khung ngang ngay.
- Click Dọc đổi lại khung dọc.
- Kết quả in thật phù hợp preview.

### TC29 - Thiếu dấu hiệu hover vùng ghi chú

Mức độ: Low  
Module liên quan: `app/actions/annotate.py`, PDF.js overlay layer

Nguyên nhân:

- Sticky note có icon/nội dung nhưng thiếu visual link giữa icon và vùng text/page được note.

Đề xuất sửa:

- Khi hover note icon, vẽ rectangle/highlight vùng `/Rect` hoặc vùng selection gốc nếu có.
- Dùng CSS transition nhẹ, border màu vàng/cam, z-index cao nhưng không che text.
- Với note không có vùng chọn, highlight chính icon và hiển thị tooltip nội dung rút gọn.

Tiêu chí nghiệm thu:

- Hover note thấy ngay vùng liên quan.
- Không làm thay đổi file PDF.

### TC35 - Tự đóng gói ZIP khi xuất nhiều trang ảnh

Mức độ: Low  
Module liên quan: `app/actions/document_ops.py`

Bằng chứng code:

- `export_pages_to_images(...)` đang loop từng trang và `pil_img.save(out_path)` vào thư mục đích.

Đề xuất sửa:

- Nếu `len(page_list) > 1`, tạo thư mục con hoặc file zip `ten_file_images.zip`.
- Khuyến nghị UX: cho người dùng chọn “Thư mục” hoặc “ZIP”; mặc định ZIP nếu xuất nhiều trang.
- Dùng `zipfile.ZipFile` và ghi ảnh vào zip, tránh rải file.

Tiêu chí nghiệm thu:

- Xuất 1 trang vẫn ra 1 ảnh.
- Xuất nhiều trang tạo 1 zip hoặc 1 thư mục con có tên rõ ràng.

## 5. Đánh giá bảo mật và hạ tầng cần xử lý trước release

### SEC-01 - Credential deploy bị hardcode

Mức độ: Critical  
Vị trí: các script deploy/check VPS

Rủi ro:

- Mật khẩu SSH/plaintext đã xuất hiện trong nhiều script.
- Nếu repo từng được chia sẻ hoặc push remote, credential phải xem như đã lộ.

Phương án:

- Rotate ngay mật khẩu VPS và mọi token liên quan.
- Chuyển deploy sang SSH key pair có passphrase.
- Không dùng password trong script. Dùng secret manager, biến môi trường hoặc CI secret.
- Xóa secret khỏi lịch sử Git bằng quy trình có kiểm soát.

### SEC-02 - `AutoAddPolicy()` và bỏ qua xác thực host key

Mức độ: High  
Vị trí: `check_vps.py`, `sftp_deploy.py`, `deploy_final.py`

Rủi ro:

- Dễ bị man-in-the-middle khi deploy.

Phương án:

- Pin host key bằng `known_hosts`.
- Dùng `RejectPolicy`.
- Ghi rõ fingerprint hợp lệ trong tài liệu vận hành.

### SEC-03 - Admin password hash nằm trong repo

Mức độ: High  
Vị trí: `admin-config-update.json`

Rủi ro:

- Hash có thể bị brute-force offline.

Phương án:

- Thêm `admin-config-update.json` vào `.gitignore`.
- Rotate mật khẩu admin.
- Chỉ commit file mẫu `admin-config.example.json`.

## 6. Lộ trình sửa lỗi khuyến nghị

### Giai đoạn 1 - Chặn lỗi Critical trong 1-2 ngày

1. Sửa TC33 và TC34 bằng cơ chế reload/sync surfaces sau thao tác mật khẩu.
2. Sửa TC38 bằng OCR fallback cho Summarize.
3. Sửa TC37 để toggle “luôn nổi” không recreate session hoặc clear UI.
4. Rotate credential hạ tầng và đưa secret ra khỏi repo.

### Giai đoạn 2 - Ổn định chức năng lõi trong 2-4 ngày

1. Sửa TC41 bằng `first_activated_at`/`term_expires_at`.
2. Sửa TC32 bằng overlay-first undo và batch save.
3. Sửa TC27 bằng delete selected annotation.
4. Sửa TC30 bằng text span index và tolerance hit-test.

### Giai đoạn 3 - Hoàn thiện UX và chất lượng trong 2-3 ngày

1. Sửa TC28 clear search highlight.
2. Sửa TC31 font/italic preview.
3. Sửa TC36 OCR preprocessing.
4. Sửa TC39-TC40 preview in.
5. Sửa TC29 hover note và TC35 zip export.

## 7. Ma trận test hồi quy sau sửa

| Nhóm | Test bắt buộc |
|---|---|
| Password/file state | Đặt mật khẩu, xóa mật khẩu, nén PDF, lưu, đóng/mở lại, kiểm tra thumbnail |
| Annotation | Tô sáng/gạch dưới/gạch ngang, xóa từng annotation, undo liên tiếp 20 lần, reopen kiểm tra |
| Search | Ctrl+F, tìm text, đóng panel, Esc, mở lại, đảm bảo highlight tạm biến mất |
| Edit text | Sửa text gốc nhiều font, nhiều dòng, tiếng Việt, PDF rotated, PDF scan |
| OCR/AI | Tóm tắt PDF text thường, PDF scan, thiếu Tesseract, thiếu `vie.traineddata` |
| Chat PDF | Chat, bật/tắt luôn nổi, đóng/mở panel, đổi PDF, clear history có chủ đích |
| Print | Preview single/facing, next/prev, portrait/landscape, in thật 1-2 trang |
| License | Active lần đầu, cài lại app, active lại cùng key, kiểm tra ngày gốc và hạn dùng |
| Security | Scan secret, kiểm tra `.gitignore`, xác thực SSH host key, deploy dry-run |

## 8. Kết luận

15 testcase Fail hiện tại không phải các lỗi rời rạc. Chúng phản ánh một vấn đề kiến trúc chung: thiếu bộ điều phối trạng thái tài liệu sau mỗi thao tác làm thay đổi file PDF hoặc overlay PDF.js. Nên ưu tiên xây một helper reload/sync surfaces dùng chung, sau đó xử lý từng lỗi UI cụ thể.

Mức ưu tiên cao nhất là TC33, TC34, TC37, TC38 và rotate credential hạ tầng. Sau khi các lỗi này được chặn, dự án mới nên tiếp tục sửa các lỗi High còn lại và chạy regression toàn bộ TC01-TC41 trước khi đóng bản release.
