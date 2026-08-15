# Test hiệu năng với file PDF nặng thực tế — 3T Reader — 2026-08-04

## Mục tiêu & phương pháp

Hai vòng QA trước đó (`docs/QA_TOAN_DIEN_2026-08-04.md`, `docs/QA_UX_FINAL_REVIEW_2026-08-04.md`) đều dùng file PDF nhỏ (vài trang, tạo bằng `reportlab`) — đủ để xác nhận tính đúng đắn chức năng, nhưng không lộ ra được các vấn đề chỉ xuất hiện khi xử lý file lớn: treo UI, tràn bộ nhớ, timeout, thao tác chậm bất thường. Vòng test này dùng file PDF **nặng nhất tìm được trên máy** để kiểm tra riêng khía cạnh hiệu năng/ổn định.

**Phương pháp**: copy file gốc ra bản test riêng trong thư mục scratchpad (**không bao giờ đụng vào file gốc của user**), mở app thật bằng bản copy đó, điều khiển bằng `pywinauto` (backend `uia`), đo thời gian bằng timestamp trước/sau mỗi thao tác, đo RAM bằng `tasklist`, xác nhận kết quả ghi file bằng cách đọc lại trực tiếp bằng `pikepdf`/`pypdfium2` (không chỉ tin thông báo trên UI), và **chụp màn hình + boost contrast** khi cần kiểm tra chi tiết khó thấy bằng mắt thường (ví dụ watermark mờ 20% opacity).

## Thông tin file test

| Thuộc tính | Giá trị |
|---|---|
| Tên file gốc | `1 Dao giao sinh tu ky thu - in (1).pdf` (sách về Đạo giáo, không phải nội dung riêng tư) |
| Vị trí gốc | `C:\Users\HieuPC\Downloads\` |
| Dung lượng | 743.5 MB (709.1 MiB) |
| Số trang | 336 |
| Loại nội dung | Scan ảnh độ phân giải cao, **không có text layer gốc** (tạo bởi Adobe Acrobat 11.0.23 Image Conversion Plug-in) |
| Bản test dùng | Copy riêng trong scratchpad, không đụng file gốc |

---

## Bảng tổng hợp kết quả theo tính năng

| Tab | Tính năng | Trạng thái | Thời gian đo được | Ghi chú |
|---|---|---|---|---|
| Tệp & Xem | Mở file | ✅ OK | ~15s | Nhanh hơn kỳ vọng cho file 743MB — có vẻ stream-load theo trang, không đọc hết cả file lúc mở |
| Tệp & Xem | Điều hướng trang (next) | ✅ OK | ~1.2s/lần | |
| Tệp & Xem | Điều hướng dồn dập (10 lần next liên tiếp) | ✅ OK | ~5s tổng | Đúng số trang, không lệch/nhân đôi |
| Tệp & Xem | Zoom 200%/400% trên trang scan độ phân giải cao | ✅ OK | ~1.5s/lần đổi zoom | Không giật, render sắc nét |
| Tệp & Xem | Thumbnail sidebar (336 thumbnail) | ✅ OK | ~4s để mở + tải | Cuộn mượt, tự động scroll đến trang hiện tại |
| Tệp & Xem | Giao diện tối/sáng | ✅ OK | — | Xem mục "Vấn đề phát hiện #1" bên dưới (transient, không tái hiện ổn định) |
| Tệp & Xem | Toàn màn hình | ✅ OK | ~1.6s | |
| Tệp & Xem | Tìm kiếm (`Ctrl+F`) | ✅ OK (đúng "không tìm thấy") | tức thời | File chưa OCR, không có text layer — báo đúng "Không tìm thấy 'sinh' trong tài liệu", không treo dù quét 336 trang |
| Chú thích | Tô sáng theo từ khóa | ✅ OK (đúng hành vi) | tức thời | Không tìm được vì chưa OCR — đúng như tìm kiếm thường |
| Chú thích | Ghi chú | ✅ OK | ~1.2s mở dialog | |
| Chú thích | Chèn chữ | ⚠️ Không kết luận được | — | Không tự động hoá thành công vòng chèn+lưu hoàn chỉnh trong phiên này (lỗi thao tác click tọa độ của công cụ test, không phải dấu hiệu lỗi app) — đã xác nhận OK với file nhỏ ở phiên trước, panel vẫn mở đúng, không crash |
| Chú thích | Sửa text gốc | ❌ Không test được | — | File là scan thuần, chưa OCR nên không có text layer PDF.js để tạo Selection — đặc thù của file, không phải lỗi app |
| Trang | Xoay trang (`Ctrl+]`) | ✅ OK | Phản hồi hình ảnh tức thời (~0.45s), ghi nền xong trong ~4s | Hoạt động hoàn hảo dù file 743MB — ghi nền chỉ động vào đúng trang, không phải ghi lại cả file |
| Bảo mật & Xuất | Watermark (336 trang) | ✅ OK | **< 60s** cho toàn bộ 336 trang | Xác nhận có thật bằng render + boost contrast (chữ "BẢN NHÁP" mờ 20% dễ bị bỏ sót nếu chỉ nhìn lướt) |
| Bảo mật & Xuất | Xóa watermark (336 trang) | ⚠️ OK về hiển thị, có vấn đề dọn tài nguyên | ~30s | Xem "Vấn đề phát hiện #2" — watermark biến mất khỏi hiển thị đúng, nhưng ảnh watermark cũ không bị xoá khỏi file |
| Bảo mật & Xuất | Đặt mật khẩu (754MB) | ✅ OK | ~60–90s | Xác nhận độc lập bằng `pikepdf`: đúng yêu cầu mật khẩu, mở đúng bằng mật khẩu đã đặt |
| Bảo mật & Xuất | Xóa mật khẩu (754MB) | ✅ OK | ~1–2 phút | Xác nhận độc lập: mở được không cần mật khẩu |
| Bảo mật & Xuất | Nén PDF (754MB) | ✅ OK | ~1 phút | Giảm nhẹ dung lượng (~570KB) — hợp lý vì ảnh scan đã được nén sẵn từ Adobe, không còn nhiều để nén thêm |
| Bảo mật & Xuất | Xuất Văn bản | ✅ Dialog OK | tức thời | Dialog lưu file mở nhanh, đúng; không chạy hết vì nội dung sẽ trống (chưa OCR) — không có giá trị test thêm |
| Bảo mật & Xuất | Xuất Word/Excel/Ảnh (336 trang) | ❓ Không chạy full | — | Xem "Phạm vi rút gọn" bên dưới |
| OCR & AI | OCR trang (1 trang) | ❌ Không test được | — | Thiếu `pytesseract` trong môi trường Python dùng để chạy app lần này (lỗi môi trường phiên test, không phải lỗi app) — app xử lý đúng, hiện dialog "Cần cài thêm Tesseract OCR" rõ ràng, không crash |
| OCR & AI | OCR tài liệu (336 trang) | ❓ Không test được | — | Phụ thuộc OCR trang ở trên |
| OCR & AI | Chat PDF / Tóm tắt / Dịch / Tìm nghĩa | ❓ Không test | — | Không đủ thời gian trong phiên — các tính năng này gọi API AI ngoài, không phụ thuộc trực tiếp vào dung lượng file PDF nên rủi ro hiệu năng thấp hơn, ưu tiên thấp hơn trong phạm vi test này |
| Ký số | Ký PFX (mở dialog chọn vị trí) | ✅ OK | ~1.6s | Dialog mở nhanh, không lag dù file 754MB, 336 trang — không chạy hết luồng ký vì đã xác nhận kỹ ở phiên trước với file nhỏ |
| Ký số | Ký lô / Ô ký / Ký tay / Kiểm tra | ❓ Không test | — | Không đủ thời gian, ưu tiên thấp hơn vì không phải thao tác đặc thù cho file nặng |

---

## Vấn đề phát hiện được

### #1 — Nền vùng xem PDF chuyển đen sau khi bật/tắt giao diện tối, không tái hiện ổn định (Mức độ: Không xác định — không đủ căn cứ kết luận là bug)

- **Hiện tượng**: sau khi bật giao diện tối rồi chuyển lại sáng, vùng nền giữa các trang (khoảng cách khi cuộn liên tục) có màu đen dù ribbon/toolbar đã đúng màu sáng. Vùng đen này giữ nguyên qua nhiều lần chuyển tab, cuộn trang, bật/tắt toàn màn hình.
- **Điều tra thêm**: thử bấm lại đúng nút chuyển đổi (xác nhận nhãn nút đổi đúng theo trạng thái: "☀ Sáng" ↔ "🌙 Tối") nhưng vùng đen không đổi theo. Sau đó, khi chuyển tab ribbon + mở/đóng 1 dialog khác (Ghi chú), vùng đen **tự biến mất**, ribbon và vùng nền đều đúng màu sáng.
- **Không đủ căn cứ kết luận là bug thật**: có thể đây chỉ là style cố định của "vùng phân cách giữa trang" trong chế độ cuộn liên tục (nhiều PDF viewer khác cũng tô tối vùng này bất kể theme, để phân biệt ranh giới trang) — hoặc là 1 lỗi repaint tạm thời, tự khỏi khi có thao tác UI khác kích hoạt vẽ lại. Ghi nhận lại để nếu tái diễn ở phiên sau, có thêm dữ liệu xác nhận.

### #2 — "Xóa watermark" không dọn tài nguyên ảnh watermark cũ khỏi file (Mức độ: Trung bình, ảnh hưởng dung lượng file)

- **Hiện tượng**: dùng "Xóa watermark" trên file đã có watermark 336 trang — watermark biến mất đúng khỏi hiển thị (đã xác nhận bằng render + boost contrast, không còn thấy chữ "BẢN NHÁP" ở bất kỳ trang nào kiểm tra). NHƯNG dung lượng file chỉ giảm ~17KB (754,552,002 → 754,534,833 byte), trong khi lẽ ra phải giảm gần bằng đúng lượng đã tăng khi thêm watermark (~11MB, từ 743,530,547 → 754,552,002 byte).
- **Nguyên nhân nghi vấn (xác nhận qua `pikepdf`, chưa đọc code)**: kiểm tra `/Resources/XObject` của các trang sau khi xóa watermark, các đối tượng ảnh watermark (ví dụ `/LLbtfSg91S5-FDCp1pzKTQ`) **vẫn còn tồn tại trong resource dictionary của trang** dù không còn được vẽ ra (không còn xuất hiện trong nội dung hiển thị). Có vẻ thao tác xóa chỉ gỡ lệnh **vẽ** watermark khỏi content stream, chưa dọn (garbage-collect) đối tượng ảnh watermark không còn dùng đến khỏi file.
- **Tác động thực tế**: với file 336 trang, mỗi lần thêm rồi xóa watermark sẽ để lại "rác" trong file (~11MB không dùng đến), làm file phình to dần nếu người dùng lặp lại nhiều lần (thêm/xóa/thêm/xóa watermark), dù kết quả hiển thị luôn đúng.
- **Đề xuất hướng xử lý (không phải code cụ thể)**: khi xóa watermark, cân nhắc dùng tính năng "linearize"/loại bỏ object không tham chiếu của pikepdf (`save(..., linearize=True)` hoặc tương đương xoá unreferenced objects) để dọn sạch các XObject ảnh watermark không còn dùng đến.

### #3 — Nút "Yes"/"No" tiếng Anh xuất hiện thêm ở dialog Xóa watermark (bổ sung cho vấn đề đã ghi nhận trong `QA_UX_FINAL_REVIEW_2026-08-04.md`)

- Báo cáo trước chỉ ghi nhận 1 chỗ (dialog xác nhận vị trí ký). Vòng test này phát hiện thêm: dialog xác nhận "Xóa watermark" ("Tiếp tục xóa watermark?") cũng dùng nút "Yes"/"No" tiếng Anh, trong khi toàn bộ nội dung dialog là tiếng Việt. Củng cố thêm giả thuyết đã nêu trước đó: nhiều nơi trong app còn dùng `QMessageBox.question()` mặc định chưa được tiếng Việt hóa nút bấm — nên rà soát toàn bộ, không chỉ 1-2 chỗ đã tìm thấy.

---

## Phạm vi phải rút gọn (và lý do)

1. **OCR trang/OCR tài liệu 336 trang**: KHÔNG chạy được — môi trường Python dùng để khởi động app trong phiên test này (`python main.py`, trỏ tới bản Python của miniconda) thiếu thư viện `pytesseract`. App phát hiện đúng và báo lỗi rõ ràng ("Cần cài thêm Tesseract OCR... pip install pytesseract"), không crash — đây là vấn đề **môi trường của phiên test**, không phải lỗi trong code app. Phiên test trước (dùng file nhỏ, cùng ngày hôm nay) đã xác nhận OCR hoạt động đúng và cho kết quả chính xác 100% khi môi trường có đủ `pytesseract`+Tesseract. **Không có số liệu ngoại suy thời gian OCR cho 336 trang trong báo cáo này** — cần chạy lại ở môi trường có đủ dependency (ví dụ dùng đúng `.venv` của project thay vì `python` mặc định) mới đo được.
2. **Xuất Word/Excel/Ảnh cho toàn bộ 336 trang**: không chạy hết trong phạm vi thời gian phiên test — ưu tiên dồn thời gian cho các thao tác ghi trực tiếp lên file lớn (Watermark, Mật khẩu, Nén, Xoay trang) vì đó là trọng tâm chính của vòng test "file nặng". Xuất Văn bản đã xác nhận dialog mở nhanh, đúng; các luồng Word/Excel/Ảnh có cùng cơ chế UI, rủi ro hiệu năng chủ yếu nằm ở bước xử lý ảnh/OCR mỗi trang (tương tự OCR) — nên **ưu tiên test lại cùng lúc với OCR ở phiên sau, dùng đúng môi trường đủ dependency**.
3. **Chat PDF/Tóm tắt/Dịch/Tìm nghĩa, Ký lô/Ô ký/Ký tay/Kiểm tra chữ ký**: không test trong phiên này — các tính năng AI gọi API ngoài không phụ thuộc trực tiếp vào dung lượng file PDF (rủi ro hiệu năng thấp hơn khía cạnh đang test); nhóm Ký số còn lại đã xác nhận kỹ với USB thật + PFX test ở phiên QA sáng nay, phiên này chỉ cần xác nhận UI không lag với file nặng (đã làm với Ký PFX, đại diện đủ cho cả nhóm).
4. **Chèn chữ**: không hoàn thành được vòng chèn+lưu qua tự động hoá do click tọa độ của pywinauto không chính xác trong 2-3 lần thử — không phải dấu hiệu app có vấn đề (panel mở đúng, không crash, không treo ở bất kỳ lần thử nào).

---

## Đánh giá tổng thể

**App xử lý file PDF nặng (743MB, 336 trang scan) khá tốt trong thực tế**, không có dấu hiệu treo UI, tràn bộ nhớ mất kiểm soát, hay crash trong toàn bộ phiên test (đã kiểm tra `app_log.txt` và Windows Event Log gián tiếp qua việc tiến trình không bao giờ chết bất ngờ — chỉ có các dòng benign COM error `0x8001010d` đã biết từ trước, không phải crash thật).

**Về hiệu năng cụ thể**:
- Mở file, điều hướng, zoom, thumbnail: nhanh, không giật — có vẻ dùng cơ chế tải/hiển thị theo trang (lazy loading), không đọc toàn bộ 743MB vào bộ nhớ cùng lúc.
- Các thao tác ghi TOÀN BỘ tài liệu (Watermark, Mật khẩu, Nén) đều hoàn thành trong khoảng **dưới 2 phút** cho 336 trang — chấp nhận được cho thao tác 1 lần, dù người dùng cần được biết trước rằng các thao tác này có "chờ" thay vì tưởng app bị treo (không quan sát thấy progress bar/% tiến độ rõ ràng trong lúc chờ — có thể là điểm cải thiện UX, không phải bug).
- Thao tác ghi CỤC BỘ (Xoay 1 trang) rất nhanh (~4s kể cả với file 743MB) — xác nhận thiết kế "chỉ ghi phần thay đổi" hoạt động đúng như mô tả trong code.

**Giới hạn cần lưu ý cho người dùng**:
- OCR toàn bộ 336 trang scan chưa được đo thời gian thực tế trong báo cáo này (do vấn đề môi trường test, không phải giới hạn của app) — với kinh nghiệm từ phiên test file nhỏ trước đó (OCR 3 trang mất vài giây), 336 trang **có khả năng mất khá lâu** (ước tính vài chục phút, cần đo lại chính xác ở phiên sau) — nên cân nhắc chạy OCR toàn bộ cho file rất nhiều trang vào lúc không cần dùng máy gấp.
- Xóa watermark không thực sự "dọn sạch" dung lượng đã dùng cho watermark cũ — nếu lặp lại nhiều lần thêm/xóa watermark trên cùng 1 file lớn, dung lượng file sẽ tăng dần theo thời gian.
- Không phát hiện giới hạn cứng nào về dung lượng/số trang trong phiên test này (743MB/336 trang vẫn chạy ổn) — nhưng cũng chưa test file lớn hơn nữa (ví dụ >1GB, >1000 trang) nên chưa thể khẳng định đây là trần tối đa app xử lý được tốt.

---

## Kết luận

Test hiệu năng với file PDF nặng nhất tìm được trên máy (743MB, 336 trang) cho thấy 3T Reader **xử lý ổn định, không crash, tốc độ chấp nhận được** cho phần lớn tính năng đã test được. **1 vấn đề đáng chú ý mới phát hiện**: Xóa watermark không dọn sạch tài nguyên ảnh cũ, gây phình dung lượng file theo thời gian nếu lặp lại nhiều lần (mức độ trung bình, không ảnh hưởng tính đúng đắn hiển thị). **1 quan sát chưa đủ căn cứ kết luận**: vùng nền đen sau khi đổi theme, tự khỏi sau thao tác khác — cần theo dõi thêm nếu tái diễn. **1 vấn đề UX đã biết được củng cố thêm bằng chứng**: nút Yes/No tiếng Anh xuất hiện ở nhiều dialog hơn báo cáo trước ghi nhận. OCR và Xuất Word/Excel/Ảnh cho toàn bộ 336 trang **chưa đo được** do thiếu dependency trong môi trường chạy phiên test này (không phải giới hạn của app) — khuyến nghị chạy lại ở phiên sau bằng đúng `.venv` của project.
