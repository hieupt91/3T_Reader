# Bug Report — 3T Reader 1.0.33

## BUG-01: Thumbnail của trang liền kề phía trên trang đang chọn không render (hiện trắng)

- **Severity:** P2 (không crash, không mất dữ liệu, nhưng gây khó hiểu — người
  dùng có thể tưởng trang đó trống/lỗi)
- **Title:** Panel thumbnail bên trái luôn để trắng đúng 1 thumbnail — vị trí
  ngay phía trên trang đang được chọn (highlight xanh)
- **Environment:** Windows 11, 3T Reader 1.0.33 (bản cài thật)
- **App version:** 1.0.33
- **Screen:** Thumbnail sidebar (bật qua nút "Thumbnail" trên ribbon)
- **Precondition:** Đã mở 1 file PDF nhiều trang, đã bật panel Thumbnail

### Các bước tái hiện chính xác

1. Mở file PDF ≥10 trang (đã test với file 50 trang).
2. Bấm "Trang sau" 5 lần liên tiếp (trang 1 → trang 6).
3. Bấm nút "Thumbnail" để mở panel bên trái.
4. **Quan sát:** thumbnail "Trang 5" (ngay phía trên "Trang 6" đang chọn,
   highlight xanh) hiện HOÀN TOÀN TRẮNG, trong khi "Trang 6", "Trang 7" hiện
   đúng nội dung.

### Reproduce #2 (trạng thái khác)

1. Từ trạng thái trên, bấm trực tiếp vào thumbnail "Trang 5" (dù đang trắng).
2. **Kết quả:** app điều hướng ĐÚNG sang trang 5 (nội dung trang chính hiện
   đúng "Trang so 5", page counter đúng "5/50") — logic điều hướng KHÔNG lỗi.
3. Nhưng giờ **"Trang 4"** (thumbnail ngay phía trên trang 5 vừa chọn) lại
   trắng, còn "Trang 5" (giờ đang chọn) đã render đúng.

→ **Pattern rõ ràng và tái hiện được 100%:** thumbnail ngay phía trên trang
đang chọn (highlight) không bao giờ render, bất kể đang ở trang nào. Đã chờ
thêm 3 giây, thumbnail vẫn không tự render — không phải do chậm/timing, là
lỗi logic thật (có khả năng lỗi tính sai biên viewport "visible" khi lazy-load
thumbnail, off-by-one ở item ngay phía trên item được chọn).

### Expected
Mọi thumbnail đang hiển thị trong viewport của panel phải render nội dung
đúng, không phụ thuộc vị trí tương đối với trang đang chọn.

### Actual
Thumbnail liền kề phía trên trang đang chọn luôn trắng.

### Reproducibility
**ALWAYS** — tái hiện 2/2 lần thử, ở 2 vị trí trang khác nhau (5→6 và 4→5).

### Screenshot
`screenshots/visual/06_thumbnail_view.png`,
`screenshots/bugs/bug01_thumbnail_blank_recheck.png`,
`screenshots/bugs/bug01_after_click_page5_thumb.png`

### Impact
Thấp-trung bình: không ảnh hưởng nội dung/dữ liệu thật, chỉ ảnh hưởng UI
thumbnail. Có thể khiến người dùng nghĩ nhầm 1 trang bị lỗi/trống khi thực ra
không phải.

### Suggested investigation area
Code xử lý render/lazy-load thumbnail trong sidebar (`app/sidebar.py` theo
cấu trúc module đã biết) — kiểm tra logic tính range "trang cần render" quanh
trang đang chọn, khả năng cao đang tính range kiểu `[current-N, current+N]`
nhưng lệch 1 ở biên trên, hoặc thumbnail của trang N-1 bị "unload" nhầm khi
trang N được chọn nhưng chưa kịp "load" lại.

### ⚠️ Fix lần 1 (15/08/2026, đã lên bản 1.0.34) — KHÔNG ĐỦ, bug vẫn còn

**Nguyên nhân từng nghi:** `app/sidebar.py::ThumbnailSidebar._start_loader()`
**GHI ĐÈ** `self._pending_pages` thay vì **GỘP** khi có yêu cầu tải mới trong
lúc loader cũ còn chạy. Đã sửa (gộp bằng `dict.fromkeys`) và có test
`tests/test_sidebar_thumbnail_race.py` (3 test, PASS). Fix này **có thật và
đúng** cho 1 race điều kiện phụ (mất trang khỏi hàng đợi tải khi bị interrupt
giữa chừng) — nhưng **KHÔNG PHẢI nguyên nhân của BUG-01**. Bản 1.0.34 đã lên
VPS/cài thật với fix này, nhưng khi re-test trực tiếp trên app đã cài (không
chỉ code review) thì **bug tái hiện y hệt** — icon vẫn được set đúng vào model
(`_append_thumbnail` chạy đúng, dữ liệu pixel xác nhận hợp lệ qua debug log)
nhưng vẫn không hiện lên màn hình. → Bài học: fix hợp lý + có unit test PASS
không đồng nghĩa đã sửa đúng bug quan sát được — phải verify lại bằng GUI thật.

### ✅ Fix lần 2 (15/08/2026) — nguyên nhân gốc thật sự, đã xác minh hết bug

**Nguyên nhân gốc xác nhận:** `QListWidget::scrollToItem()` với
`ScrollHint.PositionAtCenter` dùng đường cuộn "tối ưu" nội bộ của Qt (cuộn/blit
phần ảnh cũ sang vị trí mới rồi CHỈ vẽ lại đúng dải pixel mới lộ ra, thay vì vẽ
lại toàn bộ viewport) — nhưng Qt tính sai dải "mới lộ ra" đó, luôn bỏ sót đúng
1 item: item ngay PHÍA TRÊN item vừa được chọn/cuộn tới. Icon của item đó đã
tồn tại đúng trong model từ trước (`QListWidgetItem.setIcon()` đã chạy, dữ liệu
pixel hợp lệ — xác nhận qua debug print `min=0 max=255` cho mọi trang, kể cả
trang bị trắng) nhưng nằm ngoài vùng Qt quyết định vẽ lại nên không bao giờ
hiện, **bất kể gọi `viewport().update()`, `viewport().repaint()` (đồng bộ),
`doItemsLayout()` (buộc tính lại toàn bộ layout), hay gán lại 1 `QIcon` hoàn
toàn mới cho item đó bao nhiêu lần cũng không ăn thua** — vì vấn đề nằm ở
chính logic nội bộ `scrollToItem(PositionAtCenter)` tính sai vùng cần vẽ lại,
không phải ở dữ liệu, ở cache icon, hay ở việc thiếu 1 lệnh vẽ lại.

**Cách xác nhận (loại trừ từng giả thuyết bằng debug thật, không đoán):**
1. Debug print xác nhận `_append_thumbnail()` luôn chạy đúng, icon không null,
   pixel data hợp lệ (`min=0 max=255`) — kể cả cho trang đang bị hiện trắng.
2. Thử `self.list.viewport().update()` ngay sau `scrollToItem()` — không hết.
3. Thử thêm `self.list.doItemsLayout()` sau mỗi lần set icon — không hết.
4. Thử hoãn sang vòng lặp sự kiện kế tiếp (`QTimer.singleShot(0, ...)`) rồi
   gọi `viewport().repaint()` đồng bộ — không hết.
5. Dùng `self.list.viewport().grab()` (chụp trực tiếp từ bộ máy vẽ Qt, KHÔNG
   qua chụp màn hình OS) để loại trừ khả năng đây chỉ là lỗi chụp
   ảnh/compositing của Windows — vẫn trắng → xác nhận đây là lỗi vẽ thật bên
   trong Qt, không phải lỗi công cụ QA.
6. Điều hướng trực tiếp tới đúng trang đang bị trắng (bấm "Trang trước") — nó
   HẾT trắng và hiện đúng, nhưng trang NGAY PHÍA TRÊN nó (giờ không còn được
   chọn) lại trắng thay thế → xác nhận pattern là "item phía trên item vừa
   được chọn/cuộn tới", không phải gắn với 1 số trang cụ thể nào.
7. Đổi `ScrollHint.PositionAtCenter` → `ScrollHint.EnsureVisible` (không dùng
   đường cuộn tối ưu blit đó) — **hết bug ngay, không cần thêm bất kỳ workaround
   nào khác.**

**Fix thật:** `app/sidebar.py::ThumbnailSidebar.highlight_page()` — đổi
`QListWidget.ScrollHint.PositionAtCenter` → `QListWidget.ScrollHint.EnsureVisible`.
Đã test thêm: nhảy xa (trang 1 → trang 40 qua ô nhập số trang) vẫn cuộn đúng,
không còn thumbnail trắng ở trang liền kề.

**Test:** đã chạy lại toàn bộ `tests/` (415 test) sau fix — không có regression
(1 lần fail ở `test_single_instance.py` do tiến trình dev-mode debug còn sống
giữ socket, không liên quan sidebar.py — chạy lại riêng PASS sau khi đóng tiến
trình đó).

**Kết luận:** đã xác minh hết bug bằng GUI thật (dev-mode, lặp lại nhiều lần,
nhiều vị trí trang, cả nhảy trang gần lẫn xa) trước khi build lại bản cài đặt.

---

## BUG-02 (mới phát hiện trong lúc test B53, không liên quan BUG-01): App chạy quyền Administrator sau khi tự khởi động lại từ bản vá delta

- **Severity:** P2 (không crash, nhưng vi phạm nguyên tắc least-privilege và
  phá vỡ khả năng tương tác từ tiến trình quyền thường - vd. accessibility
  tool, automation, script khác)
- **Root cause:** `packages/updater/delta_runtime.py::run_apply_helper_from_argv()`
  gọi `subprocess.Popen([executable], ...)` để tự khởi động lại app sau khi
  vá xong - nhưng lệnh này chạy BÊN TRONG chính helper đã được UAC elevate
  (`spawn_apply_helper` dùng `ShellExecuteW(..., "runas", ...)`), nên tiến
  trình app relaunch KẾ THỪA token elevated, tiếp tục chạy với quyền
  Administrator vô thời hạn dù việc ghi file vào Program Files đã xong.
- **Phát hiện qua:** khi cố verify BUG-01 bằng GUI automation sau khi delta
  áp dụng thành công, không thể tương tác được với app nữa dù app hiển thị
  bình thường trên màn hình - `Stop-Process`, `taskkill`, UI Automation
  `FindAll` đều báo "Access is denied"/trả về rỗng - đúng đặc trưng của
  Windows UIPI (User Interface Privilege Isolation) chặn tiến trình quyền
  thường tương tác với cửa sổ quyền cao hơn.
- **Fix:** thêm `_launch_deelevated()` - route việc relaunch qua COM
  `Shell.Application.ShellExecute(...)` (chạy ở integrity level của
  Explorer, không kế thừa token elevated của helper) thay vì
  `subprocess.Popen()` thẳng. Có fallback về `subprocess.Popen()` cũ nếu
  COM lỗi vì bất kỳ lý do gì (thà chạy quyền cao hơn cần thiết còn hơn app
  không tự mở lại được).
- **Test:** `tests/test_delta_elevation.py` (2 test mới) - xác nhận
  `_launch_deelevated()` gọi đúng Shell.Application COM, không rơi xuống
  `subprocess.Popen()` khi COM khả dụng; và có fallback đúng khi COM lỗi.
- **Lưu ý quan trọng:** `delta_runtime.py` là 1 trong các file **bất biến**
  (không bao giờ được phép tự vá qua chính cơ chế delta nó tạo ra - xem
  `_IMMUTABLE_PATHS`) - fix này **chỉ tới tay người dùng qua bản cài đặt
  đầy đủ tiếp theo**, không thể tự vá qua delta. Chưa verify lại bằng GUI
  thật (cần 1 vòng build+cài lại đầy đủ khác để test) - chỉ mới test ở mức
  unit test.

---

## Không tìm thấy bug P0/P1 nào trong phạm vi đã test

Không crash, không treo UI, không mất dữ liệu, không lỗi bảo mật quan sát
được trong các luồng đã thao tác thật (mở file thường/nặng/hỏng, zoom stress,
tab switch, window resize, đóng app).
