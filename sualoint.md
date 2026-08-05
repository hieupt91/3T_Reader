# Quy trình sửa lỗi (bắt buộc tuân thủ cho mọi lỗi từ nay)

Bổ sung cho `FIX_RULES.md`, áp dụng thêm các yêu cầu sau cho từng lỗi:

1. **Đọc kỹ tính năng liên quan trước khi sửa** — đọc toàn bộ luồng code (UI trigger → action → write file → hiển thị lại) của đúng tính năng đang lỗi, không đoán.
2. **Chỉ sửa tập trung đúng lỗi đang báo** — không sửa lan man sang phần khác, không "tiện tay" refactor/cải tiến ngoài phạm vi lỗi.
3. **Không được để ảnh hưởng tính năng khác** — trước khi sửa phải liệt kê những chỗ dùng chung code/state với đoạn sắp sửa (nếu có), sửa xong phải xác nhận các chỗ dùng chung đó vẫn đúng.
4. **Rà soát tránh chồng code / xung đột** trước khi sửa:
   - `git status` + `git diff` xem có thay đổi chưa commit nào ở đúng vùng code sắp sửa không (tránh đè lên việc đang làm dở).
   - Kiểm tra file/hàm sắp sửa có đang được sửa trùng ở nhánh khác gần đây không (`git log -- <file>`).
5. **Test trước khi commit**:
   - Chạy lại đúng kịch bản lỗi để xác nhận hết lỗi.
   - Chạy `pytest tests/` toàn bộ, đối chiếu số lượng fail với baseline trước khi sửa (fail mới phát sinh do mình gây ra thì phải sửa tiếp, fail có sẵn từ trước thì ghi rõ là pre-existing).
6. **Không tự commit** — mặc định để người dùng xem qua rồi tự quyết định, trừ khi được yêu cầu rõ ràng.
7. **Báo cáo sau mỗi lỗi**: đã sửa file nào, phạm vi ảnh hưởng, đã kiểm tra gì, còn nghi vấn gì chưa chắc chắn (nếu có, phải hỏi lại trước khi đoán bừa).

Mọi lỗi tiếp theo trong phiên làm việc này đều xử lý theo đúng quy trình trên.

---

## Lỗi 1: Xoay trang bị sai — trang hiển thị ngược (upside-down)

**Trạng thái: ĐANG ĐIỀU TRA — chưa đủ căn cứ để sửa, cần bạn xác nhận thêm trước khi động vào code (theo mục 1-2 ở trên, tránh sửa bừa).**

### Đã xác minh bằng code/kiểm tra thực tế (không suy đoán)

File trong ảnh chụp màn hình: `C:/Users/HieuPC/Desktop/Hiếu/BAN_MO_TA_PHAN_MEM_signed_signed_signed_signed_gop_signed_signed.pdf` (lấy từ danh sách "recent" của app đang chạy).

Đọc trực tiếp `/Rotate` từng trang bằng pikepdf trên file thật:

| Trang | /Rotate (lưu trong file) | MediaBox |
|---|---|---|
| 1 | 0 | 612×792 (Letter) |
| 2 | **180** | 595.28×841.89 (A4) |
| 3 | **90** | 595.28×841.89 (A4) |
| 4 | 0 | 595.28×841.89 (A4) |
| 5 | 0 | 595.28×841.89 (A4) |

→ **Đây là lỗi đã ghi thật xuống đĩa** (không phải chỉ lỗi hiển thị CSS tạm thời trong PDF.js). Trang 2 hiện đang bị ngược 180°, đúng như ảnh chụp màn hình.

MediaBox khác nhau giữa trang 1 (Letter) và trang 2-5 (A4) xác nhận đây là tài liệu **đã ghép (gộp) từ nhiều nguồn khác nhau** — khớp tên file có "_gop_".

### Các nghi vấn đã KIỂM TRA và LOẠI TRỪ (không phải nguyên nhân)

Đọc toàn bộ luồng code tính năng "Xoay trang" gồm 2 UX riêng biệt:
- Xoay nhanh 1-click: `rotate_page_cw`/`rotate_page_ccw` → `_rotate_page()` (`app/actions/annotate.py:2696-2806`) — dùng CSS Transform hiển thị tức thì + ghi `/Rotate` ngầm bằng thread riêng.
- Dialog "Xoay trang...": `rotate_pages_action()` (`app/actions/pages.py:286+`) — cùng cơ chế CSS Transform, xoay 1 trang hoặc toàn bộ.

Đã loại trừ:
1. **Toán học xoay sai** — `(current_rot + degrees) % 360` đúng, 1 click = +90/-90, không tự nhân đôi.
2. **Race điều kiện ghi đè khi bấm nhanh 2 lần** — `pdf_write_slot()` (`app/actions/_pdf_save.py:339`) serialize đúng theo path, không có chuyện 2 luồng ghi đồng thời đọc trùng giá trị cũ.
3. **Double-connect signal nút xoay** — đã grep toàn bộ nơi gọi `rotate_page_cw`/`rotate_page_ccw`: ribbon button (`window.py:881-882`), menu "Trang" (`window.py:1977-1984`, phím tắt `Ctrl+]`/`Ctrl+[`), và context-menu chuột phải trên sidebar (`window.py:2368-2370`) — 3 nơi gọi độc lập, mỗi nơi connect đúng 1 lần, không trùng.
4. **Đọc sai "trang hiện tại" khi xoay từ menu chuột phải sidebar** — `goto_page()` (`app/pdf_viewer.py:592`) set `self._current_page` **đồng bộ** trước khi bắn JS, nên `_get_current_page()` đọc đúng trang vừa right-click, không bị lệch do JS async.
5. **Hàm Ghép PDF (gop) đụng vào /Rotate** — grep `app/actions/pages.py` không có dòng nào xử lý `/Rotate` trong luồng merge; pikepdf copy trang giữ nguyên `/Rotate` gốc của trang nguồn, không có logic tự ý đổi.

### Còn lại — chưa xác định được nguyên nhân vì thiếu dữ kiện

Không tìm thấy bug rõ ràng trong code khiến 1 lần bấm xoay tự nhân đôi hoặc lệch trang. Hai khả năng còn lại, cả hai đều **không nên đoán mà cần bạn xác nhận**:

- (a) `/Rotate=180`/`90` này là **do bạn đã bấm xoay nhiều lần** trên đúng 2 trang này trong các lần test trước (file đã qua rất nhiều thao tác: ghép + ký 5 lần) — nếu vậy đây không phải bug, hành vi ghi đúng như đã bấm.
- (b) `/Rotate=180`/`90` này **đã có sẵn từ tài liệu nguồn trước khi ghép** (trang scan gốc vốn bị ngược) — nếu vậy đây là vấn đề của tài liệu nguồn / tính năng Ghép PDF chưa tự-chuẩn-hoá hướng trang khi ghép (là 1 feature request, không phải bug của tính năng Xoay).

**Cần bạn trả lời để đi tiếp đúng hướng, tránh sửa sai chỗ:**
1. Bạn có nhớ đã bấm nút xoay (nhanh 1-click hay dialog "Xoay trang...") trên trang 2/3 của đúng file này trước đó không?
2. Lỗi có tái hiện được trên 1 file PDF mới, đơn giản (chưa qua ghép/ký) không — mở file mới, bấm xoay phải đúng 1 lần trên 1 trang, có bị ngược 180° ngay không?
3. Nếu không nhớ/không tái hiện được — có thể cho tôi 1 file PDF gốc (chưa xoay, chưa ghép) để tôi tự bấm xoay thử và bắt lỗi trực tiếp không?

### Trả lời của người dùng (2026-08-04)

- Câu 1: **"Từng bấm xoay trước đó"** trên đúng file này.
- Câu 2: yêu cầu tôi tự test trên app rồi báo lại.

### Đã tự test trực tiếp trên app thật (không đoán)

Tạo file PDF mới 3 trang, `/Rotate=0` cả 3 trang (`pikepdf.new()`). Mở file này trong app thật đang chạy, dùng `pywinauto` gửi đúng 1 lần phím tắt **Ctrl+]** ("Xoay phải 90°" — đúng đường menu/shortcut thật, không gọi tắt qua code). Đợi luồng ghi ngầm xong, đọc lại `/Rotate` bằng pikepdf:

| Trang | /Rotate sau 1 lần Ctrl+] |
|---|---|
| 1 | **90** ✅ đúng |
| 2 | 0 |
| 3 | 0 |

→ **1 lần bấm cho đúng 1 lần xoay 90°, không tự nhân đôi, không lệch trang.** Không tái hiện được lỗi trên file đơn giản, tính năng xoay nhanh hoạt động đúng trong test này.

### Kết luận Lỗi 1

Kết hợp: (a) tính năng xoay hoạt động đúng khi test độc lập, và (b) bạn xác nhận đã từng bấm xoay trên đúng trang 2/3 của file đó trước đây → **`/Rotate=180` ở trang 2 và `/Rotate=90` ở trang 3 nhiều khả năng là kết quả đúng của các lần bấm trước đó của bạn (có thể trang 2 đã bấm 2 lần), không phải bug trong code xoay trang hiện tại.**

**Không sửa code** cho lỗi này — theo đúng quy tắc "không sửa lan man" ở đầu file, không có bằng chứng code sai để sửa. Nếu bạn muốn trang 2 quay lại đúng chiều, chỉ cần mở file đó và bấm xoay thêm 180° (2 lần Ctrl+]) trên trang 2 — không cần sửa code.

Nếu sau này bạn phát hiện lại đúng hiện tượng này (1 lần bấm ra 180°) trên 1 file cụ thể, báo lại kèm đúng file đó để tôi bắt tận nơi — test ở trên chỉ chứng minh feature *có thể* đúng, không loại trừ 100% một edge case hiếm (ví dụ trang có /Rotate lạ sẵn từ nguồn, hoặc thao tác kết hợp với tính năng khác) mà tôi chưa tái hiện được.

### Phát hiện phụ (ngoài phạm vi lỗi này) — App CRASH khi test

Trong lúc test, app bị **crash 3 lần** (`app_log.txt`, faulthandler): `Fatal Python error: Aborted` và 1 lần `Windows fatal exception: access violation`, không có Python traceback (crash ở tầng native, faulthandler chỉ bắt được main thread). Ghi nhận sơ bộ:
- Crash 1: xảy ra khi mở thêm 1 file mới vào cửa sổ đang có sẵn tài liệu 5 trang (single-instance forward file trong lúc thumbnail/tab cũ có thể chưa rảnh) — giống dạng lỗi đã có audit note trước đây (thumbnail đang render nền + ghi/mở file khác).
- Mở lại với đúng 1 file, cửa sổ rảnh hoàn toàn → mở file mới ổn định, không crash.
- Crash lần 3: xảy ra sau khi gửi Ctrl+] xoay trang (đã đọc được kết quả /Rotate đúng trước khi tiến trình chết) — chưa rõ crash có liên quan trực tiếp đến thao tác xoay hay là timing ngẫu nhiên khác.

**Chưa điều tra kỹ, chưa sửa** — đây là lỗi khác (ổn định ứng dụng), không phải lỗi xoay trang đang xử lý. Cần bạn xác nhận có muốn mở thành "Lỗi 2" riêng để điều tra kỹ theo đúng quy trình ở đầu file không, vì đây có thể là vấn đề nghiêm trọng (crash mất dữ liệu tiềm ẩn).

---

## Lỗi 2: App crash (access violation / Aborted) khi thao tác trong lúc thumbnail đang tải nền

**Trạng thái: ĐÃ ĐIỀU TRA — chưa tìm ra nguyên nhân gốc chắc chắn, chưa sửa (không đoán bừa theo đúng quy tắc).**

### Đã đọc kỹ code liên quan

- `app/sidebar.py` — `ThumbnailSidebar` là **1 widget dùng chung cho cả cửa sổ** (không phải mỗi tab một sidebar riêng). Mỗi lần mở tab mới/chuyển tab, `load_thumbnails()` gọi `self._loader.requestInterruption()` cho loader cũ rồi tạo loader mới ngay — **không `join()`/chờ loader cũ dừng hẳn**, nên có khoảng thời gian 2 `ThumbnailLoader` (2 thread) có thể cùng hoạt động.
- `packages/pdf_engine/pdfium_engine.py` — đã có sẵn `PDFIUM_LOCK` (threading.RLock) đúng như comment mô tả: "PDFium không thread-safe... đã tái hiện 3/3 lần: luồng ThumbnailLoader render thumbnail đụng luồng auto-OCR đọc cùng lúc." Đã grep toàn bộ 15 file gọi `pypdfium2` trực tiếp trong repo (annotate.py, edit.py, document_ops.py, auto_ocr.py, chat_pdf.py, converter.py, semantic_search.py, tts_dialog.py, ocr/engine.py, ai_summarize_dialog.py) — **tất cả đều bọc đúng trong `with PDFIUM_LOCK:`**, kể cả các lệnh render/close theo sau, không thấy chỗ nào thiếu lock.

### Đã tự tái hiện crash thật (3 lần, ghi nhận trong `app_log.txt`)

1. Mở file A (5 trang, có chữ ký số) → forward mở ngay file B vào cùng cửa sổ trong lúc A có thể chưa tải xong thumbnail → **crash "Windows fatal exception: access violation"**.
2. Mở lại app, đợi ổn định (không tài liệu) rồi mở 1 file mới → **không crash** (mở bình thường).
3. Trên cửa sổ đang mở ổn định, gửi 1 lần Ctrl+] (xoay trang) → đọc được `/Rotate` đúng ngay sau đó, nhưng tiến trình **crash "Fatal Python error: Aborted"** ngay sau (chưa rõ có phải do chính thao tác xoay hay không).

### Đã kiểm tra và LOẠI TRỪ được nghi vấn chính (bằng test thực nghiệm, không đoán)

Viết script độc lập cho 2 thread cùng lặp mở/render toàn bộ trang/đóng 2 file PDF khác nhau qua đúng `PdfiumEngine` (60 vòng lặp mỗi thread, chạy song song) — **0 lỗi, 0 crash**. Vậy giả thuyết "2 luồng cùng gọi pypdfium2 qua engine có khóa là nguyên nhân" **bị loại trừ bằng thực nghiệm** — khóa `PDFIUM_LOCK` hoạt động đúng cho đúng luồng gọi này.

### Kết luận

Không xác định được nguyên nhân gốc trong phạm vi thời gian điều tra hợp lý. Đây là crash native (access violation / Aborted, không có Python traceback vì faulthandler chỉ bắt main thread — cố ý tắt `all_threads=True` do rủi ro khác, xem comment trong `main.py`), khả năng cao liên quan tới 1 trong các vùng KHÔNG được phủ bởi `PDFIUM_LOCK`: thao tác Qt (QIcon/QPixmap xoay trong `_rotate_page`, dòng 2756-2772 `app/actions/annotate.py`), tương tác giữa QWebEngineView và pikepdf ghi file nền, hoặc race giữa `ThumbnailLoader` cũ chưa kịp dừng hẳn và tab mới — nhưng **chưa có bằng chứng thực nghiệm xác nhận**, nên **không sửa** để tránh vá sai chỗ.

**Đề xuất bước tiếp theo (cần bạn quyết, không tự làm vì tốn nhiều thời gian hơn)**:
1. Theo dõi thêm: nếu crash tái diễn, giữ nguyên `app_log.txt`/`crash_log.txt` lúc đó và báo ngay kèm thao tác vừa làm trước khi crash.
2. Muốn điều tra sâu hơn cần công cụ ngoài phạm vi hiện tại: gắn WinDbg/Visual Studio debugger vào tiến trình để lấy stack trace native thật (faulthandler hiện không đủ), hoặc build bản debug PySide6.
3. Cân nhắc bật tạm `all_threads=True` cho faulthandler ở bản test riêng (không phải bản chạy thật cho user) để lấy thêm thông tin luồng nào crash — chưa làm vì cần bạn xác nhận đây có phải hướng bạn muốn đầu tư tiếp không.

### Đã thử thêm (theo yêu cầu "làm cho xong") — vẫn KHÔNG tìm ra được, đã revert code debug

Đã bật tạm `all_threads=True` trong `main.py` (chỉ để chẩn đoán, không phải bản chạy thật) rồi thử tái hiện lại nhiều lần:
- Mở nhiều file dồn dập cùng lúc vào 1 cửa sổ (7 tiến trình `main.py` chạy song song) — **không crash** lần này (race không phải lúc nào cũng trúng).
- Bấm dồn dập 6 lần Ctrl+] liên tiếp — **không crash**, `/Rotate` cộng dồn đúng (540 % 360 = 180, khớp).
- Sau đó app **crash lần nữa** trong lúc đang đọc file từ tiến trình ngoài (tái hiện đúng thao tác đã crash lần trước) — nhưng lần này **kể cả với `all_threads=True`, `app_log.txt` không ghi được gì cả** (0 dòng mới), không có "Fatal Python error", không có access violation nào được faulthandler bắt. Tiến trình chỉ đơn giản biến mất đột ngột.

**Diễn giải**: 1 fault handler không bắt được gì kể cả khi bật hết các luồng thường chỉ xảy ra với: stack overflow sâu (Windows fault handler của Python không luôn bắt được loại này), hoặc tiến trình bị hệ điều hành/phần mềm khác kill từ ngoài (không phải lỗi logic bên trong code Python/Qt của app). Đây **không phải một lỗi có thể sửa bằng cách đọc code** — cần công cụ debug ở tầng hệ điều hành (WinDbg) mà máy hiện chưa cài (`cdb.exe` không có), nằm ngoài khả năng xử lý trong phiên làm việc này.

**Đã revert `main.py` về đúng `all_threads=False` như code gốc** (không để lại thay đổi debug). Dừng điều tra Lỗi 2 tại đây — không có gì để sửa/test được, cần công cụ khác hoặc theo dõi thêm khi tái diễn ngoài đời thật.

### THEO DÕI (chưa đóng) — cần ghi lại mỗi lần tái diễn

Từ nay, mỗi lần crash "Fatal Python error: Aborted" / "Windows fatal exception: access violation" xuất hiện (kể cả trong lúc tôi tự test hay trong lúc bạn dùng thật), ghi 1 dòng vào bảng dưới đây kèm: ngày giờ, đang làm thao tác gì ngay trước đó, số dòng mới trong `app_log.txt` lúc đó. Đủ dữ liệu để tìm quy luật thay vì đoán.

| Ngày giờ | Thao tác ngay trước khi crash | Có log trong app_log.txt không |
|---|---|---|
| 2026-08-04 ~12:09 | Forward mở file mới vào cửa sổ đang có tài liệu 5 trang, có thể đang tải thumbnail | Có — "Windows fatal exception: access violation" |
| 2026-08-04 ~12:32 | Vừa gửi Ctrl+] xoay trang xong | Có — "Fatal Python error: Aborted" |
| 2026-08-04 ~13:0x | Tiến trình ngoài (pikepdf) đọc file trong lúc app có thể đang ghi ngầm sau rotate | **Không** — kể cả bật `all_threads=True` cũng không ghi được gì |
| 2026-08-04 ~15:3x | Vừa tạo Ô ký số (Sig field) → Ctrl+S lưu → click liên tục qua UI Automation ngay sau | Có — nhiều dòng "code 0x8001010d" (không tử vong) rồi cuối cùng "Fatal Python error: Aborted" (tử vong). File đã lưu đúng trước khi crash, không mất dữ liệu (đã xác nhận field Signature lưu đúng vào AcroForm) |

### ĐÀO SÂU (2026-08-04, buổi chiều) — TÌM RA NGUỒN GỐC CHÍNH XÁC qua Windows Event Log, không cần WinDbg

Không có `cdb.exe`/WinDbg, nhưng Windows tự ghi chi tiết crash native vào **Event Viewer → Application log** (Event ID 1000, "Windows Error Reporting") mà không cần cài thêm gì. Đọc bằng PowerShell (`Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000}`) ra thông tin mà `app_log.txt` không có được.

**Kết quả — đây là phát hiện quan trọng nhất trong toàn bộ quá trình điều tra:**

1. **Không phải lỗi mới, không phải do tôi test** — cùng 1 chữ ký crash xuất hiện **93 lần**, trải dài từ **22/05/2026 đến hôm nay 04/08/2026** (>2.5 tháng), qua **3 môi trường Python khác nhau** (`.venv`, `.venv313`, `miniconda3`) và **2 phiên bản Qt6Core.dll** (6.11.0.0 và 6.11.1.0). Đỉnh điểm 08-13/06/2026 (65 lần trong chưa đầy 1 tuần), sau đó thưa dần (1-3 lần/ngày có crash) nhưng chưa bao giờ hết hẳn.
2. **Luôn crash tại đúng 1 chỗ**: `Exception code: 0xc0000409` (STATUS_STACK_BUFFER_OVERRUN / Windows `__fastfail`), `Faulting module: Qt6Core.dll`, `Fault offset: 0x1cf68` — **giống hệt nhau ở mọi lần**, không lệch 1 byte.
3. **Đã xác định được tên hàm bị crash** bằng cách đọc bảng export của `Qt6Core.dll` (`pefile`, không cần WinDbg): offset `0x1cf68` nằm ngay sau hàm `QtPrivate::sizedFree(void*, unsigned __int64)` (bắt đầu tại `0x1cf10`) và trước `qBadAlloc` (tại `0x1cf80`) — tức **crash xảy ra bên trong `QtPrivate::sizedFree`, hàm giải phóng bộ nhớ nội bộ của Qt** (dùng bởi các container như QString/QList/QByteArray).
4. **Ý nghĩa kỹ thuật**: crash bên trong 1 hàm `free()` với mã lỗi "stack buffer overrun/fastfail" gần như chắc chắn là **heap corruption bị phát hiện muộn** — tức có chỗ khác trong chương trình ghi đè ra ngoài vùng nhớ đã cấp phát (buffer overrun/use-after-free/double-free), Windows Heap chỉ phát hiện ra khi Qt gọi free() ở đây, không phải lỗi nằm ở chính dòng code này.
5. **Khớp với nghi vấn đã có sẵn trong code** — comment ở `main.py` (dòng cài faulthandler) đã ghi rõ: *"all_threads=True sẽ khiến SIGSEGV ở QThread (do PySide6 GC race condition) lan ra"* — tức đội ngũ trước đây **đã từng nghi ngờ đúng loại lỗi này** (race điều kiện giữa Python garbage collector và vòng đời object C++ của Qt/PySide6), chỉ chưa có bằng chứng cụ thể để xác nhận. Phát hiện hôm nay (`sizedFree` + heap corruption) **khớp hoàn toàn** với giả thuyết GC-race đó.

**Kết luận: đây rất có khả năng là lỗi trong chính PySide6/Qt (hoặc phần tương tác giữa Python GC và Qt C++ object lifecycle), không phải lỗi trong code Python của 3T Reader.** Không có dòng code nào của app xuất hiện trong toàn bộ chuỗi lỗi — không có Python traceback ở bất kỳ lần crash nào trong 93 lần.

**Đề xuất hướng xử lý tiếp theo (ngoài khả năng "sửa code app" thông thường)**:
1. Tìm trên trình theo dõi lỗi chính thức của Qt (`bugreports.qt.io`) và PySide (`bugreports.qt.io/projects/PYSIDE` hoặc `github.com/pyside/pyside-setup`) với từ khóa `sizedFree`, `0xc0000409`, hoặc mô tả "Qt6Core crash on Windows during accessibility/GC" — khả năng cao đã có người báo lỗi tương tự với PySide6 6.11.x trên Windows.
2. Thử đổi phiên bản PySide6 (lên bản mới hơn nếu có, hoặc xuống 1 bản LTS trước đó) — vì lỗi giữ nguyên qua 6.11.0.0 → 6.11.1.0 (bản vá nhỏ không đổi được), có thể cần đổi bản lớn hơn mới né được đúng đoạn code lỗi.
3. Nếu muốn điều tra tới cùng: cần **Application Verifier** (`verifier.exe`, có sẵn trong Windows, không cần cài thêm) bật chế độ "page heap" cho `python.exe` để bắt lỗi ngay tại chỗ ghi đè bộ nhớ (thay vì muộn tại `sizedFree`) — nhưng vẫn cần WinDbg hoặc debugger tương đương để đọc kết quả, việc này vượt phạm vi phiên làm việc hiện tại.
4. Việc thưa dần từ giữa tháng 6 (có thể trùng với 1 fix nào đó đã làm trước đây) gợi ý: rà lại lịch sử commit quanh 13-19/06/2026 xem có thay đổi nào liên quan tới quản lý vòng đời QObject/QThread không — nếu có, hướng đó đã đúng nhưng chưa triệt để.

**→ Đã rà `git log`, tìm được đúng 3 commit khớp hoàn toàn với mốc thời gian crash giảm mạnh (từ 8-18 lần/ngày xuống 0-3 lần/ngày, tất cả đúng ngày 16/06/2026):**

| Commit | Ngày giờ | Nội dung |
|---|---|---|
| `5406a2c` | 2026-06-16 08:49 | fix: rotation crash by converting Signature widgets to Stamps |
| `2db47ca` | 2026-06-16 09:47 | fix: resolve rapid rotation crash and instant thumbnail preview aspect ratio |
| `bcf90a2` | 2026-06-16 14:25 | perf: implement aggressive garbage collection and QWebEngine profile cache clearing on tab close to prevent memory leaks |
| `bf2c762` | 2026-06-19 13:53 | fix: resolve QUnifiedTimer segmentation fault on dialog close by gracefully stopping background thread |

**Đây gần như chắc chắn chính là các fix đã dập phần lớn (nhưng không phải toàn bộ) nguồn gây crash `sizedFree`** — 3/4 commit nhắm đúng vào "rotation crash" + "Signature widget" + "GC", khớp 100% với giả thuyết heap-corruption-do-GC-race ở trên. **Rất đáng chú ý**: cả 3 lần tôi tự tái hiện crash hôm nay đều xảy ra ngay sau đúng nhóm thao tác này — (1) forward mở file lúc đang tải thumbnail, (2) ngay sau `Ctrl+]` xoay trang, (3) ngay sau khi tạo Ô ký số — tức **phần "đuôi" chưa dập hết của đúng nhóm lỗi rotation/signature/thumbnail mà đội đã từng sửa dở**, không phải lỗi mới hoàn toàn.

**Khuyến nghị cụ thể nhất**: đọc lại kỹ nội dung đầy đủ 4 commit trên (đặc biệt `2db47ca` và `bcf90a2`) để hiểu chính xác cơ chế GC/thread-lifecycle đã áp dụng, rồi tìm xem còn code path rotation/signature/thumbnail nào KHÔNG đi qua cơ chế dọn dẹp đó không — nhiều khả năng chính là chỗ còn sót.

**Đã tự kiểm tra thêm 1 bước**: đọc diff đầy đủ của `bcf90a2` — `gc.collect()` chủ động chỉ được gọi tại **thời điểm đóng tab** (`app/window.py`, +15 dòng). Crash #1 của tôi hôm nay xảy ra lúc **mở thêm file mới vào cửa sổ đang có tab khác tải thumbnail** — không phải lúc đóng tab — nên **rất có thể nằm ngoài phạm vi fix `bcf90a2` che phủ**. Đây là gợi ý cụ thể nhất cho hướng sửa tiếp: cân nhắc áp dụng cơ chế dọn dẹp GC/thread tương tự cho luồng **mở tab mới** (không chỉ đóng tab), đặc biệt khi có `ThumbnailLoader` của tab khác đang chạy nền tại thời điểm đó — khớp đúng với comment cảnh báo đã có sẵn trong `app/actions/auto_ocr.py` (dòng ~172) về rủi ro access-violation khi `ThumbnailLoader` cũ chưa kịp dừng lúc file bị thay đổi.

**Lưu ý quan trọng**: đây là suy luận có căn cứ mạnh (khớp thời gian, khớp hàm, khớp comment cảnh báo có sẵn), nhưng **chưa phải bằng chứng chứng minh 100%** — chưa có debugger đọc được stack trace thật tại đúng thời điểm ghi đè bộ nhớ.

### ĐÃ THỬ ÁP DỤNG MITIGATION (2026-08-04, theo quyết định của bạn) — chưa phải bằng chứng 100% đã hết, cần theo dõi thêm

**Đã tìm thêm bằng chứng ngoài cộng đồng** (WebSearch) xác nhận đây đúng là lỗi kinh điển đã biết của PyQt/PySide trên Windows: CPython cyclic GC có thể tự chạy trên **bất kỳ thread nào** khi ngưỡng phân bổ bị vượt; nếu đúng lúc đó nó hủy 1 object Qt từ thread không phải chủ sở hữu, việc đó không an toàn với Qt → hỏng heap. Có hẳn 1 package cộng đồng (`qtpygc`) chuyên vá lỗi này bằng cách: tắt auto-GC, tự `gc.collect()` định kỳ CHỈ từ main/GUI thread. PySide6 6.11 (đúng bản project đang dùng) có thêm cơ chế "defer deletion" (PYSIDE-3288) nhưng đó là cho việc XÓA QObject cụ thể — crash của mình lại nằm trong `sizedFree` (giải phóng bộ nhớ container chung), nên khả năng cao KHÔNG được PYSIDE-3288 che phủ hết.

**Đã áp dụng đúng pattern `qtpygc`** (không cài package ngoài, không phát sinh license mới — chỉ dùng module `gc` chuẩn của Python):
- `main.py`: thêm `gc.disable()` ngay sau `_install_crash_logging()`, trước khi tạo `QApplication` — tắt hẳn việc GC tự kích hoạt ngẫu nhiên trên bất kỳ thread nào.
- `app/window.py`: thêm `PDFReaderApp._start_gc_timer()` — 1 `QTimer` chạy trên main thread, gọi `gc.collect()` mỗi 10 giây, gọi trong `__init__` cạnh `_start_token_monitor()`. Các lời gọi `gc.collect()` thủ công có sẵn (lúc đóng tab, lúc in) vẫn giữ nguyên, không đổi gì — giờ chỉ là thêm 1 lớp bảo hiểm định kỳ.

**Phạm vi ảnh hưởng**: thay đổi hành vi quản lý bộ nhớ của TOÀN BỘ app (không phải 1 tính năng riêng lẻ) — đây là lý do đã hỏi ý kiến bạn trước khi làm thay vì tự quyết.

**Đã kiểm tra**:
- `pytest tests/` toàn bộ: 328 pass / 3 fail — đúng baseline, không đổi.
- Test trên app thật: mở app bình thường, không lỗi khi khởi động với `gc.disable()`.
- **Test dồn dập lại đúng 3 kịch bản đã từng crash trong phiên hôm nay**: (1) forward 15 lần mở file dồn dập vào cửa sổ đang tải thumbnail (5 vòng × 3 file liên tiếp), (2) bấm dồn dập 10 lần `Ctrl+]` xoay trang liên tiếp, (3) tổ hợp UI Automation click liên tục — **0 crash trong `app_log.txt`, 0 crash trong Windows Event Log** suốt ~20 phút test liên tục.
- RAM ổn định trong phạm vi hợp lý cho số tab đã mở (344MB → 606MB sau khi mở nhiều tab, không thấy tăng bất thường/không kiểm soát).

**Chưa commit** (mặc định theo `sualoint.md`/`FIX_RULES.md`) — đây là thay đổi ảnh hưởng rộng, nên để bạn xem qua trước khi quyết định commit.

**QUAN TRỌNG — giới hạn của kết quả test này**: crash gốc vốn đã HIẾM (93 lần trải trong 2.5 tháng, không phải crash mỗi lần thao tác) — 20 phút không crash là **tín hiệu tốt, không phải bằng chứng đã hết lỗi**. Cần theo dõi thực tế qua nhiều ngày/tuần sử dụng thật mới kết luận chắc chắn được. Nếu crash `sizedFree`/`0x8001010d` tái diễn sau khi đã áp dụng fix này, ghi tiếp vào bảng theo dõi bên trên — lúc đó mới đủ cơ sở kết luận fix có tác dụng hay không.

### Tổng kết những gì sẵn sàng để bạn test

- **Lỗi 0 (chú thích tự lưu báo sai khi chỉ đọc)** — đã sửa (`app/actions/annotate.py`, `app/actions/auto_ocr.py`, `app/window.py`), đã test pass, **sẵn sàng để bạn test lại trên app thật**.
- **Lỗi 1 (xoay trang)** — không phải bug, không có code nào thay đổi.
- **Lỗi 2 (crash)** — đã thử áp dụng mitigation (tắt auto-GC + gc.collect định kỳ trên main thread), test dồn dập 20 phút không tái hiện được crash, nhưng **cần theo dõi thực tế lâu dài mới xác nhận chắc chắn** — chưa thể coi là "đã sửa xong" theo đúng nghĩa.

---

## Lỗi 3: "Sửa text gốc" — chữ thay thế chồng lấn mất khả năng đọc khi dài hơn vùng che

**Nguồn phát hiện**: `docs/QA_UX_FINAL_REVIEW_2026-08-04.md`, mục UX #1 (vòng rà soát QA/UX cuối cùng).

**Trạng thái: ĐÃ SỬA, đã test kỹ qua 4 vòng lặp trên app thật — sẵn sàng để bạn test lại.**

### Hiện tượng gốc

Dùng "Sửa text gốc" thay "original text" (13 ký tự) bằng "REPLACEDFINAL" (14 ký tự, chỉ dài hơn 1 ký tự) — chữ mới đè lên phần văn bản còn lại phía sau ("edited later."), tạo dòng chữ chồng lẫn **không đọc được**: "REPLACEDfdMAledited".

### Nguyên nhân (đọc code xác nhận, `app/actions/edit.py`, hàm `on_click` trong `edit_text_object`)

Hàm `_expanded_text_box()` (có sẵn từ trước) đã tính toán mở rộng vùng ĐẶT chữ mới (`text_box`/`insert_box`) theo đúng bề rộng ước tính của chữ thay thế — nhưng vùng CHE chữ cũ (`redact_box` tô màu nền cho trang vector, hoặc miếng vá ảnh `patch_box` cho trang scan) **không được mở rộng theo**, vẫn giữ nguyên kích thước của vùng bôi đen gốc. Kết quả: phần chữ mới vượt ra ngoài vùng che sẽ đè trực tiếp lên nội dung cũ chưa bị xoá ở phía sau, chưa kể chữ cũ đó cũng chưa được che nên vẫn hiển thị — 2 lớp chữ chồng lên nhau.

### Đã thử 3 hướng, chọn hướng an toàn nhất sau khi test thực nghiệm phát hiện tác dụng phụ

1. **Hướng 1 (bỏ)**: mở rộng `redact_box` khớp đúng `text_box` đã tính — hết chồng chữ nhưng còn sót 1 vệt glyph vỡ ở đúng mép do công thức ước lượng bề rộng (`len(text)*font_size*0.62`) hụt so với bề rộng thật của chuỗi toàn chữ hoa (đo thực nghiệm: "REPLACEDFINAL" 14pt ước lượng 112.84pt, thật 115.14pt).
2. **Hướng 2 (bỏ)**: thêm khoảng đệm an toàn tỉ lệ theo độ dài chuỗi vào mép phải vùng che — hết vệt glyph vỡ, NHƯNG mở rộng đủ lớn để che đúng bắt đầu **ăn lấn vào nội dung liền sau mà người dùng không hề chọn để sửa** (test cho thấy chữ "e" đầu từ "edited" bị xoá mất, thành "dited") — tuy nhìn "sạch" hơn nhưng thực chất **làm mất nội dung không được yêu cầu sửa**, một dạng lỗi nghiêm trọng hơn (âm thầm sai lệch nội dung) so với lỗi chồng chữ (lộ liễu, dễ nhận ra ngay).
3. **Hướng 3 (ĐÃ CHỌN, đúng như đề xuất ban đầu trong `QA_UX_FINAL_REVIEW`)**: PDF không tự dàn lại dòng, nên **ưu tiên co cỡ chữ thay thế lại cho vừa đúng vùng đã bôi đen** (giữ sàn tối thiểu 55% cỡ chữ gốc để còn đọc được) thay vì mở rộng vùng che. Chỉ khi co tới sàn vẫn không đủ chỗ (chữ thay thế quá dài) mới cho phép mở rộng vùng che ra ngoài như phương án cuối (kèm đệm an toàn của Hướng 2) — trường hợp này chấp nhận đè nhẹ lên nội dung liền sau vì không còn lựa chọn nào khác để tránh chồng chữ hoàn toàn không đọc được.

### Đã sửa

`app/actions/edit.py`, trong `on_click()` (hàm lồng bên trong `edit_text_object`), thêm logic ngay sau khi có `text_value`, TRƯỚC khi build `patch_info`/tô màu nền: so `available_width` (bề rộng vùng đã chọn, đo thật) với `estimated_width` (bề rộng ước tính của chữ thay thế) — nếu vượt, co `font_size` theo tỉ lệ (sàn 55%); sau đó mới gọi `_expanded_text_box()` như cũ; nếu ngay cả ở sàn vẫn không đủ chỗ, mới mở rộng `redact_box` kèm đệm an toàn.

### Phạm vi ảnh hưởng

Chỉ đổi hành vi khi chữ thay thế **rộng hơn** vùng đã chọn ở cỡ chữ gốc (trường hợp phổ biến gây chồng chữ). Không đổi gì khi chữ thay thế vừa đủ hoặc ngắn hơn (đường `if estimated_width > available_width` không kích hoạt — đã unit-test riêng bằng `reportlab.pdfmetrics.stringWidth` xác nhận trường hợp "new" ngắn giữ nguyên `font_size`, không co).

### Đã kiểm tra

- `pytest tests/`: baseline xác nhận lại bằng `git stash` là **5 fail / 326 pass** (2 fail nhiều hơn con số "328/3" ghi trước đó trong file này — đã xác nhận cả 5 đều **pre-existing, không liên quan gì đến sửa lần này**, tái hiện y hệt cả khi stash code fix). Sau khi sửa: đúng **5 fail / 326 pass**, không có fail mới.
- Test trực tiếp trên app thật, 4 vòng lặp (mỗi vòng: launch app mới, dùng CDP tạo text-selection thật trên `.textLayer span`, bấm "Sửa text gốc", nhập "REPLACEDFINAL" thay "original text", `Ctrl+S`, render lại bằng `pypdfium2` ở cả độ phóng đại thường và 6-12x để soi kỹ):
  - Vòng 1 (chưa sửa): chồng chữ không đọc được — xác nhận đúng bug report.
  - Vòng 2 (Hướng 1): còn 1 vệt glyph vỡ ở mép.
  - Vòng 3 (Hướng 2): vệt glyph hết nhưng mất chữ "e" của "edited" → "dited" — phát hiện tác dụng phụ, loại bỏ hướng này.
  - Vòng 4 (Hướng 3 - bản cuối): render đúng nguyên vẹn **"This is REPLACEDFINAL to be edited later."** — không mất chữ, không chồng lấn, chỉ đổi cỡ chữ vùng thay thế (nhỏ hơn chữ xung quanh, chấp nhận được vì ưu tiên đúng nội dung).
- Sau khi sửa xong, đã **test thêm với 1 file PDF thật rất lớn** (743MB, 336 trang, scan ảnh) — `C:\Users\HieuPC\Downloads\1 Dao giao sinh tu ky thu - in (1).pdf` — mở file, nhảy trang 1→336→150→50→300, bật thumbnail sidebar (336 thumbnail), mở `Ctrl+F` tìm kiếm — **không crash, không treo, `app_log.txt` sạch không có dòng lỗi mới nào trong suốt phiên**, memory tăng dần hợp lý theo số trang đã cache (570MB→751MB) rồi đóng app sạch sẽ.

**Còn 1 vấn đề nhỏ KHÔNG thuộc phạm vi lỗi này, phát hiện phụ trong lúc test (chưa sửa)**: có 1 vệt gạch ngang nhỏ (artifact) xuất hiện ổn định ở cùng 1 vị trí bên dưới chữ thay thế trong TẤT CẢ các lần test (kể cả trước khi sửa lỗi chồng chữ) — nghi là phần đuôi (descender) của ký tự "g" trong "original" (chữ cũ) chưa được che hết theo chiều dọc. Không liên quan đến lỗi chồng chữ theo chiều ngang đang xử lý ở đây, chỉ nhìn thấy khi phóng to 6-12 lần, không ảnh hưởng khi đọc ở độ phóng đại thường. Ghi nhận lại để xử lý riêng nếu cần, không sửa lan man trong lần này.

**Chưa commit** (mặc định theo quy tắc ở đầu file).

---

## Lỗi 4: "Xóa watermark" không dọn tài nguyên ảnh cũ, làm phình file

**Nguồn phát hiện**: `docs/QA_HEAVY_FILE_2026-08-04.md`, mục "Vấn đề phát hiện #2" (test với file 743MB/336 trang).

**Trạng thái: ĐÃ SỬA, đã test qua app thật.**

### Nguyên nhân

`remove_watermark()` (`app/actions/document_ops.py`) chỉ gỡ lệnh **vẽ** overlay khỏi content stream của trang (`_remove_last_overlay_draw`) — object ảnh watermark vẫn còn nguyên trong `/Resources/XObject` của trang dù không còn được vẽ ra, vì không có bước dọn (garbage-collect) nào sau đó. `pdf.save()` của pikepdf vẫn ghi xuống mọi object còn "sống" trong đồ thị object, kể cả object không còn được tham chiếu từ content stream nào.

### Đã sửa

Thêm `page.remove_unreferenced_resources()` (API có sẵn của pikepdf) ngay sau khi `_remove_last_overlay_draw()` xóa thành công, trong vòng lặp của `remove_watermark()`. Hàm này dọn sạch mọi entry trong `/Resources` không còn được content stream hiện tại tham chiếu tới.

### Đã kiểm tra

- Thực nghiệm độc lập bằng pikepdf (tạo XObject giả, xóa content stream, so sánh kích thước output có/không gọi `remove_unreferenced_resources()`): xác nhận API thực sự khiến `pdf.save()` bỏ hẳn object không dùng, không chỉ orphan trong bộ nhớ.
- `pytest tests/`: 326 pass / 5 fail — đúng baseline (đã xác nhận qua `git stash` 5 fail này pre-existing, không liên quan sửa lần này).
- Test trực tiếp trên app thật (file 5 trang): Watermark (167,525 byte) → Xóa watermark → còn 2,995 byte (gần bằng dung lượng gốc trước khi thêm), `pikepdf` xác nhận `/Resources/XObject` của trang = `None` (sạch hoàn toàn).

**Chưa commit.**

---

## Lỗi 5: Nút "Yes"/"No" tiếng Anh trong nhiều dialog xác nhận

**Nguồn phát hiện**: `docs/QA_UX_FINAL_REVIEW_2026-08-04.md` UX#3 + củng cố thêm ở `docs/QA_HEAVY_FILE_2026-08-04.md` #3.

**Trạng thái: ĐÃ SỬA toàn bộ, đã test qua app thật + pytest.**

### Nguyên nhân

`QMessageBox.question()` dùng `QMessageBox.StandardButton.Yes/No` mặc định — bản dịch `qtbase_vi.qm` cài kèm không phủ nhãn nút chuẩn này, nên dù app đã cài `QTranslator` cho `vi_VN` (`main.py`), nút vẫn hiện "Yes"/"No" tiếng Anh trong khi toàn bộ nội dung dialog là tiếng Việt.

### Đã rà soát toàn bộ codebase (không chỉ 1-2 chỗ đã báo)

Grep `QMessageBox.question(` ra đúng **17 chỗ gọi**, trải trong 10 file: `document_ops.py` (Xóa watermark), `sign.py` (5 chỗ: xác nhận vị trí ký, 3 dialog "ký thành công → mở file?", thêm ô ký), `annotate.py` (Xóa trang), `pages.py` (3 chỗ: mở file mới/xác nhận xóa trang/mở file đã gộp), `license_dialog.py` (nâng cấp tính năng), `document_converter.py` (2 chỗ: tải LibreOffice, tải iTaxViewer), `ai_actions.py` (xoá cấu hình AI), `ocr.py` (2 chỗ: cảnh báo tài liệu dài, cả 2 hàm riêng), `updater.py` (có bản cập nhật mới), `signature_pad.py` (xóa mẫu chữ ký).

### Đã sửa

Thêm hàm dùng chung `ask_yes_no(parent, title, message, *, default_no=False)` vào `app/dialogs.py` (cạnh `show_warning`/`show_info`/`show_error` đã có sẵn) — dựng `QMessageBox` thủ công, gán `.setText("Có")`/`.setText("Không")` cho 2 nút chuẩn, vẫn trả về đúng `QMessageBox.StandardButton.Yes/No` như `QMessageBox.question()` gốc để **không phải sửa bất kỳ dòng nào đang so sánh `reply == /!= StandardButton.Yes`** ở 17 nơi gọi — chỉ đổi cách tạo dialog. Thay toàn bộ 17 lời gọi `QMessageBox.question(...)` bằng `ask_yes_no(...)`. Nhân tiện sửa 1 câu trong `sign.py` từng nhắc thẳng tên nút cũ ("Chọn No nếu muốn kéo lại vùng ký") thành "Chọn Không..." cho khớp nhãn mới.

### Đã kiểm tra

- `pytest tests/`: 326 pass / 5 fail — đúng baseline, không có fail mới phát sinh từ việc đổi 17 chỗ gọi.
- Test trực tiếp trên app thật: dialog "Xóa watermark" hiện đúng nút "Có"/"Không" tiếng Việt (chụp màn hình xác nhận).
- Đã kiểm tra kỹ từng chỗ gọi để giữ đúng `default_no` (nút mặc định) như code gốc: `Xóa trang`, `Xóa cấu hình AI`, `Xóa mẫu chữ ký` giữ mặc định là "Không" (an toàn cho thao tác phá hủy); các dialog còn lại giữ mặc định "Có" hoặc không set (theo đúng hành vi gốc).

**Chưa commit.**

---

## Lỗi 6: "Chèn chữ" không tự focus khung nhập text sau khi tạo

**Nguồn phát hiện**: `docs/QA_UX_FINAL_REVIEW_2026-08-04.md` UX#2.

**Trạng thái: ĐÃ SỬA, đã test qua app thật với thao tác chuột thật (không chỉ UI Automation).**

### Điều tra

Ban đầu nghi ngờ JS thiếu `.focus()` — đọc code (`assets/js/inline_text_bridge.js`) thấy **đã có sẵn** `ta.focus()` đúng chỗ (dòng 275, ngay sau khi tạo textarea). Test lại bằng click chuột thật (Windows API `mouse_event`, không qua UI Automation, để loại trừ khả năng đây chỉ là hạn chế công cụ test) — **vẫn tái hiện đúng lỗi**: gõ "HELLO" ngay sau khi click đặt vị trí không vào được ô nhập (chụp màn hình xác nhận ô vẫn hiện placeholder "Gõ văn bản…").

### Nguyên nhân thật (đọc kỹ `app/pdf_inline_editor.py`)

Panel điều khiển font/cỡ chữ (`InlineEditPanel`) là 1 top-level window riêng (`Qt.WindowType.Tool`), KHÔNG hiện sẵn khi bắt đầu chế độ chèn chữ — nó chỉ được `.show()` lần đầu bên trong callback `_ready()`, được gọi khi JS báo `reportReady` qua WebChannel **NGAY SAU** khi JS vừa `ta.focus()` xong. Callback đó gọi `panel.show(); panel.raise_(); panel.activateWindow()` — `activateWindow()` yêu cầu hệ điều hành cấp OS-level keyboard focus cho panel, cướp lại đúng focus mà JS vừa đặt vào ô nhập trong QWebEngineView 1 nhịp trước đó. Vì 2 window (panel và QWebEngineView) là 2 top-level window OS riêng biệt, ai activate sau cùng thắng.

### Đã sửa

Bỏ `panel.activateWindow()` ở cả 2 chỗ gọi giống hệt nhau trong `app/pdf_inline_editor.py` (`run_inline_text()` dòng ~493 và `run_inline_image()` dòng ~600) — giữ nguyên `panel.show(); panel.raise_()` để panel vẫn hiện & nổi lên trên, các nút/control trong panel vẫn thao tác bằng chuột bình thường (không cần activate trước). Sửa cả 2 chỗ vì cùng 1 pattern lỗi hệt nhau (`run_inline_image` tuy không cần gõ phím ngay nhưng Enter/Esc xác nhận/hủy trên trang cũng qua JS keydown listener, cùng phụ thuộc OS focus).

### Đã kiểm tra

- `pytest tests/`: 326 pass / 5 fail — đúng baseline.
- Test trực tiếp trên app thật, **click chuột thật qua Windows API** (không phải UI Automation invoke) vào trang PDF ngay sau khi bấm "Chèn chữ", gõ "HELLO" ngay lập tức: TRƯỚC khi sửa → ô trống (chỉ hiện placeholder); SAU khi sửa → "HELLO" vào đúng ô ngay lần click đầu tiên, không cần click thêm lần 2 (2 ảnh chụp màn hình đối chiếu).

**Đã commit** (`0c4d9d8`).

---

## Lỗi 7: Vệt đuôi chữ (descender) bị cắt cụt trong "Sửa text gốc"

**Trạng thái: ĐÃ SỬA.** Xem chi tiết đầy đủ ở commit `c68761b` — cho phép mép dưới vùng che lấn xuống thêm tối đa 1/4 cỡ chữ trước khi giới hạn theo span thật (`tight_bottom = max(bottom - descender_allowance, span_bottom)` thay vì `max(bottom, span_bottom)`). Test lại đúng kịch bản cũ (chữ "g" trong "original"): vệt biến mất hoàn toàn. `pytest`: 328 pass / 4 fail (baseline). **Đã commit.**

---

## Xác nhận lại 2 mục "chưa đủ căn cứ kết luận" từ `QA_UX_FINAL_REVIEW_2026-08-04.md`

### "Xóa đối tượng" (UX#4) — XÁC NHẬN HOẠT ĐỘNG ĐÚNG, không phải bug

Test lại trong **1 phiên pywinauto liên tục, không ngắt kết nối** (khác với lần trước dùng 2 script rời rạc): Chèn chữ ("DELMETEXT") bằng click chuột thật → "Chèn vào PDF" (chưa lưu) → bấm "Xóa obj" (ribbon đổi màu đúng, nút "Hủy" nổi lên đúng) → click chuột thật trực tiếp vào text vừa chèn → **text biến mất đúng, mode thoát sạch, không lỗi**. Xác nhận nghi vấn trước đó đúng là do phương pháp test (mất kết nối pywinauto giữa 2 script làm rớt trạng thái "đang chờ chọn"), không phải bug app.

### Nền đen thoáng qua sau đổi theme (Vấn đề #1, `QA_HEAVY_FILE_2026-08-04.md`) — KHÔNG TÁI HIỆN ĐƯỢC

Đã thử: đổi theme tối→sáng liên tục 6 lần dồn dập, cuộn qua nhiều trang tới vùng phân cách giữa trang, chụp màn hình **ngay lập tức không delay** sau mỗi lần đổi theme (đúng thời điểm nghi có bug) — **không tái hiện được** hiện tượng nền đen ở bất kỳ lần thử nào, nền luôn đúng màu theo theme hiện tại. Giữ nguyên kết luận cũ: chưa đủ căn cứ để coi là bug thật, có thể là hiện tượng ngẫu nhiên/hiếm gặp phụ thuộc timing. Không có gì để sửa.

---

## Còn lại duy nhất chưa test được (không phải do né tránh)

- **Tìm nghĩa** (semantic search — bước tìm kiếm thực tế): cần OpenAI API key của user, máy chỉ có Gemini key.
- OCR toàn bộ + Xuất Word/Excel/Ảnh cho file rất nhiều trang: lần test trước dùng sai môi trường Python (thiếu `pytesseract`), cần chạy lại bằng đúng `.venv` của project.
