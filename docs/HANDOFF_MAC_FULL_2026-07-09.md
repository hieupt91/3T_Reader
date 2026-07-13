# Bàn giao đầy đủ cho team Mac — tổng hợp nền tháng 06 và delta mới đến 09/07/2026

**Ngày lập:** 09/07/2026  
**Branch Win:** `piper-vps-sync`  
**Mục tiêu:** gom toàn bộ phần team Mac cần biết vào **một file duy nhất** để triển khai đối chiếu với nhánh Mac.

---

## 1. Cách dùng tài liệu này

Team Mac đọc file này theo đúng thứ tự:

1. Đọc phần **Mốc git và phạm vi**
2. Đọc phần **Các cụm tính năng shared phải đối chiếu**
3. Đọc phần **Delta mới sau handoff cũ**
4. Đi theo **Checklist triển khai**

Tài liệu này không yêu cầu Mac copy nguyên UI Windows.  
Mục tiêu là đồng bộ:

- hành vi shared
- contract với VPS/backend
- các invariant kỹ thuật
- các bug/regression đã được tìm ra ở Win để Mac không lặp lại

---

## 2. Mốc git và phạm vi

## 2.1. Handoff cũ đã có trên git

Mốc handoff Win -> Mac rõ nhất trước đợt này là **07/07/2026**:

- `4d9e641` — bàn giao team Mac các thay đổi bảo mật đợt 07/2026
- `fc6d5f5` — cập nhật trạng thái port sang Mac
- `d8eb3d8` — patch backend bảo mật đã deploy live + cập nhật handoff

Các tài liệu cũ liên quan:

- `docs/HANDOFF_MAC_BAO_MAT_2026-07.md`
- `docs/patches/backend-security-fixes-20260707.patch`
- `docs/patches/README.md`

## 2.2. Nền tháng 06 mà Mac phải xem như baseline parity

Tháng `06/2026` là giai đoạn Win hoàn thiện phần lớn shared behavior cho:

- viewer / annotation / selection / zoom / thumbnail sync
- signing / TSA / LTV / batch sign
- AI / TTS / translation / i18n
- print preview / OCR / export / edit existing text
- license / updater / secure config
- workflow sync Win/Mac

Các mốc docs/feature quan trọng:

- `4e92ab7` — tổng hợp cập nhật tính năng + guide cho team Mac
- `1b29610` — fix large PDF OOM, incremental save, invisible pyhanko stamps, update Mac guide
- `488b971` — thêm `docs/PHASE7_MACOS_DEPLOYMENT_GUIDE.md`
- `63cba1b` — guide sync Win/Mac
- `6a13584` — align cross-platform sync guidelines
- `431f724` — translation sync guide
- `0084c09` — finalize runtime fixes and handoff

## 2.3. Delta mới sau mốc 07/07 mà Mac chưa có trong handoff cũ

- `84a43cf` — rõ lỗi mở recent file khi file nguồn đã mất
- `0e2c776` — search 1 từ match được từ dính dấu câu
- `46c12ef` — expose `Rotate pages...`
- `f217522` — gói regression fixes lớn
- `8a92859` — giữ lịch sử Chat PDF + GUI callback đúng luồng

---

## 3. Tài liệu Mac phải đọc

Team Mac đọc đủ các file sau:

1. `docs/HANDOFF_MAC_FULL_2026-07-09.md`  
   File này là entry point chính.

2. `docs/HANDOFF_MAC_BAO_MAT_2026-07.md`  
   Nền bảo mật/VPS và các lưu ý shared backend.

3. `docs/PHASE7_MACOS_DEPLOYMENT_GUIDE.md`  
   Hướng dẫn parity cho export/edit existing text.

4. `docs/PHASE1_MAC_HANDOVER.md`  
   Handoff phase 1 cũ, có nhiều mô tả nền về cấu trúc Mac/Win.

5. `docs/HANDOFF_MAC_DELTA_2026-07-09.md`  
   Delta rút gọn sau mốc 07/07.

6. `docs/2_DA_LAM.md`

7. `docs/TESTER_BUG_REPORT_TC27_TC41.md`

8. `QUY_TRINH_SUA_LOI.md`

---

## 4. Cụm shared behavior Mac phải đối chiếu

## A. Viewer / annotation / selection / thumbnail sync

### Nền tháng 06 bên Win

Đầu tháng 06 Win tập trung ổn định viewer và annotation:

- sync cuộn trang với thumbnail
- ổn định chọn text để highlight/underline/strikeout
- sticky note / note runtime / autosave target
- object edit session
- signed widget appearances
- shared PDF selection reader
- flush annotations trước heavy PDF ops

### Những file shared cần Mac tự grep ở nhánh mình

- `app/actions/annotate.py`
- `app/pdf_viewer.py`
- `app/sidebar.py`
- `assets/css/pdfjs_overrides.css`
- JS hooks/bridge liên quan text layer, selection, note, overlay

### Invariant cần giữ

- selection text ổn định, không phụ thuộc may rủi timing của PDF.js
- thumbnail và trang chính không lệch state khi zoom/cuộn/xoay
- autosave annotation không ghi nhầm target path
- signed widgets không biến mất do normalize/render lại

### Verify

- highlight/underline/strikeout nhiều lần liên tiếp
- note/comment rồi reload
- zoom lớn/nhỏ + cuộn liên tục
- file có chữ ký số / widget appearance vẫn hiện đúng

---

## B. PDFium shared behavior

### Đây là cụm ưu tiên cao nhất

Win hiện coi `pypdfium2` là **không thread-safe**.  
Nếu gọi từ nhiều thread cùng lúc, có thể:

- crash native
- access violation
- lỗi ngầm khi OCR/render/summarize chạy đồng thời

### Fix Win đã áp

- `packages/pdf_engine/pdfium_engine.py` có `PDFIUM_LOCK = threading.RLock()`
- mọi chỗ đụng PDFium phải đi qua lock
- với PDF scan có widget appearance, phải gọi `init_forms()` trước khi render/in

### Caller bên Win đã phải đồng bộ

- `packages/ocr/engine.py`
- `packages/ai/chat_pdf.py`
- `packages/ai/semantic_search.py`
- `packages/document_core/converter.py`
- `app/actions/auto_ocr.py`
- `app/actions/document_ops.py`
- `app/actions/edit.py`
- `app/actions/annotate.py`
- `app/actions/tts_dialog.py`
- `app/ai_summarize_dialog.py`

### Team Mac cần làm

- grep toàn bộ chỗ gọi PDFium trên branch Mac
- nếu Mac cũng dùng `pypdfium2`:
  - gom về 1 lock chung
  - mọi render/ocr/search/summarize/print đều qua lock
- nếu Mac dùng engine khác:
  - xác nhận engine đó có constraint tương tự không

### Verify

- OCR nền + preview/render + AI summarize cùng lúc không crash
- semantic search trên file scan không phá viewer
- preview/in file scan có dấu/con dấu/signature widget vẫn hiện đúng

---

## C. Print / preview / scan parity

### Nền tháng 06 bên Win

Win đã hoàn thiện:

- in-app print preview
- mixed orientation
- sharpen preview rendering
- toolbar preview
- giữ đúng hướng in ngang/dọc
- preview 2 trang theo spread

### Delta cần Mac biết thêm

Trong regression fixes đầu tháng 07, Win còn xử lý thêm trường hợp:

- file scan có dấu/signature widget không hiện khi in
- nguyên nhân là cần `init_forms()` trước render PDFium

### Team Mac cần làm

- nếu Mac có print preview riêng:
  - kiểm tra mixed orientation
  - kiểm tra preview spread
  - kiểm tra file scan có widget appearance
- nếu dùng shared print logic:
  - đồng bộ behavior và test như Win

### Verify

1. PDF thường portrait
2. PDF landscape
3. PDF mixed orientation
4. PDF scan có dấu/con dấu/signature widget
5. Preview và bản in phải nhất quán

---

## D. OCR / summarize / semantic search / scan workflow

### Nền tháng 06

Win đã có:

- OCR flow
- summarize
- semantic search
- cache speech / chat / OCR text

### Delta mới

Win tiếp tục siết lại để:

- file scan không bị giả định sai là luôn có text layer
- summarize scan ổn định hơn
- semantic search không đua thread với OCR/render
- Chat PDF không mất identity khi reload temp path

### Team Mac cần làm

- rà lại toàn bộ flow AI trên scan:
  - OCR text lấy từ đâu
  - cache identity bám vào source path hay temp path
  - worker có động vào GUI sai thread không

### Verify

- file scan nhiều trang
- OCR nền chạy
- summarize chạy
- semantic search chạy
- Chat PDF vẫn còn context/history

---

## E. Chat PDF / AI dialog / worker threading

### Đây là cụm ưu tiên rất cao

Win đã sửa một loạt regression của Chat PDF:

1. bật/tắt `Luôn nổi` không làm mất chat đang hiển thị
2. đóng chat sau khi bật/tắt `Luôn nổi` không bị đơ
3. lịch sử chat không bị đổi identity khi file reload thành temp path
4. callback worker không được chạm GUI từ background thread
5. bubble `AI đang trả lời...` được thay tại chỗ, không rebuild toàn bộ khung chat

### Root cause Win đã xác định

- identity history trước đây dựa vào path dễ đổi
- signal worker nối vào closure thường, Qt không marshal chắc chắn về main thread
- toggle window flags có thể làm Qt recreate state nếu view giữ state hời hợt

### Fix Win

- khóa `chat_identity_path` ngay lúc mở file
- `packages/ai/chat_pdf.py` hash history theo resolved path ổn định
- `app/ai_task_runner.py` thêm `_DialogTaskRelay(QObject)` với `@pyqtSlot`
- `app/ai_chat_dialog.py` lưu/restore `chat_html`, input, status, scroll
- thay bubble thinking bằng `_thinking_start_pos` + `QTextCursor`

### Team Mac cần làm

- nếu Mac có Chat PDF:
  - review toàn bộ cụm state + history + threading
- nếu Mac không có `Luôn nổi`:
  - vẫn phải đối chiếu các invariant shared:
    - history identity
    - callback main thread
    - replace thinking in-place

### Verify

1. mở Chat PDF
2. hỏi vài câu
3. reload/chỉnh sửa/chú thích tài liệu
4. mở lại chat
5. lịch sử vẫn còn
6. không crash/thread warning

---

## F. Search / annotation behavior

### Delta mới quan trọng

#### F1. Search 1 từ phải match được cả token dính dấu câu

Win đã sửa:

- query 1 từ -> match substring
- query nhiều từ -> giữ exact match

Ví dụ phải tìm được:

- `sửa`
- `sửa.`
- `chỉnh sửa.`

#### F2. Underline / strikeout theo search query mà không cần selection tay

Win đã sửa:

- nếu đang có search query:
  - `Gạch dưới`
  - `Gạch ngang`
  chạy trực tiếp trên kết quả tìm kiếm
- line marks không padding rect như highlight

### Team Mac cần làm

- rà behavior search annotations
- nếu branch Mac dùng helper gần giống Win:
  - port thẳng logic
- nếu branch Mac có implementation khác:
  - vẫn phải giữ behavior đầu ra giống Win

### Verify

- Ctrl+F query 1 từ có dấu câu
- underline khi không bôi đen
- strikeout khi không bôi đen
- rect không lệch

---

## G. Recent file UX

### Delta mới

Nếu user mở file trong danh sách recent nhưng file gốc đã bị xóa/di chuyển:

- phải báo rõ `không tìm thấy tài liệu tại đường dẫn ...`
- không báo lỗi generic kiểu “không mở được file”

### Team Mac cần làm

- nếu Mac có recent list:
  - review thông báo lỗi mở recent
  - tách lỗi “file mất” khỏi lỗi “mở thất bại thật sự”

### Verify

1. mở file
2. xóa file ngoài Finder
3. mở lại từ recent
4. app phải báo đúng bản chất lỗi

---

## H. Rotate pages / page ops / save consistency

### Nền tháng 06

Win đã xử lý:

- soft reload/hard reload ổn định hơn
- page ops sau edit/insert/delete bớt trắng màn hình
- save state đồng bộ hơn

### Delta mới

Win bổ sung đường vào `Rotate pages...` cho:

- xoay 1 trang
- xoay toàn bộ tài liệu

và tiếp tục siết consistency giữa edit state và page operations.

### Team Mac cần làm

- nếu branch Mac có page tools:
  - xem đã có rotate pages toàn cục chưa
  - kiểm tra page ops sau insert/edit/delete/rotate có đồng bộ state không

### Verify

- edit xong rồi rotate/delete/split
- viewer không blank
- page numbering không lệch
- thumbnail và main page cùng state

---

## I. Signing / TSA / LTV / batch sign / license-update contracts

### Nền tháng 06

Win đã xây khá nhiều thứ:

- batch sign
- TSA
- LTV
- signature profiles
- signed updater
- license behavior
- reactivation same-device

### Team Mac cần nhớ

- không copy `windows_provider.py`
- nhưng phải đối chiếu:
  - protocol/signing shared layer
  - verifier shared layer
  - license/update client contracts
  - same-device reactivation logic

### Tài liệu tham chiếu

- `docs/HANDOFF_MAC_BAO_MAT_2026-07.md`
- `docs/PHASE1_MAC_HANDOVER.md`
- `docs/PHASE7_MACOS_DEPLOYMENT_GUIDE.md`

---

## J. TTS / AI / i18n / translation

### Nền tháng 06

Tháng 06 Win có cụm khá lớn:

- TTS đọc văn bản
- native macOS `say` / `afplay`
- Piper voice sync
- translation module
- dynamic language packs
- i18n hệ thống
- fix translation threads

### Team Mac cần làm

- đối chiếu lại branch Mac đã có những gì
- chú ý:
  - translation worker/thread lifecycle
  - TTS crash guards
  - module download đa nền tảng
  - symlink extraction trên macOS

---

## 5. Những chỗ không nên bê nguyên từ Win

Không cần copy nguyên xi:

- Ribbon/menu wiring riêng của Win
- file Win-only
- installer Windows
- Windows provider / DLL lookup / font path

Nhưng phải giữ **invariant behavior** giống nhau ở layer shared.

---

## 6. Checklist triển khai cho team Mac

- [ ] Đọc hết file này trước khi sửa gì.
- [ ] Đọc thêm:
  - [ ] `docs/HANDOFF_MAC_BAO_MAT_2026-07.md`
  - [ ] `docs/PHASE7_MACOS_DEPLOYMENT_GUIDE.md`
  - [ ] `docs/PHASE1_MAC_HANDOVER.md`
  - [ ] `docs/HANDOFF_MAC_DELTA_2026-07-09.md`
  - [ ] `QUY_TRINH_SUA_LOI.md`
- [ ] Audit toàn bộ caller `pypdfium2`.
- [ ] Audit Chat PDF / AI threading / history identity.
- [ ] Audit search / annotation behavior.
- [ ] Audit recent file error handling.
- [ ] Audit print preview / scan forms rendering.
- [ ] Audit rotate/page ops parity nếu Mac có feature đó.
- [ ] Báo lại theo 3 nhóm:
  - [ ] Mac đã có sẵn
  - [ ] cần port
  - [ ] không áp dụng vì khác kiến trúc

---

## 7. Quy tắc triển khai

Khi team Mac bắt đầu port/fix, phải bám đúng `QUY_TRINH_SUA_LOI.md`:

- tái hiện được lỗi hoặc behavior cần đồng bộ
- chỉ ra root cause
- đánh giá blast radius
- sửa tối thiểu
- verify lại luồng liên quan

Không port kiểu copy cơ học cả file nếu chỉ cần 1 invariant behavior.

---

## 8. Kết luận ngắn

Nếu team Mac chỉ nhớ 5 việc ưu tiên nhất, thì là:

1. `PDFIUM_LOCK` và `init_forms()`  
2. Chat PDF: history identity + callback main thread  
3. Search 1 từ match token dính dấu câu  
4. Underline/strikeout theo search query không cần selection  
5. Recent file báo rõ khi file nguồn đã mất

Phần còn lại đọc tiếp trong tài liệu này và các file tham chiếu liên quan.
