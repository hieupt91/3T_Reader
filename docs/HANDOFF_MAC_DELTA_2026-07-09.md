# Bàn giao team Mac — Delta từ Win sau mốc 07/07/2026

**Ngày lập:** 09/07/2026  
**Branch Win hiện tại:** `piper-vps-sync`  
**Mốc handoff gần nhất đã thấy trên git:** `2026-07-07`

## 1. Mốc bàn giao gần nhất trên git

Ba commit gần nhất thể hiện team Win đã chia sẻ cho team Mac trước đợt này:

- `4d9e641` — `2026-07-07` — bàn giao thay đổi bảo mật 07/2026 dùng chung VPS
- `fc6d5f5` — `2026-07-07` — cập nhật trạng thái port sang Mac
- `d8eb3d8` — `2026-07-07` — cập nhật handoff + patch backend đã deploy live

Tài liệu gốc:

- `docs/HANDOFF_MAC_BAO_MAT_2026-07.md`
- `docs/patches/backend-security-fixes-20260707.patch`
- `docs/patches/README.md`

Kết luận: từ mốc handoff đó đến thời điểm hiện tại, team Win đã có thêm các thay đổi ngày `2026-07-08` và `2026-07-09` mà team Mac **chưa thấy trong tài liệu bàn giao cũ**.

---

## 2. Các commit Win cần bổ sung chia sẻ cho Mac

### 2.1. Danh sách delta sau mốc 07/07

- `84a43cf` — `2026-07-08` — `fix(file): show clear missing recent document error`
- `0e2c776` — `2026-07-08` — `fix(annotate): match single-word search inside punctuated tokens`
- `46c12ef` — `2026-07-08` — `fix(pages): expose and speed up rotate pages`
- `f217522` — `2026-07-09` — `fix: address reader regression fixes`
- `8a92859` — `2026-07-09` — `fix(ai): preserve chat history and UI callbacks`

### 2.2. Phân loại mức độ áp dụng cho Mac

**Bắt buộc Mac review/port nếu đang dùng cùng luồng shared code hoặc cùng UI feature**

- Mở file gần đây bị mất file nguồn
- Tìm kiếm + tô/gạch chú thích theo từ khóa
- Chat PDF / AI dialog / worker thread / lịch sử chat
- OCR / semantic search / summarize / PDFium render-lock
- In file scan có con dấu/chữ ký widget

**Chỉ áp dụng nếu nhánh Mac có feature tương ứng**

- UI `Xoay trang...` cho 1 trang hoặc toàn bộ tài liệu
- Checkbox `Luôn nổi` trong Chat PDF
- Luồng in dựa trên PDFium render thay vì native preview riêng của macOS

**Không cần port nguyên xi nếu Mac đã có kiến trúc khác**

- Các wiring Ribbon/menu chỉ dành riêng cho cửa sổ Win
- Những file Win-only không tồn tại ở nhánh Mac

---

## 3. Chi tiết cần chia sẻ cho team Mac

## A. Mở file gần đây — báo lỗi rõ khi file nguồn đã mất

**Commit:** `84a43cf`  
**File Win:** `app/actions/file.py`

### Vấn đề
Khi user mở một mục trong danh sách "Gần đây" nhưng file gốc đã bị xóa/di chuyển, thông báo cũ khiến user hiểu nhầm là app lỗi mở file gần đây, không biết gốc là do tài liệu không còn tồn tại.

### Hành vi đúng cần thống nhất

- Nếu đường dẫn mục "Gần đây" không còn tồn tại:
  - báo rõ kiểu: `Không tìm thấy tài liệu tại đường dẫn ...`
  - không dùng thông báo chung chung kiểu "không mở được file"

### Team Mac cần làm

- Review luồng mở file gần đây bên Mac.
- Nếu Mac cũng có recent list và dùng thông báo generic, đổi sang lỗi tách bạch:
  - lỗi tài liệu không tồn tại
  - lỗi đọc/mở tài liệu thật sự

### Verify

1. Mở một file PDF.
2. Đóng app.
3. Xóa file đó ngoài Finder.
4. Vào recent list trong app Mac.
5. Chọn lại file đó.
6. App phải báo rõ là **không tìm thấy tài liệu tại đường dẫn**.

---

## B. Tìm kiếm từ khóa 1 từ phải khớp được cả từ dính dấu câu

**Commit:** `0e2c776`  
**File Win:** `app/actions/annotate.py`

### Root cause bên Win
Logic `_search_words_across_lines()` trước đây khớp nguyên token. Vì token giữ nguyên dấu câu nên query một từ như `sửa` không khớp `sửa.` trong `chỉnh sửa.`.

### Fix đã làm trên Win

- Query 1 từ:
  - khớp theo `substring`
  - tương đương hành vi `match_whole_word=False`
- Query nhiều từ:
  - giữ nguyên exact match cũ

### Team Mac cần làm

- Nếu Mac có cùng helper search annotation hoặc cùng behavior Ctrl+F + highlight thật:
  - sửa nhánh query 1 từ theo hướng substring
  - không đổi hành vi query nhiều từ

### Verify

Tạo PDF có đủ các trường hợp:

- `sửa chữ`
- `sửa số`
- `chỉnh sửa.`

Tìm `sửa`:

- trước fix chỉ thường thấy 2 match
- sau fix phải thấy đủ 3 match

---

## C. Underline / strikeout theo từ khóa tìm kiếm, không bắt user phải bôi đen

**Commit chính:** `f217522`  
**File Win:** `app/actions/annotate.py`  
**Test Win:** `tests/test_annotation_search_line_marks.py`

### Hành vi mới bên Win

- Nếu đang có search query hiện tại:
  - `Gạch dưới`
  - `Gạch ngang`
  có thể áp trực tiếp lên toàn bộ kết quả tìm kiếm mà không cần selection tay.
- Với line marks (`underline`, `strikeout`):
  - dùng rect không padding
  - tránh lệch vị trí so với text thật

### Team Mac cần làm

- Nếu Mac có annotation tools tương ứng:
  - ưu tiên search query hiện tại khi không có selection
  - line marks không dùng rect padding kiểu highlight

### Verify

1. Ctrl+F tìm từ khóa.
2. Không bôi đen text.
3. Bấm `Gạch dưới`.
4. Bấm `Gạch ngang`.
5. Kết quả tìm kiếm phải được đánh dấu đúng vị trí, không lệch và không bắt selection tay.

---

## D. Xoay trang — thêm đường vào thao tác xoay 1 trang / toàn bộ tài liệu

**Commit:** `46c12ef`  
**File Win:** `app/actions/pages.py`, `app/window.py`, `app/language_manager.py`

### Những gì Win đã thêm

- Action `Xoay trang...`
- cho phép:
  - xoay trang hiện tại
  - xoay toàn bộ tài liệu
- expose action này ra UI thay vì chỉ có xoay trái/phải trang hiện tại

### Team Mac cần làm

- Nếu Mac có page operations:
  - kiểm tra xem đã có "Rotate pages..." chưa
  - nếu chưa, bổ sung dialog thao tác tương đương
- Nếu Mac vẫn chỉ có rotate current page:
  - xác nhận có cần parity UX với Win không

### Ghi chú

- Đây là mục phụ thuộc mạnh vào UI nhánh Mac.
- Không cần copy wiring Ribbon của Win; chỉ cần thống nhất capability và hành vi.

---

## E. PDFium phải init forms trước khi render/in để không mất con dấu/chữ ký widget

**Commit chính:** `f217522`  
**File Win:** `packages/pdf_engine/pdfium_engine.py`  
**Test Win:** `tests/test_pdfium_print_forms.py`

### Vấn đề
Với PDF scan có chữ ký số/con dấu nằm trong widget appearance (`/Widget`, `/AP`), nếu render PDFium mà không `init_forms()`, preview/in có thể không hiện phần dấu đó.

### Fix Win

- Khi mở `PdfiumDocument`, gọi `init_forms()` nếu backend hỗ trợ.
- Nếu form data lỗi, nuốt exception để không làm hỏng render PDF thường.

### Team Mac cần làm

- Nếu Mac dùng PDFium cho render hoặc print preview:
  - thêm init forms tương đương
- Nếu Mac dùng engine khác:
  - kiểm tra engine đó có bước enable form/widget appearance trước render không

### Verify

1. Dùng PDF scan có dấu hoặc signature widget.
2. Preview/in từ app Mac.
3. Dấu phải xuất hiện trong preview và bản in.

---

## F. Khóa PDFium toàn cục cho các luồng OCR / summarize / semantic search / page ops

**Commit chính:** `f217522`  
**File Win:** `packages/pdf_engine/pdfium_engine.py`, `packages/ocr/engine.py`, `packages/ai/chat_pdf.py`, `packages/ai/semantic_search.py`, `packages/document_core/converter.py`, `app/actions/auto_ocr.py`, `app/actions/document_ops.py`, `app/actions/edit.py`, `app/actions/annotate.py`, `app/actions/tts_dialog.py`

### Root cause
`pypdfium2` không thread-safe. Gọi song song từ nhiều thread có thể gây crash native, access violation hoặc lỗi ngầm.

### Fix Win

- Dùng `PDFIUM_LOCK = threading.RLock()`
- Mọi chỗ đụng PDFium phải đi qua lock này

### Team Mac cần làm

- Nếu Mac branch cũng dùng `pypdfium2`:
  - grep toàn bộ caller PDFium
  - đảm bảo OCR, summarize, semantic search, page extraction, print/render đều qua 1 lock chung
- Nếu Mac branch đã đổi engine:
  - kiểm tra engine tương ứng có ràng buộc thread-safety tương tự không

### Verify

- OCR nền + thumbnail/render + AI summarize/chat chạy gần nhau không crash
- mở file scan nhiều trang, tìm kiếm/summary/OCR liên tiếp không sập app

---

## G. Chat PDF — luôn nổi, giữ lịch sử, không mất state nhìn thấy

**Commit liên quan:** `f217522`, `8a92859`  
**File Win:** `app/ai_chat_dialog.py`, `packages/ai/chat_pdf.py`, `app/actions/ai_actions.py`, `app/window.py`, `app/ai_task_runner.py`

### Cụm vấn đề bên Win đã sửa

1. Bật/tắt `Luôn nổi` không làm mất nội dung chat đang hiển thị.
2. Đóng chat sau khi bật/tắt `Luôn nổi` không bị đơ.
3. Lịch sử chat không bị đổi identity khi file PDF được reload qua temp path.
4. Callback worker không được chạm GUI từ background thread.
5. Bubble `AI đang trả lời...` được thay tại chỗ, không rebuild toàn bộ khung chat.

### Root cause chính

- Identity history trước đây bám vào path có thể bị reload thành temp path.
- Signal worker nối trực tiếp vào closure thường, Qt không marshal chắc chắn về main thread.
- Toggle window flags có thể làm Qt recreate window state, nếu chỉ giữ state trong view sẽ mất chat nhìn thấy.

### Fix Win

- Khóa `chat_identity_path` ngay lúc mở tài liệu.
- `PDFChatSession._resolve_history_path()` hash theo resolved path ổn định, không hash theo `mtime/size`.
- Dùng `_DialogTaskRelay(QObject)` + `@pyqtSlot` để callback luôn quay về GUI thread.
- Lưu và restore `chat_html`, `input_text`, `status_text`, `status_style`, `scroll_value` khi toggle `WindowStaysOnTopHint`.
- Dùng `_thinking_start_pos` để replace bubble thinking in-place.

### Team Mac cần làm

- Nếu Mac có Chat PDF:
  - review toàn bộ cụm `dialog state + worker callback + history identity`
- Nếu Mac không có checkbox `Luôn nổi`:
  - vẫn phải port các phần shared:
    - history identity ổn định
    - callback về main thread
    - replace thinking bubble in-place

### Verify

1. Mở Chat PDF.
2. Gửi vài câu hỏi.
3. Bật/tắt `Luôn nổi` nếu Mac có.
4. Đóng chat, mở lại.
5. Chỉnh sửa/chú thích/reload tài liệu.
6. Mở lại chat.
7. Lịch sử phải còn, không mất vì temp path.
8. Không được có crash/thread-warning khi AI trả lời.

---

## H. Tài liệu scan + AI/OCR phải dùng cùng text cache/logic ổn định hơn

**Commit chính:** `f217522`  
**File Win:** `packages/ai/chat_pdf.py`, `packages/ai/semantic_search.py`, `app/ai_summarize_dialog.py`, `packages/ocr/engine.py`

### Ý chính cần Mac nắm

- Các tính năng AI trên file scan không thể giả định luôn có text layer sẵn.
- Win đã siết lại đường đọc text + OCR cache + lock PDFium để:
  - summarize scan ổn định hơn
  - semantic search không đua thread với OCR/render
  - Chat PDF không mất history khi tài liệu đổi temp path

### Team Mac cần làm

- Đối chiếu xem Mac đang dùng lại cùng lớp shared hay fork riêng.
- Nếu fork riêng:
  - đồng bộ các invariant:
    - text scan lấy được ổn định
    - cache identity bám vào source path
    - worker AI không phá UI thread

---

## 4. Những tài liệu nền Mac nên đọc kèm

Nếu team Mac chưa sync các đợt trước, cần đọc thêm:

- `docs/HANDOFF_MAC_BAO_MAT_2026-07.md`
- `docs/PHASE7_MACOS_DEPLOYMENT_GUIDE.md`
- `docs/2_DA_LAM.md`
- `docs/TESTER_BUG_REPORT_TC27_TC41.md`
- `QUY_TRINH_SUA_LOI.md`

Lý do:

- `HANDOFF_MAC_BAO_MAT_2026-07.md` là nền bảo mật/VPS dùng chung
- `PHASE7_MACOS_DEPLOYMENT_GUIDE.md` là parity guide cũ cho export/edit
- `2_DA_LAM.md` và `TESTER_BUG_REPORT_TC27_TC41.md` mô tả một loạt hành vi QA mà Mac nên đối chiếu lại

---

## 5. Checklist triển khai cho team Mac

- [ ] Rà branch Mac xem có recent-file flow tương đương `app/actions/file.py` không; nếu có thì port lỗi "không tìm thấy tài liệu".
- [ ] Port fix search 1 từ khớp được từ dính dấu câu.
- [ ] Port underline/strikeout theo search query không cần selection tay.
- [ ] Review page rotation capability; nếu Mac có page tools thì bổ sung `Rotate pages...` parity.
- [ ] Review print/render engine; nếu dùng PDFium thì thêm `init_forms()`.
- [ ] Audit mọi caller `pypdfium2` bên Mac; gom về 1 lock chung.
- [ ] Audit Chat PDF / summarize / semantic search:
  - [ ] history identity path ổn định
  - [ ] callback worker về main thread
  - [ ] không rebuild toàn bộ chat chỉ để thay bubble thinking
- [ ] Retest scan PDF có dấu/chữ ký widget khi preview/in.
- [ ] Retest AI + OCR + render chạy đồng thời không crash.

---

## 6. Kết luận

Từ mốc bàn giao `2026-07-07` đến `2026-07-09`, team Win đã có thêm **một delta đáng kể ở 3 cụm shared behavior**:

- file/recent UX
- annotation/search
- AI/OCR/PDFium/threading/chat history

Trong đó, phần **quan trọng nhất Mac phải đọc kỹ** là:

1. `packages/pdf_engine/pdfium_engine.py` + toàn bộ caller PDFium  
2. `app/ai_chat_dialog.py` / `app/ai_task_runner.py` / `packages/ai/chat_pdf.py`  
3. `app/actions/annotate.py`

Nếu Mac branch còn diverge mạnh, không cần bê nguyên UI Win; nhưng **các invariant hành vi** ở trên nên được giữ đồng nhất để tránh lệch bug giữa 2 nền tảng.
