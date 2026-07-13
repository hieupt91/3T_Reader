# Phân tích lỗi TC37, TC42-TC53

Ngày lập: 11/07/2026

Căn cứ: đã đọc `QUY_TRINH_SUA_LOI.md`. Theo quy trình, bước này chưa sửa code; tài liệu này chỉ khoanh vùng vấn đề, nêu root cause có căn cứ, hướng xử lý tối thiểu và test cần có.

## Tóm tắt kết luận

Những lỗi cần xử lý thật sự:

- TC37: Chat PDF bật/tắt “luôn nổi” làm mất lịch sử và nút đóng bị đơ.
- TC42: Chế độ đánh dấu đang đánh dấu toàn bộ từ trùng lặp thay vì chỉ đúng vùng người dùng kéo chọn.
- TC43: Icon `Xóa trắng` bị dẹt.
- TC44: Tooltip không đổi ngôn ngữ khi đổi hệ thống.
- TC45: Xóa highlight trên trang xong, reload lại thì highlight xuất hiện lại.
- TC46: Ghi chú hover highlight theo chữ trùng lặp thay vì đúng vị trí thực tế.
- TC51: Chat PDF không hiển thị tin nhắn đầu tiên / trôi lịch sử / UI chat chưa giữ history đúng.

Những TC đang ghi `Pass` trong danh sách cần giữ regression test:

- TC47, TC48, TC49, TC50, TC52, TC53.

## TC37 - Tóm tắt nhanh lỗi và hướng fix

### Lỗi đang gặp

Chat PDF bị lỗi sau chuỗi thao tác:

1. Vào Chat PDF.
2. Bật chế độ `Luôn nổi`.
3. Tắt chế độ `Luôn nổi`.
4. Thử đóng/tắt chat.

Kết quả fail:

- nút đóng/tắt chat bị đơ;
- nội dung chat của phiên đó bị xóa hoặc render lại thành trống;
- lịch sử hội thoại không được giữ đúng như kỳ vọng.

### Vùng code nghi ngờ chính

- `app/ai_chat_dialog.py`
  - `_set_stays_on_top()`
  - `closeEvent()`
  - `set_pdf()`
  - `_rebuild_chat()`
- `app/actions/ai_actions.py`
  - `open_chat_dialog()`
- `packages/ai/chat_pdf.py`
  - `PDFChatSession`
  - `_save_history()`
  - `_load_history()`
- `tests/test_ai_chat_dialog_tc37.py`

### Root cause hiện tại

Fix hiện tại chưa đủ chắc vì `tests/test_ai_chat_dialog_tc37.py` chỉ kiểm tra chuỗi trong source, ví dụ có dòng `chat_html = self._chat_area.toHtml()`. Test này không mô phỏng QDialog thật nên có thể `Pass` trong pytest nhưng vẫn fail ngoài app.

Điểm nghi ngờ chính:

- `setWindowFlags()` trong `_set_stays_on_top()` có thể recreate native window của Qt, làm UI state/focus/close button thay đổi.
- `open_chat_dialog()` khi dialog đã tồn tại vẫn có thể gọi `existing.set_pdf(...)`; nếu identity/path bị xem là khác thì `set_pdf()` clear UI và `_rebuild_chat()`.
- Lịch sử thật nằm ở `_session.history`, còn `_set_stays_on_top()` đang restore HTML tạm bằng `setHtml(chat_html)`. Nếu session bị tạo lại hoặc UI rebuild sau đó, nội dung vẫn có thể mất.

### Hướng fix đúng

1. Thay test source-string bằng test hành vi thật:
   - tạo `AIChatDialog`;
   - nạp sẵn history;
   - bật `_set_stays_on_top(True)`;
   - tắt `_set_stays_on_top(False)`;
   - gọi close/hide;
   - assert chat vẫn còn nội dung và dialog không bị đơ.
2. Sửa `_set_stays_on_top()` để chỉ đổi window flag, không rebuild chat, không tạo session mới, không làm mất `_session.history`.
3. Sửa `open_chat_dialog()` để nếu dialog đang mở cùng file/cùng `history_identity_path` thì chỉ `show()/raise_()/activateWindow()`, không gọi `set_pdf()` lại.
4. Sửa `set_pdf()` để nếu cùng identity thì return sớm, tuyệt đối không clear `_chat_area`.
5. Đảm bảo `closeEvent()` chỉ `hide()` và `accept()`, không reset session, không clear history.

### Test cần có cho TC37

- Test toggle `Luôn nổi` giữ nguyên nội dung chat.
- Test đóng dialog sau toggle không bị kẹt.
- Test mở lại Chat PDF cùng file không gọi `set_pdf()` làm clear lịch sử.
- Test session history trong `packages/ai/chat_pdf.py` vẫn còn sau khi sửa/chú thích PDF làm đổi mtime file.

## Nguyên tắc cần bám khi fix

- Mỗi TC phải có test riêng, không gom thành một diff lớn.
- Không sửa chung hàm search nếu lỗi chỉ nằm ở luồng selection.
- Không xóa/refactor lan man trong `annotate.py`, vì file này đang gom nhiều luồng: highlight, underline, strikeout, note, undo, rotate/delete page.
- Sau mỗi fix: `py_compile` file sửa và chạy pytest liên quan.
- Chưa commit cho đến khi user test/xác nhận.

## Vùng code liên quan

### Annotation / highlight / note

- `app/actions/annotate.py`
- Các hàm chính:
  - `_get_selection_payload_sync`
  - `_fallback_selection_payload_from_text`
  - `_selection_page_rects`
  - `_do_selected_text_mark`
  - `_mark_keyword_from_selection`
  - `_mark_keyword_everywhere`
  - `add_comment`
  - `_notes_for_js`
  - `_merge_overlay_notes`
  - `_marks_from_pdf`
  - `_delete_annotations_by_prefix`
  - `_delete_annotations_by_content`
  - `deleteMark`
  - `deleteMarksOnPage`
  - `enable_note_tools`

### Ribbon / icon / tooltip / language

- `app/window.py`
- `app/ribbon_bar.py`
- `app/language_manager.py`
- `assets/icons/redact.svg`

### Chat PDF

- `app/ai_chat_dialog.py`
- `app/actions/ai_actions.py`
- `packages/ai/chat_pdf.py`
- `tests/test_ai_chat_dialog_tc37.py`
- `tests/test_ai_chat_phase6_regressions.py`

## TC42 - Chế độ đánh dấu tự động tô sáng toàn bộ chữ trùng lặp

### Hiện tượng

Vào chế độ đánh dấu, kéo chọn một từ. Hệ thống tô sáng tất cả các từ trùng lặp trên trang/toàn tài liệu thay vì chỉ đúng đoạn người dùng chọn.

### Bằng chứng code

Trong `app/actions/annotate.py`:

- `highlight_text(window)` nếu `_mark_mode_is_find(window)` thì gọi `_mark_keyword_from_selection(window, "highlight")`.
- `_mark_keyword_from_selection()` lấy `selected_text`, normalize thành `keyword`, rồi gọi `_mark_keyword_everywhere()`.
- `_mark_keyword_everywhere()` quét toàn bộ document bằng `_search_text_on_page()` và tạo mark cho mọi rect tìm thấy.

Ngoài ra `_get_selection_payload_sync()` có fallback:

- nếu không lấy được rect selection từ PDF.js, nó lấy `QWebEnginePage.selectedText()`;
- sau đó `_fallback_selection_payload_from_text()` dùng `_search_text_on_page()` để tìm text trên trang hiện tại.

Fallback này có thể biến một selection cụ thể thành search theo chữ, dẫn đến tô sáng các từ trùng lặp.

### Root cause có căn cứ

Đang trộn 2 ý nghĩa của “chế độ”:

- `select`: chỉ đánh dấu đúng selection rect người dùng kéo chọn.
- `find`: đánh dấu theo keyword trên nhiều vị trí.

Khi UI đang ở trạng thái người dùng nghĩ là “chọn”, code vẫn có đường đi sang `_mark_keyword_everywhere()` nếu `_mark_mode == "find"` hoặc khi fallback search text kích hoạt.

### Hướng fix tối thiểu

1. Trong luồng toolbar “chọn”, tuyệt đối không được fallback text sang search.
2. Tách hàm đọc selection thành 2 mode:
   - `strict=True`: chỉ chấp nhận payload có rect thật từ PDF.js.
   - `strict=False`: được fallback search text cho luồng find/search riêng.
3. `_do_selected_text_mark()` phải gọi strict selection.
4. `_mark_keyword_from_selection()` mới được gọi keyword everywhere, và chỉ khi nút mode thật sự là `Tìm`.
5. Nếu strict không có rect: hiện thông báo “Hãy bôi đen lại văn bản”, không tự search.

### Test cần thêm

- Tạo PDF có 3 từ giống nhau trên cùng trang.
- Giả lập selection payload chỉ có 1 rect.
- Gọi `_do_selected_text_mark(window, "highlight")`.
- Assert chỉ 1 rect được đưa vào `_add_overlay_marks_batch`.
- Test riêng: khi `_mark_mode == "find"` thì keyword everywhere vẫn đánh dấu nhiều vị trí.

## TC43 - Icon Xóa trắng bị dẹt

### Hiện tượng

Nút `Xóa trắng` trên ribbon hiển thị icon bị bóp méo, ảnh hưởng thẩm mỹ.

### Bằng chứng code

Trong `app/window.py`:

- `self.act_redact = make("Xóa trắng", "redact.svg", ...)`
- Ribbon dùng `make_action_btn(self.act_redact, "Xóa trắng")`.

Trong `app/ribbon_bar.py`:

- `make_action_btn()` set `btn.setDefaultAction(action)`, `btn.setIconSize(QSize(icon_size, icon_size))`, nhưng không khóa kích thước button/icon frame riêng cho từng icon.
- Stylesheet `QToolButton` có `min-width: 40px; max-width: 72px; padding: 3px 6px;`.

Nếu `redact.svg` có `viewBox`, width/height hoặc padding nội bộ không cân đối, icon dễ bị render nhìn dẹt khi Qt scale vào khung nhỏ.

### Root cause cần xác minh khi fix

Có 2 khả năng:

- `assets/icons/redact.svg` có viewBox/geometry không vuông hoặc nội dung icon đang rộng/cao lệch.
- `QToolButton` text-under-icon + width giới hạn làm icon bị scale theo khung không ổn định.

### Hướng fix tối thiểu

1. Mở `assets/icons/redact.svg`, chuẩn hóa viewBox về khung vuông nếu icon file sai.
2. Nếu SVG đúng, sửa `make_action_btn()`/style theo hướng không bóp icon:
   - giữ `setIconSize(QSize(28, 28))`;
   - set `btn.setFixedWidth(...)` hoặc minimum width đủ cho label;
   - không đặt CSS làm image/icon có width/height khác tỷ lệ.
3. Chỉ tác động nút/icon `redact.svg` nếu có thể, tránh đổi toàn bộ ribbon.

### Test cần thêm

- Test đọc SVG `redact.svg` có `viewBox` vuông.
- Test source UI có `setIconSize(QSize(28, 28))` và không override tỷ lệ icon cho redact.
- Cần screenshot UI để xác nhận bằng mắt theo quy trình.

## TC44 - Tooltip không đổi ngôn ngữ

### Hiện tượng

Đổi ngôn ngữ từ Tiếng Việt sang Tiếng Anh, text nút có thể đổi nhưng tooltip vẫn giữ Tiếng Việt.

### Bằng chứng code

Trong `app/window.py`:

- Hàm `make(text, svg_file, tooltip, shortcut, slot)` tạo `QAction` và set `a.setToolTip(tooltip)` bằng chuỗi cứng.
- `_apply_language_texts()` hiện chỉ gọi `_set(...).setText(...)`, không cập nhật tooltip cho hầu hết action.
- `_ensure_action_tooltips()` chỉ set tooltip nếu action chưa có tooltip. Các action đã có tooltip Tiếng Việt sẽ không bị thay thế.
- Một số tooltip còn set trực tiếp:
  - `page_spin.setToolTip("Nhập số trang rồi Enter")`
  - `zoom_spin.setToolTip(...)`
  - `_toggle_theme()` set tooltip bằng chuỗi cứng.

### Root cause có căn cứ

Tooltip không được binding với translation key. Khi đổi ngôn ngữ, `_apply_language_texts()` chỉ render lại label, còn tooltip cũ vẫn nằm trong `QAction`.

### Hướng fix tối thiểu

1. Thêm map tooltip key riêng cho action, ví dụ `_action_tooltip_keys = { action: ("tooltip.open", fallback) }`.
2. Sửa helper `make()` để nhận `text_key`, `tooltip_key` hoặc sau khi tạo action đăng ký metadata:
   - action text key
   - tooltip key
   - fallback.
3. Trong `_apply_language_texts()`:
   - update cả `.setText(...)`
   - update cả `.setToolTip(...)`
   - update `page_spin`, `zoom_spin`, language button, theme tooltip.
4. Bỏ logic “chỉ set tooltip nếu rỗng” cho các action cần dịch; `_ensure_action_tooltips()` chỉ là fallback cho menu action không có key.
5. Bổ sung translation key vào `BUILTIN_TRANSLATIONS` cho `vi/en` trước, các ngôn ngữ khác fallback được.

### Test cần thêm

- Khởi tạo MainWindow, set language `vi`, assert tooltip là Việt.
- Gọi `_set_language("en")`, assert tooltip của `act_redact`, `act_highlight`, `act_open`, `page_spin` đã là English.
- Test `_ensure_action_tooltips()` không ghi đè tooltip đã dịch.

## TC45 - Highlight đã xóa xuất hiện lại sau reload

### Hiện tượng

Xóa highlight trên trang thành công trên UI. Sau khi dùng tính năng khác làm reload file, highlight lại hiện như chưa xóa.

### Bằng chứng code

Trong `deleteMarksOnPage()`:

- mark overlay trên page được set `_deleted = True`.
- `_flush_annotation_queue()` được gọi.
- PDF được mở bằng pikepdf, xóa annotation có `/NM` bắt đầu `3t-mark-`.
- Sau đó `_save_pikepdf_in_place()` nếu `deleted > 0`.
- Chạy JS `__3tNotesDeleteMarksOnPage(pageNumber)`.
- Gọi `compact_annotation_overlay_state(self._window)` không truyền `keep_paths`.

Trong `enable_note_tools()`:

- load `_notes_for_js(path)`;
- merge overlay notes;
- extend `_overlay_marks_for_js(window, path)`;
- tiếp tục extend `_marks_from_pdf(path)` bỏ qua ID có trong session_ids.

Rủi ro nằm ở chỗ:

- Nếu PDF annotation chưa flush xong hoặc xóa không match ID, `_marks_from_pdf(path)` sẽ đọc lại mark cũ.
- Nếu overlay tombstone bị compact mất quá sớm, `enable_note_tools()` không còn biết ID đó đã bị xóa trong session và lại đọc từ PDF/cache.
- Nếu local PDF.js/server cache chưa invalidate sau `_save_pikepdf_in_place()`, reload có thể lấy PDF cũ.

### Root cause có căn cứ

Lỗi lưu trạng thái xóa chưa đồng bộ đầy đủ giữa 3 lớp:

- overlay session;
- PDF annotation thật trong file;
- cache/render của viewer.

Việc `compact_annotation_overlay_state()` sau xóa có nguy cơ xóa tombstone quá sớm, trong khi reload sau đó lại đọc mark từ PDF/cache.

### Hướng fix tối thiểu

1. Trong `deleteMarksOnPage()` sau khi save PDF, invalidate cache PDF.js/local server như queue flush đang làm.
2. Giữ tombstone theo `path + page + mark_id` đến sau lần reload tiếp theo, không compact ngay nếu vừa xóa.
3. Nếu xóa theo page, cần lưu tombstone page-level, vì xóa nhiều mark không có list ID rõ ràng.
4. Trong `enable_note_tools()`, khi `_marks_from_pdf(path)` load lại, phải lọc bỏ:
   - mark có id đang `_deleted`;
   - mark thuộc page có page-level tombstone vừa xóa.
5. Đảm bảo heavy ops như `add_page_numbers` và `edit_existing_text` gọi `_flush_annotations_before_heavy_op()` trước khi thay file, nếu chưa thì thêm vào đúng entrypoint.

### Test cần thêm

- Tạo PDF có 2 highlight `3t-mark-*` trên trang 1.
- Gọi `deleteMarksOnPage(1)`.
- Gọi lại `_marks_from_pdf(path)` assert rỗng.
- Gọi `enable_note_tools()` sau reload giả lập assert không inject mark cũ.
- Test cache invalidation được gọi sau save xóa mark.

## TC46 - Ghi chú tự tìm từ trùng lặp để highlight

### Hiện tượng

Tạo ghi chú tại từ cụ thể, ví dụ “lời cảm ơn”. Khi hover icon ghi chú, app highlight tất cả các chữ “lời cảm ơn” trên trang thay vì đúng vị trí note gắn vào.

### Bằng chứng code

Trong `add_comment()`:

- đọc `selection_payload = _get_selection_payload_sync(window)`.
- `_get_selection_payload_sync()` có fallback text sang search qua `_fallback_selection_payload_from_text()`.
- `target_rects = _merge_rects_by_line(selection_rects)` được lưu vào overlay note.

Trong JS `_ARM_NOTE_TOOLS_JS`:

- `showNoteHoverRegion()` dùng `note.target_rects` nếu có, nếu không fallback về `[note.rect]`.

Nhưng `add_annotation()` khi ghi note vào PDF chỉ lưu:

- `/Subtype /Text`
- `/Rect`
- `/Contents`
- `/NM`

Không thấy có lưu `target_rects` vào PDF. Nghĩa là sau reload, `_notes_for_js()` chỉ đọc note rect/content, không đọc target rects.

### Root cause có căn cứ

Có 2 vấn đề:

1. Lúc tạo note, nếu selection rect không lấy được, fallback search text có thể tạo `target_rects` cho tất cả từ trùng lặp.
2. `target_rects` chỉ tồn tại trong overlay memory, không persist vào PDF annotation. Sau reload note mất target rect thật, hoặc có xu hướng suy luận lại theo text/content nếu luồng khác bổ sung sau.

### Hướng fix tối thiểu

1. Với ghi chú gắn selection: dùng strict selection rect, không fallback search text.
2. Lưu `target_rects` vào annotation PDF bằng custom key riêng, ví dụ `/3TTargetRects` hoặc `/3TTargetRectJson`.
3. `_notes_for_js()` phải đọc lại custom key này và trả về `target_rects`.
4. Nếu note cũ không có target rects:
   - hover chỉ highlight icon rect;
   - không search theo `/Contents`.
5. Không dùng nội dung ghi chú làm keyword để tìm highlight.

### Test cần thêm

- PDF có 3 cụm “lời cảm ơn”.
- Giả lập selection payload chỉ chọn cụm thứ 2.
- Tạo note.
- `_notes_for_js(path)` sau save/reload phải có `target_rects` đúng 1 cụm.
- Hover JS dùng `target_rects`, không search text.

## TC37 - Bật/tắt luôn nổi làm mất lịch sử và treo nút đóng Chat PDF

### Hiện tượng

Vào Chat PDF, bật luôn nổi, tắt luôn nổi, thử tắt chat: nút tắt bị đơ và nội dung chat bị xóa.

### Bằng chứng code

Trong `app/ai_chat_dialog.py`:

- `_set_stays_on_top()` hiện đang lưu `chat_html`, input/status/button state/scroll.
- Sau `setWindowFlags(flags)`, gọi `self._chat_area.setHtml(chat_html)`.
- `closeEvent()` accept rồi hide.

Trong `tests/test_ai_chat_dialog_tc37.py`:

- test chỉ đọc source và assert có chuỗi `chat_html = self._chat_area.toHtml()`.
- Không tạo dialog thật, không toggle flag thật, không click close thật.

Trong `app/actions/ai_actions.py`:

- `open_chat_dialog()` nếu existing dialog tồn tại thì luôn gọi `existing.set_pdf(pdf_path, history_identity_path=...)`.
- `set_pdf()` trong dialog nếu path/identity khác thì clear UI và `_rebuild_chat()`.

### Root cause có căn cứ

Fix hiện tại mới giữ HTML tạm thời quanh `setWindowFlags`, nhưng chưa kiểm chứng hành vi Qt thực tế. Có ba điểm rủi ro:

1. `setWindowFlags()` trên QDialog có thể recreate native window, làm trạng thái widget/focus/close button thay đổi.
2. `_set_stays_on_top()` dùng `setHtml(chat_html)` để restore UI tạm thời, nhưng lịch sử thật nằm trong `_session.history`; nếu session bị reset/recreate do `set_pdf()` hoặc path identity thay đổi thì UI vẫn có nguy cơ bị clear sau đó.
3. Test TC37 hiện tại là source-string test nên có thể pass trong khi UI thật vẫn fail.

### Hướng fix tối thiểu

1. Viết test hành vi bằng Qt:
   - tạo `AIChatDialog` với fake `PDFChatSession`;
   - nạp 2 tin nhắn;
   - toggle `_set_stays_on_top(True)` rồi `False`;
   - gọi `close()`/`closeEvent`;
   - assert dialog hide được, `_chat_area.toPlainText()` vẫn có tin nhắn.
2. Trong `_set_stays_on_top()`:
   - không gọi `_rebuild_chat()`;
   - không tạo session mới;
   - sau `setWindowFlags()`, restore state từ `_session.history` hoặc giữ document HTML, nhưng phải đảm bảo `_session.history` không mất.
3. Trong `open_chat_dialog()`:
   - nếu existing dialog đang cùng `history_identity_path`, không gọi `set_pdf()` vô ích.
   - nếu dialog đã bị close/hide, chỉ show lại, không reset.
4. `closeEvent()` nên chỉ hide và accept, đồng thời clear `_busy`/thread nếu cần; không reset session.

### Test cần thêm

- Thay `tests/test_ai_chat_dialog_tc37.py` source-string bằng behavior test.
- Test `open_chat_dialog()` không gọi `set_pdf()` khi path/identity không đổi.
- Test `set_pdf()` với same identity không clear chat.

## TC51 - Chat PDF không hiện tin nhắn đầu tiên và trôi lịch sử

### Hiện tượng

Tin nhắn đầu tiên của user không hiện, gửi tiếp câu thứ hai thì tin trước bị xóa/lịch sử trôi.

### Bằng chứng code

Trong `AIChatDialog._on_send()`:

- append user bubble vào UI trước;
- append thinking bubble;
- background task gọi `session.ask(question)`.

Trong `PDFChatSession.ask()`:

- `_record_user_question(question)` được gọi trước khi đọc text/ask AI.
- nếu AI fail, user question vẫn được lưu.

Trong `_replace_thinking_with()`:

- dùng `_thinking_start_pos` để xóa từ vị trí thinking đến cuối document.
- Nếu `_thinking_start_pos` tính sai do `QTextEdit.append()` thêm block/HTML, có thể xóa nhầm cả bubble user trước đó.

### Root cause có căn cứ

UI chat đang thao tác trực tiếp trên HTML của `QTextEdit` và replace bằng cursor position. Nếu position tính lệch, bong user đầu tiên có thể bị xóa khi thay thinking bubble. Đây là lỗi UI state, không phải chỉ history storage.

### Hướng fix tối thiểu

1. Bỏ cách replace từ `_thinking_start_pos` đến end nếu không test được ổn định.
2. Chuyển sang render chat từ model riêng:
   - `self._visible_messages = [...]`
   - append user/thinking/assistant vào list;
   - render lại HTML từ list khi cần.
3. Hoặc giữ QTextEdit append-only:
   - user bubble append;
   - thinking bubble append;
   - khi có kết quả thì append answer mới, không xóa thinking; sau đó có thể ẩn thinking bằng block id nếu làm được an toàn.
4. Nếu muốn Messenger UI thật, nên dùng `QScrollArea + QLabel/QFrame` message bubbles thay vì edit HTML bằng cursor.

### Test cần thêm

- Gửi câu đầu với fake AI success: assert UI có question + answer.
- Gửi câu hai: assert UI vẫn còn câu đầu.
- Fake AI fail: assert câu user vẫn hiện và vẫn lưu trong session history.

## TC47 - Không tìm thấy kết quả dù có kết quả

Trạng thái danh sách ghi là `Pass`. Cần giữ regression:

- Khi search có kết quả, không show popup “Không tìm thấy”.
- Cần test điều kiện hiện popup dựa vào tổng số match thật, không dựa vào state UI tạm thời.

## TC48 - Undo highlight tìm kiếm bị lag/lưu vết

Trạng thái danh sách ghi là `Pass`. Cần giữ regression:

- Undo nhiều highlight chồng lên nhau không để lại overlay cũ.
- Cần test `_MAX_ANNOTATION_UNDO`, compact overlay và queue flush.

## TC49 - Nút tô sáng trong thanh tìm kiếm lệch tọa độ

Trạng thái danh sách ghi là `Pass`. Cần giữ regression:

- Phần search highlight và phần draw/mark trên thanh Ctrl+F không dùng chung offset sai.
- Cần test bounding box/offset riêng nếu có JS helper.

## TC50 - Mở gần đây trống

Trạng thái danh sách ghi là `Pass`. Cần giữ regression:

- Mở file -> recent menu có path.
- File mất -> hiện thông báo rõ “không tìm thấy tài liệu tại đường dẫn”, không gây cảm giác lỗi mở gần đây.

## TC52 - Mất nút xóa và bảng đổi màu highlight cũ

Trạng thái danh sách ghi là `Pass`. Cần giữ regression:

- Click mark cũ đọc từ PDF phải hiện menu xóa/palette.
- Cần test `_marks_from_pdf()` tạo hit-area và JS `showMarkMenu()` có delete/color.

## TC53 - Xoay toàn bộ trang PDF

Trạng thái danh sách ghi là `Pass`. Cần giữ regression:

- Xoay toàn bộ trang giữ thumbnail/main view đồng bộ.
- Các thao tác reload sau xoay không làm mất annotation state.

## Thứ tự fix để giảm rủi ro

1. TC42 + TC46: cùng gốc selection strict vs fallback search. Làm trước để chặn auto highlight sai.
2. TC45: sau khi selection/note ổn định, xử lý delete persistence/cache.
3. TC37 + TC51: tách nhóm Chat PDF, sửa UI state và behavior tests.
4. TC44: sửa tooltip/language metadata.
5. TC43: sửa icon/ribbon style nhỏ.
6. Chạy lại regression TC47-TC50, TC52-TC53.

## Checklist verify sau khi fix

- `py_compile app/actions/annotate.py app/ai_chat_dialog.py app/actions/ai_actions.py app/window.py app/ribbon_bar.py app/language_manager.py`
- pytest nhóm annotation:
  - `tests/test_pr7_helpers.py`
  - `tests/test_annotation_search_line_marks.py`
  - test mới TC42/TC45/TC46
- pytest nhóm chat:
  - `tests/test_ai_chat_dialog_tc37.py`
  - `tests/test_ai_chat_phase6_regressions.py`
  - test mới TC51
- pytest nhóm UI language/icon:
  - test mới TC43/TC44
- Mở app kiểm bằng mắt:
  - selection highlight chỉ 1 vùng
  - note hover chỉ đúng vùng
  - delete highlight reload không quay lại
  - tooltip đổi sang English
  - icon `Xóa trắng` không bị dẹt
  - Chat PDF toggle luôn nổi và đóng/mở không mất lịch sử
