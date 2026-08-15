# Kế hoạch tích hợp chế độ soạn thảo Word cơ bản cho 3T Reader

**Ngày lập:** 09/07/2026  
**Mục tiêu:** phân tích chi tiết và đề xuất hướng tích hợp tính năng soạn thảo văn bản cơ bản vào 3T Reader, tận dụng nền LibreOffice hiện có trong repo.

---

## 1. Bài toán thực tế

Người dùng không cần toàn bộ sức mạnh của Microsoft Word.  
Mục tiêu hợp lý hơn là một chế độ **Word Basic** cho phép:

- tạo văn bản mới
- mở file `docx`
- gõ/chỉnh sửa văn bản
- định dạng cơ bản:
  - font
  - cỡ chữ
  - đậm / nghiêng / gạch dưới
  - màu chữ
  - căn trái / giữa / phải / đều
  - bullet / numbering
  - spacing đoạn và dòng
  - lề trang cơ bản
- lưu `docx`
- xuất `pdf`
- in

Tức là một **trình soạn thảo tài liệu cơ bản**, không phải một bản sao đầy đủ của Word.

---

## 2. Trạng thái hiện tại của repo

Repo hiện đã có sẵn nền quan trọng để đi theo hướng này:

### 2.1. Đã có flow mở tài liệu Office bằng LibreOffice

File:

- [app/actions/document_converter.py](/C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/app/actions/document_converter.py)

Trong đó đã có:

- tải module LibreOffice riêng cho Win/Mac
- tìm `soffice`
- convert `doc/docx/xls/xlsx` sang PDF
- mở kết quả PDF trong viewer hiện tại

Điểm chính:

- `download_and_extract_libreoffice(window)`
- `get_libreoffice_bin()`
- `convert_office_to_pdf(window, file_path)`

### 2.2. Đã có export PDF -> Word / Excel

File:

- [packages/document_core/converter.py](/C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/packages/document_core/converter.py)
- [app/actions/export.py](/C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/app/actions/export.py)

Repo hiện có:

- `convert_pdf_to_docx()`
- `convert_pdf_to_docx_layout()`
- `convert_pdf_to_docx_structured()`
- `convert_pdf_to_xlsx()`

### 2.3. App đã chấp nhận mở `doc/docx/xls/xlsx`

File:

- [app/window.py](/C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/app/window.py)

Hiện drag/drop và open dialog đã hỗ trợ:

- `.doc`
- `.docx`
- `.xls`
- `.xlsx`

Nhưng hiện nay bản chất là:

> tài liệu Office được **convert sang PDF để xem**, chứ chưa có editor thực thụ cho Word.

---

## 3. Kết luận kỹ thuật ngắn

**Có thể tích hợp “Word Basic Mode” vào 3T Reader.**

Nhưng cần chọn đúng kiến trúc:

- **không** biến PDF viewer hiện tại thành editor Word
- **không** tự viết lại một word processor từ đầu
- **nên** dùng LibreOffice làm engine tài liệu phía dưới
- 3T Reader chỉ cung cấp UI đơn giản, gọn, đủ dùng

Nói thẳng:

> Nếu cố làm “Word đầy đủ” thì scope nổ ngay.  
> Nếu chốt là “Word cơ bản” thì làm được và hợp lý.

---

## 4. Các hướng kỹ thuật có thể chọn

## Phương án A — Dùng PDF viewer hiện tại và giả lập chỉnh sửa trên bản convert PDF

### Ý tưởng

- mở `docx`
- convert sang PDF
- dùng overlay/editor trên viewer để cho người dùng sửa như đang sửa PDF

### Ưu điểm

- tái dùng tối đa viewer hiện tại
- không cần editor mới

### Nhược điểm

- sai bản chất tài liệu gốc
- rất khó map sửa đổi ngược từ PDF về `docx`
- paragraph, list, spacing, reflow, page break sẽ vỡ
- save `docx` gần như không đáng tin

### Kết luận

**Không nên chọn.**

Phương án này chỉ hợp để xem hoặc annotate, không hợp để soạn thảo Word.

---

## Phương án B — Mở LibreOffice ngoài app, 3T Reader chỉ làm launcher + preview

### Ý tưởng

- 3T Reader mở `docx`
- bấm “Chỉnh sửa” thì mở bằng LibreOffice ngoài app
- lưu xong quay về 3T Reader reload preview

### Ưu điểm

- nhanh làm
- ít rủi ro kỹ thuật
- dùng đúng engine Word/LibreOffice

### Nhược điểm

- UX rời rạc
- user có cảm giác bị văng sang app khác
- không tạo ra giá trị “3T Reader có editor riêng”

### Kết luận

**Dùng được như fallback**, nhưng không nên là sản phẩm chính nếu muốn tích hợp thật.

---

## Phương án C — Tích hợp một “Word Basic Mode” riêng trong app, dùng LibreOffice làm engine

### Ý tưởng

Thêm một chế độ editor riêng cho tài liệu Word:

- `PDF Mode`
- `Word Basic Mode`

Trong `Word Basic Mode`:

- tài liệu `docx` là tài liệu gốc
- LibreOffice xử lý file thật
- 3T Reader điều khiển qua một lớp bridge/adapter
- UI chỉ lộ ra bộ công cụ cơ bản

### Ưu điểm

- đúng bản chất dữ liệu
- save `docx` đáng tin hơn
- export PDF/in dễ hơn
- vẫn giữ được trải nghiệm “mọi thứ trong 3T Reader”

### Nhược điểm

- phức tạp hơn phương án mở LibreOffice ngoài app
- cần thêm editor surface riêng
- cần bridge giữa 3T Reader và LibreOffice

### Kết luận

**Đây là phương án nên chọn.**

---

## 5. Khuyến nghị kiến trúc chính thức

Đề xuất chính thức:

> Xây một **Word Basic Mode** trong 3T Reader, dùng LibreOffice làm engine tài liệu, và chỉ hỗ trợ bộ tính năng soạn thảo cơ bản.

### Kiến trúc đề xuất

Gồm 4 lớp:

1. **Document shell**
   - quản lý tab Word
   - mở/tạo/lưu file
   - recent files
   - dirty state

2. **Editor UI**
   - vùng soạn thảo
   - toolbar formatting
   - status bar

3. **Word adapter**
   - lớp Python điều phối lệnh
   - gọi LibreOffice / UNO / subprocess

4. **Persistence & export**
   - save `docx`
   - export `pdf`
   - print

---

## 6. Scope nên chốt cho phiên bản đầu

## 6.1. Bắt buộc có

- tạo mới tài liệu `.docx`
- mở `.docx`
- save / save as
- nhập và sửa text
- font family
- font size
- bold
- italic
- underline
- text color
- align left / center / right / justify
- bullet list
- numbered list
- line spacing cơ bản
- paragraph spacing before/after
- page margins cơ bản
- export PDF
- print

## 6.2. Có thể thêm sau

- chèn ảnh
- chèn bảng đơn giản
- header/footer cơ bản
- page number
- find/replace

## 6.3. Những gì nên loại khỏi phase đầu

Đây là chỗ phải chốt cứng để không làm vỡ scope:

- không hỗ trợ track changes
- không hỗ trợ comment/review như Word đầy đủ
- không hỗ trợ section break phức tạp
- không hỗ trợ mail merge
- không hỗ trợ equation editor
- không hỗ trợ SmartArt / shape phức tạp
- không hỗ trợ macro VBA
- không hỗ trợ collaborative editing realtime
- không cố clone toàn bộ ribbon của Microsoft Word

Nếu không khóa phạm vi từ đầu, phần khó nhất không phải viết UI mà là:

- mapping hành vi đúng với document model
- giữ file `docx` ổn định sau nhiều lần save
- kiểm soát preview / print / export nhất quán

---

## 7. Đề xuất kiến trúc chi tiết hơn

## 7.1. Mô hình sản phẩm

Đề xuất thêm một loại tab tài liệu mới trong app:

- `PdfDocumentTab`
- `ImageDocumentTab`
- `WordBasicDocumentTab`

`WordBasicDocumentTab` không dùng logic annotate/search/render của PDF làm lõi soạn thảo.  
Nó là một surface riêng, nhưng vẫn đi chung:

- tab bar
- recent files
- file menu
- save flow
- print flow
- status bar
- theme/language hiện có

Điểm này quan trọng vì nếu cố nhét editor Word vào tab PDF hiện tại thì:

- state rất dễ chồng chéo
- shortcut conflict
- toolbar conflict
- logic dirty/save dễ sai
- sau này support Excel/PowerPoint càng khó mở rộng

## 7.2. State model đề xuất

Nên có một state object rõ ràng cho mỗi tab Word:

```python
class WordTabState:
    source_path: str | None
    display_name: str
    session_id: str
    dirty: bool
    is_new_document: bool
    file_format: str  # docx / odt / import-doc
    preview_pdf_path: str | None
    last_preview_revision: int
    last_saved_revision: int
    current_revision: int
    read_only: bool
    editor_ready: bool
    libreoffice_attached: bool
    pending_preview_job: bool
```

Ít nhất phải có ba revision/state độc lập:

- `current_revision`: tăng khi user sửa nội dung
- `last_saved_revision`: revision đã save ra file gốc
- `last_preview_revision`: revision đã render ra preview PDF

Lý do:

- tránh preview cũ nhưng app tưởng đang mới
- tránh save xong mà dirty state không reset đúng
- tránh in/export lấy nhầm snapshot

## 7.3. Module đề xuất cụ thể

### A. UI / application layer

- `app/actions/word_basic.py`
  - entrypoint menu/ribbon
  - new/open/save/save as/export pdf/print
  - hỏi lưu khi đóng tab
  - xử lý missing LibreOffice module

- `app/word_basic_editor.py`
  - widget chính của editor
  - toolbar + editor body + status line
  - nhận signal từ adapter/session
  - không chứa logic file format

- `app/word_basic_toolbar.py`
  - font family
  - font size
  - bold / italic / underline
  - text color
  - align left / center / right / justify
  - bullets / numbering
  - line spacing presets
  - page margin presets

- `app/word_basic_preview.py`
  - nếu có preview PDF nhúng bên phải/dưới
  - render trạng thái “đang cập nhật preview”
  - không tự ý sửa document

### B. document/session layer

- `packages/document_core/word_basic_session.py`
  - quản lý lifecycle của 1 tài liệu Word
  - open/create/attach/close
  - dirty/revision/save/export
  - serialize command queue nếu cần

- `packages/document_core/libreoffice_bridge.py`
  - tìm `soffice`
  - launch process service
  - attach UNO connection
  - map command Python -> LibreOffice document ops
  - export PDF
  - close document an toàn

- `packages/document_core/word_basic_commands.py`
  - định nghĩa command surface mức trung gian
  - giúp UI không gọi UNO trực tiếp

- `packages/document_core/word_basic_preview_service.py`
  - debounce preview rebuild
  - quản lý temp PDF
  - tránh convert đè chồng nhiều job

### C. persistence / recovery layer

- `packages/document_core/word_basic_autosave.py`
  - snapshot recovery
  - autosave file tạm
  - khôi phục sau crash

- `packages/document_core/word_basic_recent.py`
  - recent docs cho Word mode
  - lưu metadata định dạng/mode

---

## 8. Chọn engine: dùng gì thật sự bên dưới

## 8.1. Kết luận ngắn

Nếu muốn:

- mở `docx` thật
- save `docx` ổn
- print/export PDF khớp

thì phải coi LibreOffice là **document engine thật**, không chỉ là tool convert.

## 8.2. Hai cách dùng LibreOffice

### Cách 1: subprocess convert-only

Đây là thứ repo đang có:

- mở/tải `soffice`
- convert file Office -> PDF
- viewer chỉ đọc PDF

Cách này **không đủ** cho editor.

### Cách 2: UNO bridge / service mode

Ý tưởng:

- khởi chạy `soffice` dạng service hoặc invisible
- Python attach qua UNO socket/pipe
- giữ một document object sống trong session
- mọi thao tác format cơ bản đi qua command API
- save/export/print đều chạy trên document đó

Đây mới là hướng đủ lực cho `Word Basic Mode`.

## 8.3. Vì sao không nên lấy `QTextEdit` làm sản phẩm thật

`QTextEdit` có thể làm proof-of-concept nhanh, nhưng có ba vấn đề lớn:

1. Không đại diện đúng `docx` thật
2. Save round-trip sang `docx` yếu
3. Preview/in/export dễ lệch với nội dung người dùng thấy

Nó chỉ hợp cho:

- prototype UI
- demo toolbar
- spike rất ngắn để chốt UX

Không hợp cho sản phẩm chính nếu user muốn dùng thay Word cơ bản.

---

## 9. Command surface nên chốt từ đầu

UI không nên gọi API UNO rải rác.  
Nên có một command surface ổn định như sau:

```python
session.new_document()
session.open_document(path)
session.save()
session.save_as(path)
session.export_pdf(path)
session.print_document(printer_name=None)

session.insert_text(text)
session.delete_selection()

session.set_font_family(name)
session.set_font_size(points)
session.toggle_bold()
session.toggle_italic()
session.toggle_underline()
session.set_text_color(rgb)

session.set_alignment("left")
session.set_alignment("center")
session.set_alignment("right")
session.set_alignment("justify")

session.set_list_style("bullet")
session.set_list_style("number")
session.clear_list_style()

session.set_line_spacing(mode="1.0")
session.set_paragraph_spacing(before=0, after=6)
session.set_page_margins(top, right, bottom, left)

session.undo()
session.redo()
session.get_selection_state()
session.close()
```

Lợi ích:

- UI đơn giản hơn
- test dễ hơn
- có thể mock session để test app layer
- sau này Mac team chỉ cần giữ contract này

---

## 10. Thiết kế UI nên đi theo hướng nào

## 10.1. Không nên nhồi full ribbon Word

User đang cần:

- soạn văn bản
- căn chỉnh cơ bản
- lưu/in/xuất PDF

Nên UI phù hợp hơn là một toolbar gọn, chia nhóm rõ:

### Nhóm File

- Tạo mới
- Mở
- Lưu
- Lưu thành
- Xuất PDF
- In

### Nhóm Font

- Font family
- Font size
- Bold
- Italic
- Underline
- Text color

### Nhóm Paragraph

- Align left
- Align center
- Align right
- Justify
- Bullet list
- Number list
- Increase/decrease indent
- Line spacing

### Nhóm Page

- Margin preset
- Orientation
- Page size

## 10.2. Layout editor đề xuất

Có 3 layout khả thi:

### Layout A: chỉ editor

- nhanh nhất
- ít phức tạp
- không có preview PDF song song

### Layout B: editor + preview panel

- trái: editor
- phải: preview PDF
- preview cập nhật chậm có kiểm soát

### Layout C: editor + mode switch

- Edit mode
- Print preview mode

Khuyến nghị thực tế cho phase đầu:

> dùng **Layout C** hoặc **Layout A**, chưa nên làm preview song song realtime.

Lý do:

- preview PDF rebuild tốn thời gian
- document dài sẽ lag nếu convert liên tục
- print preview chỉ cần khi user sắp in/xuất

## 10.3. Status bar nên có gì

- số trang hiện tại của tài liệu
- trạng thái save: `Đã lưu` / `Chưa lưu`
- trạng thái engine: `Sẵn sàng` / `Đang đồng bộ` / `Mất kết nối`
- zoom editor nếu có
- ngôn ngữ / chế độ nhập nếu sau này cần

---

## 11. Luồng nghiệp vụ chi tiết

## 11.1. Tạo mới tài liệu

1. User bấm `Tài liệu Word mới`
2. App kiểm tra LibreOffice engine đã sẵn sàng chưa
3. Nếu chưa có module:
   - hiện dialog tải/cài như flow Office hiện tại
4. App tạo session mới
5. Session yêu cầu bridge tạo document trống
6. UI mở tab `Chưa lưu 1.docx`
7. Dirty = `False`
8. Khi user gõ nội dung đầu tiên:
   - `current_revision += 1`
   - dirty = `True`

## 11.2. Mở file `docx`

1. User chọn file `docx`
2. App kiểm tra file tồn tại và quyền truy cập
3. App tạo Word session
4. Bridge mở tài liệu bằng LibreOffice
5. Session lấy metadata cơ bản:
   - title
   - page count nếu có
   - read-only state
6. UI bind toolbar với selection state
7. `last_saved_revision = current_revision`

## 11.3. Lưu

1. User bấm `Lưu`
2. Session flush command queue
3. Bridge yêu cầu LibreOffice save
4. Nếu save thành công:
   - `last_saved_revision = current_revision`
   - dirty = `False`
5. Nếu lỗi:
   - giữ nguyên dirty
   - báo lỗi rõ lý do

## 11.4. Save As

1. User chọn đường dẫn mới
2. Session validate extension
3. Bridge save ra file mới
4. Session cập nhật `source_path`
5. Recent files cập nhật lại

## 11.5. Export PDF

1. Session save nếu có thay đổi chưa lưu
2. Bridge gọi export PDF từ document hiện tại
3. File PDF tạo xong thì:
   - cho mở ngay trong viewer PDF
   - hoặc chỉ báo thành công

## 11.6. In

Có 2 hướng:

- in trực tiếp từ LibreOffice engine
- export PDF tạm rồi dùng luồng in PDF hiện có

Khuyến nghị phase đầu:

> export PDF tạm rồi dùng pipeline in PDF hiện tại.

Lý do:

- đồng bộ với hệ thống in sẵn có
- ít khác biệt UI
- dễ debug hơn

---

## 12. Đồng bộ nội dung và hiệu năng

## 12.1. Vấn đề chính

Nếu mỗi lần user gõ một ký tự mà app lại:

- save
- export PDF
- reload preview

thì sẽ chậm ngay.

## 12.2. Chiến lược hợp lý

Phân tách 3 lớp đồng bộ:

### A. Đồng bộ thao tác edit

- chạy ngay trên document session
- không chờ preview

### B. Đồng bộ save file

- chỉ khi user bấm save hoặc autosave

### C. Đồng bộ preview PDF

- debounce 800ms đến 1500ms sau khi user dừng gõ
- hủy job cũ nếu có job mới
- chỉ rebuild khi cần

## 12.3. Đề xuất cho phase đầu

- không preview realtime khi đang gõ
- chỉ có `Print Preview`
- chỉ rebuild khi:
  - user mở preview
  - user bấm export PDF
  - user bấm in

Đây là quyết định thực dụng nhất.

---

## 13. LibreOffice process lifecycle

## 13.1. Phải quản lý như một service

Nếu mỗi lần mở file lại spawn một `soffice` mới thì:

- nặng
- mở chậm
- dễ treo process rác
- khó cleanup

Nên dùng mô hình:

- app-level service manager
- một LibreOffice process nền
- nhiều session document bám vào process đó

## 13.2. Thành phần đề xuất

```python
class LibreOfficeServiceManager:
    def ensure_started(self) -> None: ...
    def connect(self) -> object: ...
    def is_alive(self) -> bool: ...
    def restart(self) -> None: ...
    def shutdown(self) -> None: ...
```

```python
class LibreOfficeDocumentHandle:
    def open(self, path: str) -> None: ...
    def create_blank(self) -> None: ...
    def save(self) -> None: ...
    def save_as(self, path: str) -> None: ...
    def export_pdf(self, path: str) -> None: ...
    def close(self) -> None: ...
```

## 13.3. Failure cases phải tính trước

- `soffice` không tồn tại
- `soffice` có nhưng không start được
- UNO không attach được
- document bị khóa bởi process khác
- file read-only
- save thất bại do quyền ghi
- process LibreOffice chết giữa phiên

Mỗi case trên phải có thông báo riêng. Không được dồn hết thành một lỗi chung mơ hồ.

---

## 14. Tương thích định dạng

## 14.1. Nên chốt phase đầu chỉ hỗ trợ `docx`

Đây là quyết định đúng về kỹ thuật.

`doc` cũ:

- định dạng legacy
- dễ phát sinh khác biệt import/export
- khó test round-trip ổn định hơn

`docx`:

- phổ biến
- hiện đại
- dễ chốt test matrix

Khuyến nghị:

- phase đầu: mở/tạo/lưu `docx`
- `doc` chỉ cho phép import và yêu cầu save lại thành `docx`

## 14.2. Quy tắc khi mở file `doc`

Nếu vẫn muốn nhận `doc`:

1. mở bằng LibreOffice
2. hiện banner:
   - `Định dạng .doc cũ, nên lưu lại thành .docx để chỉnh sửa ổn định hơn`
3. default action là `Save As .docx`

---

## 15. Phần có thể tái sử dụng từ repo hiện tại

## 15.1. Dùng lại được

- `download_and_extract_libreoffice(window)`
- `get_libreoffice_bin()`
- một phần dialog/message flow cho cài module
- file open / drag-drop acceptance cho office docs
- pipeline export/in từ PDF ở mức app shell
- recent files framework hiện có nếu đang dùng chung metadata

## 15.2. Không nên tái sử dụng trực tiếp

- logic render/search/annotate của PDF viewer
- logic sửa text gốc PDF
- state highlight/comment/annotation
- thumbnail sidebar PDF

Lý do:

- Word mode là document editor, không phải PDF canvas editor

---

## 16. Rủi ro kỹ thuật thật sự

## 16.1. Rủi ro cao nhất

1. UNO bridge khó debug hơn subprocess thường
2. Khác biệt hành vi giữa Win và Mac
3. Quản lý process LibreOffice bị treo/rò session
4. Preview/in/save có thể lệch nếu luồng state không rõ
5. Toolbar state theo selection dễ sai nếu sync kém

## 16.2. Cách giảm rủi ro

- khóa phase đầu chỉ `docx`
- không làm preview realtime
- có service manager riêng
- command API rõ ràng, không gọi UNO tản mát
- test file mẫu cố định
- thêm logging riêng cho Word mode

---

## 17. Logging và chẩn đoán lỗi

Nên có log channel riêng, ví dụ:

- `word_basic.session`
- `word_basic.bridge`
- `word_basic.preview`
- `word_basic.autosave`

Log tối thiểu cần có:

- start/stop LibreOffice service
- open/save/save as/export pdf
- thời gian thực thi mỗi bước
- exception khi attach UNO
- đường dẫn file đang thao tác
- số revision hiện tại

Điều này rất quan trọng vì lỗi Word mode thường không nằm ở UI mà nằm ở:

- process lifecycle
- lock file
- bridge sync

---

## 18. Autosave và crash recovery

Nếu làm editor thật thì phải nghĩ luôn đến recovery.

## 18.1. Mức tối thiểu

- autosave 30-60 giây/lần nếu dirty
- ghi snapshot tạm trong thư mục app data
- lưu mapping `session_id -> original_path`

## 18.2. Khi app mở lại

Nếu thấy snapshot chưa recover:

- hiện dialog khôi phục
- cho chọn:
  - khôi phục bản gần nhất
  - bỏ qua

## 18.3. Vì sao cần ngay phase đầu

Vì đây là tính năng soạn thảo.  
Mất nội dung người dùng gõ sẽ nghiêm trọng hơn nhiều so với lỗi viewer PDF.

---

## 19. Kế hoạch triển khai theo pha

## Phase 0 - Spike kỹ thuật

Mục tiêu:

- chứng minh có thể mở tài liệu `docx`
- attach LibreOffice service
- save thành công
- export PDF thành công

Deliverable:

- script thử nghiệm độc lập
- log attach/open/save/export
- tài liệu hóa command cơ bản

## Phase 1 - Engine layer

Mục tiêu:

- có `LibreOfficeServiceManager`
- có `WordBasicSession`
- có `Command API`

Deliverable:

- unit tests cho state/session
- integration tests mở/lưu/xuất

## Phase 2 - UI editor cơ bản

Mục tiêu:

- tab Word
- toolbar font/paragraph/file
- save/save as/export/in

Deliverable:

- dùng được cho tài liệu cơ bản hằng ngày

## Phase 3 - Recovery + polish

Mục tiêu:

- autosave
- crash recovery
- read-only handling
- warning format `.doc`

## Phase 4 - Nâng cấp tùy chọn

- chèn ảnh
- chèn bảng đơn giản
- find/replace
- print preview tốt hơn

---

## 20. Test matrix nên chuẩn bị

## 20.1. Functional

- tạo file mới rồi save `docx`
- mở `docx` có sẵn rồi sửa nội dung
- đổi font/cỡ/chữ đậm/nghiêng/gạch dưới
- căn lề trái/giữa/phải/đều
- bật bullet/number list
- save rồi mở lại vẫn giữ định dạng
- export PDF khớp nội dung
- in qua pipeline PDF hoạt động

## 20.2. Edge cases

- file đang bị khóa
- file read-only
- ổ đĩa hết dung lượng
- đường dẫn Unicode
- tên file rất dài
- LibreOffice chưa cài/chưa tải module
- process LibreOffice bị kill giữa lúc save

## 20.3. Cross-platform

- Windows 10/11
- macOS Intel/Apple Silicon nếu team Mac làm song song

---

## 21. Kết luận triển khai

Nếu mục tiêu là:

- thêm một trình soạn thảo văn bản cơ bản vào 3T Reader
- không cần đầy đủ như Word
- nhưng vẫn phải mở/lưu `docx` đáng tin

thì hướng đúng là:

> xây `Word Basic Mode` riêng, dùng LibreOffice làm engine thật qua bridge/session layer, và giữ UI tối giản theo đúng scope cơ bản.

Không nên đi theo hướng:

- chỉnh sửa trên PDF viewer
- hoặc lấy `QTextEdit` làm sản phẩm cuối

vì cả hai hướng đó sẽ sớm đụng trần chất lượng ở save/print/export.

---

## 22. Đề xuất chốt để bắt đầu

Nếu triển khai thật, tôi đề xuất chốt 6 điểm này ngay:

1. Phase đầu chỉ hỗ trợ `docx`
2. In đi qua export PDF tạm
3. Chưa làm preview realtime
4. Dùng LibreOffice service + UNO bridge
5. UI chỉ gồm nhóm File / Font / Paragraph / Page
6. Có autosave/recovery mức tối thiểu ngay từ bản đầu editor

---

## 23. File/code hiện tại đã được đối chiếu

Để tránh phân tích chung chung, phần trên dựa trên code hiện có ở repo này:

- [app/actions/document_converter.py](/C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/app/actions/document_converter.py)
- [app/actions/export.py](/C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/app/actions/export.py)
- [app/window.py](/C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/app/window.py)
- [packages/document_core/converter.py](/C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/packages/document_core/converter.py)

Nghĩa là:

- repo đã có nền `LibreOffice convert`
- đã có chấp nhận file Office ở mức open/view
- nhưng chưa có editor session/document model thật

Đó là khoảng trống chính cần xây.

## 6.3. Không nên làm ở phase đầu

- track changes
- comments kiểu Word thật
- section breaks phức tạp
- multi-column layout
- image wrapping phức tạp
- table editor sâu
- compatibility 100% với Word

---

## 7. Editor surface nên dùng gì

Đây là quyết định quan trọng nhất.

## Lựa chọn 1 — Qt text editor nâng cấp

Ví dụ:

- `QTextEdit` / `QTextDocument`

### Ưu điểm

- tích hợp UI nhanh
- chỉnh định dạng cơ bản khá dễ
- phù hợp với soạn thảo văn bản đơn giản

### Nhược điểm

- `QTextDocument` không phải DOCX engine chuẩn
- phải tự viết layer import/export DOCX
- save ra `docx` chuẩn sẽ yếu
- layout khác LibreOffice/Word

### Kết luận

Hợp nếu mục tiêu chỉ là editor nội bộ + xuất đơn giản.  
Không hợp nếu user kỳ vọng mở/lưu `docx` thật ổn định.

## Lựa chọn 2 — LibreOffice UNO bridge

### Ý tưởng

- chạy LibreOffice ở chế độ headless hoặc invisible service
- Python điều khiển document model qua UNO
- UI 3T Reader gửi lệnh xuống engine

### Ưu điểm

- dùng document model thật của LibreOffice
- mở/lưu `docx` đúng hơn nhiều
- export PDF tự nhiên
- formatting cơ bản đáng tin cậy hơn

### Nhược điểm

- bridge phức tạp hơn
- debugging khó hơn
- cần quản lý process/session LibreOffice cẩn thận

### Kết luận

**Nếu muốn support `docx` nghiêm túc, nên chọn hướng này.**

## Khuyến nghị cuối cùng

- **MVP nhanh:** có thể dùng `QTextEdit` nếu chỉ muốn proof-of-concept
- **Sản phẩm thật:** nên dùng **LibreOffice UNO bridge**

Vì user đang kỳ vọng “soạn Word cơ bản”, không phải “notepad rich text”.

---

## 8. Cách tích hợp vào 3T Reader

## 8.1. Khái niệm tab mới

Hiện app đang PDF-first.  
Cần thêm loại tab mới:

- `PdfTabState`
- `WordTabState`

`WordTabState` nên giữ:

- `source_path`
- `display_name`
- `temp_preview_pdf`
- `dirty`
- `word_session_id`
- `word_mode_state`

## 8.2. Menu / ribbon đề xuất

Thêm nhóm mới:

- `Tạo Word mới`
- `Mở Word`
- `Lưu`
- `Lưu thành`
- `Xuất PDF`
- `In`

Toolbar Word Basic:

- font
- size
- B / I / U
- color
- align left / center / right / justify
- bullets
- numbering
- line spacing

## 8.3. Chuyển chế độ xem

Một tài liệu Word nên có 2 kiểu nhìn:

1. **Editor View**
   - chỉnh sửa trực tiếp

2. **PDF Preview**
   - convert sang PDF tạm
   - xem đúng layout in

Điều này rất hợp với 3T Reader vì app vốn mạnh ở PDF preview.

---

## 9. Luồng người dùng đề xuất

## 9.1. Tạo Word mới

1. User bấm `Tạo Word mới`
2. App mở tab `Word Basic`
3. Tạo tài liệu mới trong session engine
4. User gõ nội dung
5. Save thành `.docx`

## 9.2. Mở `docx`

1. User mở `docx`
2. App tạo `WordTabState`
3. Engine mở file thật
4. Editor hiển thị nội dung
5. Có thể bấm `Xem PDF Preview`

## 9.3. Xuất PDF

1. User bấm `Xuất PDF`
2. Engine lưu `docx`
3. LibreOffice convert sang PDF
4. Mở PDF bằng viewer hiện có hoặc xuất file ra ngoài

---

## 10. Thiết kế module đề xuất

Các file nên thêm mới theo hướng hiện tại của repo:

### App layer

- `app/actions/word_basic.py`
  - entry points
  - create/open/save/export/print

- `app/word_basic_editor.py`
  - widget editor chính

- `app/word_toolbar.py`
  - toolbar controls riêng cho word basic

- `app/word_preview_dialog.py`
  - preview PDF nếu cần modal riêng

### Core / packages layer

- `packages/document_core/word_basic_session.py`
  - lifecycle session
  - dirty state
  - path management

- `packages/document_core/libreoffice_bridge.py`
  - gọi LibreOffice/UNO
  - create/open/save/format/export

- `packages/document_core/word_basic_export.py`
  - export PDF / in / preview

### Optional

- `packages/document_core/word_basic_commands.py`
  - command objects cho undo/redo nếu sau này cần

---

## 11. API chức năng nội bộ đề xuất

Ví dụ API Python:

```python
session = create_word_session()
session.open_docx(path)
session.set_text_style(bold=True, italic=False, underline=False)
session.set_font("Times New Roman", 12)
session.set_alignment("center")
session.insert_bullet_list()
session.set_line_spacing(1.5)
session.save()
session.save_as(new_path)
session.export_pdf(pdf_path)
```

Nếu dùng UNO bridge, các hàm trên sẽ map xuống thao tác document thật.

---

## 12. Hai cách triển khai thực tế

## Cách triển khai 1 — Làm MVP nhanh

### Mục tiêu

Chứng minh UX có hợp không, không đi sâu engine ngay.

### Làm bằng gì

- `QTextEdit`
- toolbar format cơ bản
- save thành HTML/ODT tạm hoặc thử `python-docx` cho output đơn giản

### Ưu điểm

- lên demo nhanh

### Nhược điểm

- không đại diện tốt cho `docx` thật
- bỏ đi khá nhiều khi nâng cấp

### Khi nào nên dùng

- chỉ để validate UX/product direction

## Cách triển khai 2 — Làm đúng sản phẩm

### Mục tiêu

Có thể ship cho user dùng thật.

### Làm bằng gì

- LibreOffice engine
- UNO bridge
- preview PDF bằng flow convert sẵn có

### Ưu điểm

- đúng hướng lâu dài

### Nhược điểm

- tốn công ngay từ đầu hơn

### Khi nào nên dùng

- khi đã xác định chắc chắn sẽ tích hợp Word Basic thật

## Khuyến nghị

Nếu bạn đã chắc là muốn đưa thành tính năng sản phẩm,  
**đừng làm MVP bằng editor giả quá lâu**.  
Nên đi thẳng theo **LibreOffice bridge**.

---

## 13. Rủi ro kỹ thuật phải chấp nhận trước

## 13.1. LibreOffice process lifecycle

Phải xử lý:

- khởi động chậm lần đầu
- profile tạm
- treo process
- timeout
- recover session lỗi

## 13.2. Đồng bộ UI và document thật

Nếu user chỉnh format liên tục:

- UI state phải phản ánh selection hiện tại
- không được lệch giữa toolbar và nội dung

## 13.3. Preview PDF không phải editor state tức thời

Nếu preview PDF là convert từ docx:

- preview có thể chậm hơn editor vài trăm ms tới vài giây
- cần cơ chế debounce/rebuild preview

## 13.4. Undo/redo

Nếu giao hết cho engine:

- UI phải hiểu khi nào trạng thái dirty thay đổi

## 13.5. Cross-platform

Repo đang hỗ trợ Win/Mac.  
Cần xác nhận:

- cách tìm `soffice`
- cách bundle LibreOffice module
- cách giao tiếp UNO
- path handling

---

## 14. Quyết định sản phẩm cần chốt trước khi code

Trước khi triển khai, cần chốt rõ:

1. Có chấp nhận thêm một tab editor riêng trong app không?
2. Có chấp nhận phụ thuộc mạnh hơn vào LibreOffice không?
3. Có cần hỗ trợ `doc` cũ hay chỉ `docx`?
4. Có cần save trực tiếp `docx` ngay phase đầu không?
5. Có cần preview PDF live không, hay chỉ export PDF khi user yêu cầu?

Khuyến nghị:

- chỉ hỗ trợ **`docx`** ở phase đầu
- save trực tiếp `docx`
- preview PDF theo nút hoặc debounce, không cần live từng ký tự

---

## 15. Lộ trình triển khai đề xuất

## Phase 1 — Word viewer + shell đúng kiến trúc

- tạo `WordTabState`
- mở `docx`
- convert sang PDF preview
- tab riêng cho Word
- create/open/save placeholder flow

**Mục tiêu:** cắm được editor mode vào app.

## Phase 2 — Basic editor formatting

- nhập text
- font / size / B / I / U / color
- align
- bullets / numbering
- line spacing
- save `docx`

**Mục tiêu:** đủ gọi là “Word cơ bản”.

## Phase 3 — Preview / export / print

- export PDF
- print
- preview PDF
- dirty state + reload preview

## Phase 4 — Chèn ảnh / bảng đơn giản

- insert image
- simple table
- margins / page setup

---

## 16. Khuyến nghị cuối cùng

Nếu mục tiêu của bạn là:

> “3T Reader có thể soạn thảo văn bản cơ bản như Word, không cần quá nhiều”

thì hướng đúng là:

### Quyết định chiến lược

- thêm **Word Basic Mode**
- dùng **LibreOffice làm engine**
- 3T Reader chỉ cung cấp **UI tối giản, rõ ràng, ổn định**

### Không nên làm

- nhét chỉnh sửa Word trực tiếp vào PDF viewer
- tự viết word processor hoàn chỉnh từ đầu

### Nên làm

- document engine thật ở dưới
- editor UI đơn giản ở trên
- PDF preview để tận dụng thế mạnh hiện có của 3T Reader

---

## 17. Đề xuất chốt scope để bắt đầu

Nếu bắt đầu ngay, mình đề xuất chốt scope v1 như sau:

- `Tạo Word mới`
- `Mở docx`
- `Soạn text cơ bản`
- `Font / size / B / I / U / color`
- `Align`
- `Bullet / numbering`
- `Spacing`
- `Save / Save As`
- `Xuất PDF`
- `In`

Đây là scope đủ nhỏ để làm thật, nhưng đủ rõ để user cảm thấy có giá trị.

---

## 18. Bước tiếp theo đề xuất

Nếu bạn quyết định đi tiếp, bước đúng tiếp theo là:

1. chốt scope v1 ở mục 17
2. chọn kiến trúc:
   - MVP giả lập
   - hay LibreOffice bridge làm thật
3. mình viết tiếp:
   - **spec kỹ thuật cấp module**
   - **sơ đồ file cần thêm/sửa**
   - **roadmap implementation theo phase**
   - **checklist test**

Khi đó mới nên bắt đầu code.
