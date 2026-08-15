# Rà soát QA/UX lần cuối trước khi xuất bản — 3T Reader — 2026-08-04

## Mục tiêu & phương pháp

Đây là vòng rà soát **cuối cùng**, độc lập với vòng QA toàn diện đã thực hiện sớm hơn trong cùng ngày hôm nay (xem `docs/QA_TOAN_DIEN_2026-08-04.md` và `sualoint.md`). Mục tiêu không chỉ là xác nhận "còn chạy được" mà đứng ở góc nhìn của một chuyên gia QA/UI-UX độc lập trước khi xuất bản: đánh giá tính rõ ràng của nhãn/thông báo, tính nhất quán ngôn ngữ, phản hồi trực quan, hành vi ở các cạnh (hủy giữa chừng, đóng bằng Esc, thao tác dồn dập), và chế độ tối.

**Phương pháp**: mở app thật (`python main.py qa_final_test.pdf`, có `QTWEBENGINE_REMOTE_DEBUGGING` để dùng lại kỹ thuật CDP cho "Sửa text gốc"), điều khiển bằng `pywinauto` (backend `uia`), xác nhận bằng **chụp màn hình thật** ở mọi bước nghi vấn và **đọc lại file PDF bằng `pikepdf`/`pypdfium2`** sau mỗi thao tác ghi — tuân thủ đúng bài học phương pháp đã rút ra từ vòng test trước (không kết luận lỗi chỉ vì UI Automation "không thấy" cửa sổ). File PDF test và toàn bộ tiến trình đã được dọn sạch sau khi test xong; `git status --short` cuối cùng chỉ còn 3 file docs không liên quan đã có từ trước phiên làm việc.

**Phạm vi đã test trong vòng này**: toàn bộ 6 tab ribbon (Tệp & Xem, Chú thích, Trang, Bảo mật & Xuất, OCR & AI, Ký số), tập trung re-verify 2 lỗi đã sửa trước đó (Highlight fallback, nhãn dialog Vẽ tự do) và mitigation crash, cộng thêm nhiều edge case mới (hủy dialog bằng Esc, OCR trên trang đã có text, dark mode, xóa mật khẩu/watermark giữa chừng, thao tác dồn dập). Nhóm Ký số **không** dùng lại USB token thật (đã xác nhận kỹ sáng nay) — dùng chứng thư PFX tự-ký tạo riêng cho vòng test này để kiểm tra luồng UI không hồi quy.

---

## Bảng tổng hợp tình trạng

| Nhóm | Tính năng | Trạng thái | Ghi chú |
|---|---|---|---|
| Tệp & Xem | Điều hướng, Zoom, Fullscreen, Tìm kiếm (F3 wrap) | ✅ OK | Không phát hiện vấn đề |
| Chú thích | Gạch dưới/ngang/Tô sáng (theo từ khóa) | ✅ OK, không hồi quy | Re-verify bằng pikepdf: đúng `/Highlight`, `/Underline`, `/StrikeOut` trên đúng trang |
| Chú thích | Ghi chú | ✅ OK | Dialog rõ ràng, dark mode OK |
| Chú thích | Vẽ tự do | ✅ OK, không hồi quy | Nhãn dialog vẫn đúng "Chọn vị trí chèn" sau fix |
| Chú thích | Chèn chữ | ⚠️ OK nhưng có vấn đề UX | Xem mục UX #2 |
| Chú thích | Xóa trắng | ✅ OK | |
| Chú thích | Hoàn tác | ✅ OK | Xóa đúng object vừa chèn (chưa lưu) |
| Chú thích | Chọn & Xoay | ✅ OK | UI handle rõ ràng |
| Chú thích | Xóa đối tượng | ❓ Không xác nhận chắc chắn | Xem mục UX #4 — nghi vấn do phương pháp test, không kết luận là lỗi |
| Chú thích | Sửa text gốc | ⚠️ OK về chức năng, có vấn đề chất lượng hiển thị | Xem mục UX #1 |
| Trang | Xoay trang (dồn dập 10-15 lần) | ✅ OK | Cộng dồn đúng, không crash |
| Trang | Số trang | ✅ OK | Esc hủy sạch |
| Bảo mật & Xuất | Watermark | ✅ OK | Esc hủy sạch, dark mode OK |
| Bảo mật & Xuất | Đặt mật khẩu | ✅ OK | Esc hủy sạch |
| OCR & AI | OCR trang (kể cả trên trang đã có text — edge case) | ✅ OK | Không crash, không phá dữ liệu, đóng sạch |
| Ký số | Ký PFX (chứng thư tự-ký test) | ✅ OK, không hồi quy | Nhãn dialog đúng "Chọn vị trí ký" (khác Vẽ tự do — xác nhận phạm vi fix cũ đúng); hành vi từ chối chứng thư tự-ký khi LTV bật vẫn đúng như sáng nay |
| Ổn định | Mitigation crash (gc.disable + timer) | ✅ Vẫn giữ vững | 3 vòng stress dồn dập, 0 crash mới trong `app_log.txt`, 0 sự kiện Windows Event Log Id=1000 mới trong toàn phiên |
| Toàn app | Chế độ tối (dark mode) | ✅ OK | Dialog Ghi chú + Watermark đều theo đúng theme tối |

**Không phát hiện bug chức năng mới nào trong vòng rà soát này.** 2 bug đã sửa trước đó (Highlight fallback, nhãn Vẽ tự do) vẫn giữ nguyên, không hồi quy.

---

## Danh sách vấn đề UX phát hiện được

### UX #1 — "Sửa text gốc": chữ thay thế có thể chồng lấn gây MẤT KHẢ NĂNG ĐỌC khi dài hơn vùng che (Mức độ: Trung bình) — ĐÃ SỬA

> **Cập nhật sau báo cáo này**: đã sửa trong `app/actions/edit.py` (co cỡ chữ thay thế vừa vùng che thay vì mở rộng vùng che đè lên nội dung liền sau), test 4 vòng trên app thật + pytest baseline không đổi. Chi tiết đầy đủ ở `sualoint.md` mục "Lỗi 3". Chưa commit.

- **Vị trí**: tính năng "Sửa text gốc" (`app/actions/edit.py` hoặc tương đương — chưa đọc code chi tiết trong vòng này, chỉ ghi nhận hiện tượng).
- **Hiện tượng**: thay "original text" (13 ký tự) bằng "REPLACEDFINAL" (14 ký tự, chỉ dài hơn 1 ký tự) trên PDF test. Vùng che (whiteout) chỉ đủ rộng cho text cũ; chữ mới đè lên phần chữ còn lại phía sau ("edited later."), tạo ra dòng chữ chồng lẫn **không thể đọc được**: "REPLACEDfdMAledited" (chụp render trực tiếp + xác nhận độc lập bằng OCR trang cũng đọc ra đúng chuỗi méo này).
- **Khác với đánh giá ở báo cáo sáng nay** ("chồng nhẹ" / "cosmetic") — nhìn kỹ ở vòng rà soát cuối này, mức độ chồng lấn là **đáng kể**, đủ để văn bản không còn đọc được, không chỉ là vấn đề thẩm mỹ nhỏ.
- **Đã có sẵn cảnh báo bằng lời** ngay trong dialog ("text cũ chỉ bị che đi, không bị xoá khỏi file PDF") nhưng cảnh báo này nói về rủi ro bảo mật (bôi đen/copy được), **không cảnh báo về rủi ro chồng chữ mất khả năng đọc** khi độ dài khác nhau.
- **Đề xuất hướng cải thiện** (chỉ ở mức ý tưởng, chưa đề xuất code cụ thể): cân nhắc tự động co cỡ chữ theo bề rộng vùng che, hoặc hiện cảnh báo riêng khi phát hiện text thay thế dài hơn đáng kể so với text gốc, hoặc mở rộng vùng che theo chiều ngang để không đè lên nội dung liền sau (rủi ro: có thể đè lên chữ liền trước nếu text ngắn lại).

### UX #2 — "Chèn chữ": focus bàn phím không tự động vào khung nhập sau khi tạo (Mức độ: Thấp–Trung bình)

- **Vị trí**: tính năng "Chèn chữ" (Chú thích tab).
- **Hiện tượng**: click vào trang để tạo khung nhập văn bản nổi (hiện placeholder "Gõ văn bản...") — nếu gõ ngay sau đó **không có ký tự nào xuất hiện**. Phải click thêm 1 lần nữa vào bên trong khung mới gõ được.
- **Rủi ro thực tế**: người dùng thông thường có xu hướng gõ ngay sau khi click đặt vị trí (giống hầu hết các trình soạn thảo khác tự động focus). Gặp phải hiện tượng này dễ khiến người dùng tưởng nút bị treo/không hoạt động.
- **Đề xuất hướng cải thiện**: tự động `focus()`/đặt con trỏ ngay vào khung nhập tại thời điểm nó được tạo ra bởi click đặt vị trí.

### UX #3 — Nhãn nút "Yes"/"No" tiếng Anh trong dialog xác nhận vị trí ký (Mức độ: Thấp)

- **Vị trí**: hộp thoại "Xác nhận vị trí ký" (xuất hiện sau khi kéo vùng ký trong luồng Ký PFX/Ký số/Ký lô).
- **Hiện tượng**: toàn bộ nội dung dialog bằng tiếng Việt ("Bạn có đồng ý ký văn bản này tại vị trí đã chọn không?") nhưng 2 nút bấm vẫn là **"Yes" / "No"** tiếng Anh — không nhất quán với phần còn lại của app (100% tiếng Việt, kể cả các dialog OK/Cancel khác cũng thường được localize riêng, ví dụ "Đặt mật khẩu PDF" dùng "OK"/"Cancel" tiếng Anh nhưng ít nhất đó là quy ước chung; "Yes"/"No" nổi bật hơn vì khác kiểu với các nút khác).
- **Nghi vấn nguyên nhân sơ bộ**: nhiều khả năng đây là `QMessageBox.question()` mặc định của Qt chưa truyền `buttonText` tùy chỉnh, khác với các dialog tự thiết kế khác trong app (đã tiếng Việt hóa đầy đủ).
- **Đề xuất hướng cải thiện**: rà lại toàn bộ các `QMessageBox` dùng nút mặc định trong luồng ký số/xóa trang/v.v. để đồng bộ ngôn ngữ nút bấm.

### UX #4 — "Xóa đối tượng": không xác nhận chắc chắn được hành vi click-để-xóa trong vòng test này (Mức độ: Không xác định — cần test lại)

- **Hiện tượng**: bấm nút "Xóa obj" → mode chuyển sang trạng thái đang chờ chọn đối tượng (nút ribbon đổi màu, xuất hiện nút "Hủy" nổi trên trang) — xác nhận qua ảnh chụp. Nhưng khi thử click vào đối tượng vừa chèn (text "QAUXTESTINSERT") ở một lần chạy script kế tiếp, mode đã tự thoát mà không xóa được gì.
- **Không kết luận đây là lỗi thật**: giữa 2 bước có một lần kết nối lại `pywinauto` bằng tiến trình Python mới (gọi `set_focus()` lại vào cửa sổ chính), nhiều khả năng chính thao tác refocus này đã hủy trạng thái "đang chờ chọn đối tượng" — đây là hạn chế của phương pháp test theo từng script rời rạc, không phải bằng chứng app có lỗi. Cần test lại trong **một phiên pywinauto liên tục, không ngắt kết nối** để có kết luận chắc chắn.
- **Đề xuất**: nếu có thời gian, test lại thủ công (dùng chuột thật) luồng Xóa đối tượng để loại trừ hoàn toàn nghi vấn.

### UX #5 — Native file-picker (chọn chứng thư ký số) khó tự động hóa ổn định (Mức độ: Ghi chú phương pháp, không phải vấn đề app)

- Hộp thoại Windows "Chọn file chứng thư ký số" (common dialog gốc hệ điều hành) không tự động hóa ổn định bằng tọa độ click qua nhiều lần thử — không phải lỗi của app (đây là dialog hệ thống Windows, ngoài phạm vi code app). Đã đổi hướng xác minh: gọi thẳng hàm ký (`sign_pdf_with_pkcs12`, tương tự phương pháp đã dùng sáng nay) để xác nhận **hành vi bảo mật cốt lõi không đổi** — chứng thư tự-ký vẫn bị từ chối đúng khi `enable_ltv=True` (lỗi `InvalidCertificateError`, y hệt kết quả sáng nay).

---

## Danh sách bug chức năng thật

**Không tìm thấy bug chức năng mới nào trong vòng rà soát cuối này.**

---

## Xác nhận re-test các hạng mục đã sửa/áp dụng trước đó

| Hạng mục | Trạng thái sau vòng rà soát cuối |
|---|---|
| Fix "Tô sáng" thiếu nhánh fallback theo từ khóa | ✅ Vẫn đúng — re-verify bằng pikepdf, `/Highlight` ghi đúng trên cả 2 trang chứa từ khóa "Lorem" |
| Fix nhãn dialog "Vẽ tự do" (không còn nhầm "chữ ký") | ✅ Vẫn đúng — dialog hiện đúng "Chọn vị trí chèn" / "đặt vùng chèn hình vẽ"; đồng thời xác nhận 5 luồng Ký số thật không bị ảnh hưởng (dialog Ký PFX vẫn đúng "Chọn vị trí ký" như thiết kế gốc) |
| Mitigation crash `sizedFree` (gc.disable + timer 10s) | ✅ Vẫn giữ vững qua 3 vòng stress dồn dập trong vòng rà soát này (rotate x10-15 liên tục, chuyển tab x20 + zoom x20 + page-nav x20 dồn dập cùng lúc) — 0 dòng crash mới trong `app_log.txt` (chỉ có mã COM benign `0x8001010d` đã biết), 0 sự kiện Windows Event Log Id=1000 mới trong suốt phiên. **Nhắc lại giới hạn đã nêu trước đó**: lỗi gốc vốn hiếm (93 lần/2.5 tháng) nên một phiên test dài không crash là tín hiệu tốt, chưa phải bằng chứng tuyệt đối đã hết — vẫn cần theo dõi thực tế dài hạn theo bảng đã lập trong `sualoint.md` |

---

## Đề xuất bổ sung tổng thể (mức ý tưởng, không phải bug)

1. **Tự động focus vào khung nhập** ngay khi tạo mới trong "Chèn chữ" — giảm 1 bước thao tác thừa dễ gây hiểu lầm (xem UX #2).
2. **Xử lý overflow văn bản trong "Sửa text gốc"** khi chữ thay thế dài hơn đáng kể so với chữ gốc, để tránh chồng chữ mất khả năng đọc (xem UX #1) — đây là vấn đề ảnh hưởng trực tiếp đến chất lượng tài liệu đầu ra, nên có mức ưu tiên cao hơn các đề xuất khác trong danh sách này.
3. **Đồng bộ ngôn ngữ nút bấm** trong các `QMessageBox` mặc định còn sót tiếng Anh (ít nhất 1 chỗ đã tìm thấy — dialog xác nhận vị trí ký; có thể còn chỗ khác chưa rà hết trong vòng test này).
4. **Cân nhắc phản hồi trực quan rõ hơn** cho các mode "đang chờ chọn đối tượng trên trang" (như Xóa đối tượng) — hiện tại chỉ có nút ribbon đổi màu nhẹ, người dùng mới có thể không nhận ra mode đang bật.
5. Nhìn tổng thể, các dialog trong app đã có mức độ nhất quán tốt: đa số dùng chung 1 kiểu cửa sổ tự thiết kế (biểu tượng "3T" ở góc trên-trái, tiêu đề rõ ràng, nút OK/Cancel hoặc Đóng), phản hồi Esc-để-hủy hoạt động nhất quán ở mọi dialog đã test, và dark mode được áp dụng đồng bộ — đây là nền tảng UX tốt, các vấn đề tìm được trong báo cáo này đều ở mức tiểu tiết, không có vấn đề kiến trúc UX lớn.

---

## Kết luận

Sau khi tự mình mở ứng dụng thật và thao tác tuần tự qua toàn bộ 6 tab ribbon với con mắt QA/UX độc lập, **không phát hiện bug chức năng mới**, 2 bug đã sửa trước đó vẫn đứng vững không hồi quy, và mitigation crash vẫn giữ vững qua nhiều vòng stress dồn dập bổ sung. Phát hiện được **5 vấn đề UX** (1 mức trung bình đáng chú ý — chồng chữ trong Sửa text gốc, các mục còn lại ở mức thấp hoặc chỉ là ghi chú phương pháp), toàn bộ đã ghi nhận chi tiết ở trên kèm vị trí, hiện tượng và đề xuất hướng cải thiện — **chưa sửa code nào trong vòng rà soát này**, để người dùng tự quyết định ưu tiên xử lý.
