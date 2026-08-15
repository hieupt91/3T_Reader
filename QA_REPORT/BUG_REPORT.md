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

### ✅ ĐÃ SỬA VÀ XÁC MINH (15/08/2026)

**Nguyên nhân gốc xác nhận:** `app/sidebar.py::ThumbnailSidebar._start_loader()`
**GHI ĐÈ** `self._pending_pages` thay vì **GỘP** khi có yêu cầu tải mới trong
lúc loader cũ còn chạy (vd. `scrollToItem()` lúc chọn trang kích hoạt nhiều
signal liên tiếp: `verticalScrollBar().valueChanged` + `highlight_page()` tự
gọi `_schedule_visible_load()`). Trang đã yêu cầu ở lần gọi trước nhưng chưa
kịp render bị rơi mất nếu lần tính lại phạm vi hiển thị sau không còn tính
trang đó vào — đúng khớp pattern "trang liền kề trang đang chọn luôn trắng"
quan sát được (biên của phạm vi hiển thị là nơi dễ lệch nhất giữa 2 lần tính
liên tiếp).

**Fix:** gộp `_pending_pages` (dùng `dict.fromkeys` giữ thứ tự, loại trùng),
chỉ bỏ trang đã thực sự render xong (`_loaded_pages`).

**Test:** `tests/test_sidebar_thumbnail_race.py` (3 test) — xác nhận cả 3 đều
**FAIL** trên code cũ (chưa fix) và **PASS** trên code đã fix, chứng minh test
bắt đúng bug, không phải test vô nghĩa.

**Verify bằng GUI thật, qua đúng luồng B53 delta-update (không rebuild
installer, đúng theo yêu cầu):**
1. Build lại `_internal` với fix → đóng gói code package delta (7.4MB, giảm
   ~98.5% so với installer full 486MB) → upload VPS → bật `delta_enabled` tạm
   thời trên admin-config.
2. App 1.0.33 đang cài thật trên máy tự phát hiện bản vá qua
   `/api/v2/update/check` → tải → verify SHA-256 + chữ ký Ed25519 → áp dụng
   → tự khởi động lại. **Toàn bộ luồng B53 chạy thật lần đầu tiên, không
   phải test giả lập.**
3. Lần thử đầu bị gián đoạn giữa chừng (dừng đúng lúc ghi file `.pyd` đầu
   tiên) → cơ chế rollback tự phát hiện và khôi phục đúng - **xác nhận an
   toàn của thiết kế hoạt động đúng** dù lần áp dụng đó không thành công.
4. Lần thử thứ 2 (kiên nhẫn hơn, không polling ngay sau khi bấm) → áp dụng
   **thành công hoàn toàn** — xác nhận qua `sidebar.pyc` trong
   `C:\Program Files\3T Reader\_internal\app\` có timestamp mới
   (14:17:51) thay vì bản gốc (11:52:32), và `state.json` báo
   `"status": "complete"`.
5. Đã tắt lại `delta_enabled=False` trên VPS sau khi test xong (khôi phục mặc
   định an toàn).

**Kết luận:** fix đã được xác nhận áp dụng thành công vào đúng bản cài thật
trên máy, thông qua đúng cơ chế cập nhật sẽ dùng cho người dùng thật sau này.

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
