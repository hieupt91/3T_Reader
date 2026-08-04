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

### Tổng kết những gì sẵn sàng để bạn test

- **Lỗi 0 (chú thích tự lưu báo sai khi chỉ đọc)** — đã sửa (`app/actions/annotate.py`, `app/actions/auto_ocr.py`, `app/window.py`), đã test pass, **sẵn sàng để bạn test lại trên app thật**.
- **Lỗi 1 (xoay trang)** — không phải bug, không có code nào thay đổi.
- **Lỗi 2 (crash)** — chưa sửa được, không đủ công cụ chẩn đoán trong phạm vi phiên này.
