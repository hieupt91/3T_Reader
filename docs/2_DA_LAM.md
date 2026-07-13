# 2. DANH SÁCH CÁC HẠNG MỤC ĐÃ HOÀN THÀNH (ĐẾN THỜI ĐIỂM HIỆN TẠI)

## 1. Giao diện & Trải nghiệm (UI/UX)
- [x] Tích hợp bộ Giao diện Sáng/Tối (Light/Dark Mode) đồng bộ với hệ thống.
- [x] Tạo thanh công cụ Ribbon chuyên nghiệp mô phỏng MS Office.
- [x] Tính năng "Zero-reload Rotation": Xoay trang PDF lập tức bằng CSS Transform mà không bị khựng hình (Đã fix lỗi đồng bộ cho cả Thumbnail bên cột trái).
- [x] Xóa bỏ lỗi viền trắng dọc mép giấy khi cuộn PDF trong chế độ Dark mode.
- [x] Tháo gỡ các khóa tính năng ảo (Freemium bypass) giúp mọi nút bấm hoạt động thông suốt.

## 2. Tính năng Nâng cao (Advanced Features)
- [x] **Trợ lý AI:** Tích hợp AI Chat với PDF, Dịch thuật, Tóm tắt toàn bộ tài liệu, Tìm kiếm ngữ nghĩa (Semantic Search).
- [x] **Nhận dạng văn bản (OCR):** Tích hợp engine Tesseract OCR, hỗ trợ tự động tải engine chạy ngầm mà không cần cài đặt bằng tay.
- [x] **Ký số toàn diện:**
  - Ký bằng USB Token qua thư viện chuẩn PKCS#11 (Dành riêng cho máy Windows).
  - Ký bằng file chứng thư số `.pfx`.
  - Ký tay và chèn con dấu công ty.
  - Tích hợp chuẩn LTV (Long-Term Validation) và TSA (Time-Stamping Authority).
  - Khắc phục triệt để lỗi crash giao diện PDF.js khi load các file chứa chữ ký số phức tạp (Bằng cách chuyển Widget thành Stamp).
- [x] **Ký lô (Batch Sign):** Tự động ký hàng trăm file PDF cùng lúc trong một thư mục.

## 3. Auto-OCR khi mở file (06/07/2026, chờ tester retest)
- [x] **OCR nền tự động ngay khi mở file scan** (`app/actions/auto_ocr.py`, mới): với file scan (ảnh thuần, không có text layer), ứng dụng tự OCR ngầm ngay khi mở, không cần bấm nút nào. Trang đang xem được OCR trước tiên để bôi đen/tìm kiếm/sửa text hoạt động sớm nhất, các trang còn lại xử lý dần ở nền.
- [x] Kết quả OCR được ghi thành **text layer vô hình, định vị đúng theo từng từ** vào file PDF thật (dùng chế độ xuất `textonly_pdf` có sẵn của Tesseract, ghép bằng `pikepdf.Page.add_overlay`) — nhờ vậy tìm kiếm (Ctrl+F), bôi đen/gạch dưới/gạch ngang và **sửa text gốc (TC30)** đều hoạt động trên file scan như file PDF thường, không cần code riêng cho từng tính năng.
- [x] Idempotent theo thiết kế: trước khi OCR một trang, hệ thống kiểm tra trang đã có text chưa (`page_has_text`) — mở lại file đã xử lý sẽ tự bỏ qua, không tốn công OCR lại.
- [x] Ghi PDF dùng chung hàng đợi autosave chú thích sẵn có nên không xung đột với các thao tác ghi file khác (highlight, ghi chú...) đang chạy song song.
- [x] **Mở cho mọi gói license** (không giống OCR thủ công toàn tài liệu/1 trang trong menu, vẫn khóa Personal/Enterprise như cũ) — vì đây là nền tảng để tính năng cơ bản (bôi đen, sửa text) hoạt động, không phải tính năng OCR độc lập.
- Đã kiểm chứng bằng test thực tế (không chỉ lý thuyết): tạo PDF giả lập chỉ có ảnh chữ, chạy OCR + ghép text layer, xác nhận text trích xuất được khớp chính xác nội dung ảnh.

## 4. Đợt sửa lỗi Test Case QA — TC27–TC41 (06/07/2026, chờ tester retest)
- [x] **TC27** — Xóa nét bôi vẽ (highlight/gạch dưới/gạch ngang): click trái hoặc chuột phải trực tiếp vào nét vẽ → menu "🗑️ Xóa nét vẽ" / "🧹 Xóa toàn bộ highlight trên trang". Nét dài bị PDF tách thành nhiều khúc (`id-0`, `id-1`…) được chuẩn hóa về ID gốc nên xóa một phát là sạch cả nét, trên cả file PDF lẫn overlay UI. Click trái chỉ kích hoạt khi không kéo chọn chữ nên không ảnh hưởng bôi đen văn bản. Annotation PDF nay ghi thêm opacity `/CA` (0.60 highlight, 0.9 gạch dưới/ngang) và `/Contents` nên màu không đổi và xóa được cả sau khi đóng/mở lại file. Thêm nút **"Chế độ: Chọn/Tìm"** trên Ribbon: chế độ Tìm tô/gạch (và xóa) toàn bộ từ khóa trên tài liệu thay vì chỉ vùng bôi đen.
  - *Bản vá 06/07 (chiều):* phát hiện và sửa bug chặn toàn bộ chức năng xóa — `app/webchannel.py` dùng proxy WebChannel ổn định (`_NoteToolsBridgeProxy`) đứng giữa JS và backend; slot `deleteMark`/`deleteMarksOnPage` mới thêm vào backend nhưng thiếu trong proxy khiến JS báo lỗi `bridge.deleteMark is not a function`. Đã bổ sung 2 slot vào proxy.
- [x] **TC28** — Tắt thanh tìm kiếm (Ctrl+F) hoặc xóa trắng ô tìm kiếm là highlight biến mất ngay: thêm `clear_search()` gửi query rỗng + `findbarclose`, reset `findController` và dọn class highlight còn sót trong text layer. Thêm nút **"Tô sáng tất cả"** trên thanh tìm kiếm — quét và lưu toàn bộ kết quả tìm được thành nét vẽ thật (khác với highlight tạm của Ctrl+F).
- [x] **TC29** — Hover vào icon ghi chú tô sáng đúng **vùng chữ đã bôi đen lúc tạo ghi chú** (lưu `target_rects`), không chỉ viền quanh icon. Rê chuột lên nét tô sáng/gạch dưới/gạch ngang không hiện tooltip/preview (chỉ đổi con trỏ, click để xóa như cũ).
- [x] **TC30** — Sửa text gốc ổn định hơn: chấp nhận sai số ±5pt khi khớp bounding box (PDF.js lệch 1–2pt so với bbox thật), kéo dài hạn cache selection 10s→30s và timeout đọc selection 500ms→900ms để thao tác qua nút Ribbon không bị trượt.
- [x] **TC31** — Preview chèn chữ đúng font và in nghiêng: truyền cấu hình font bằng JSON payload (an toàn với font có khoảng trắng), JS apply đủ `fontStyle`/`fontFamily` cả khi gõ mới lẫn khi sửa lại text đã chèn (prefill).
- [x] **TC32** — Undo nhiều nét vẽ không còn đơ: overlay bị xóa tức thời trên UI, các lần Ctrl+Z liên tục được debounce 520ms gom thành một lần lưu PDF + một lần soft reload duy nhất.
- [x] **TC33** — Đặt mật khẩu PDF không mất thumbnail: sau khi mã hóa file gốc, app giữ bản snapshot đã giải mã làm file xem tạm và reload viewer + sidebar từ đó (cùng cơ chế như khi mở file có mật khẩu).
- [x] **TC34** — Xóa mật khẩu không còn màn hình đen: nguyên nhân là sau khi nhả khóa file, webview đang ở `about:blank` mà luồng cũ lại soft-reload bằng JS trên trang trắng. Đã đổi sang hard-load file đã giải mã kèm cơ chế retry-if-blank.
- [x] **TC35** — Xuất nhiều trang ra ảnh tự động gom vào một file ZIP (ghi thẳng vào ZIP, không rải ảnh lẻ; tên ZIP tự thêm hậu tố `_2`, `_3` nếu trùng; Explorer mở và chọn thẳng file kết quả). Xuất 1 trang giữ hành vi cũ.
- [x] **TC36** — OCR nhận diện tốt hơn với font phức tạp: thêm bước tiền xử lý ảnh (grayscale + autocontrast, denoise median cho chế độ chất lượng cao) trước khi đưa vào Tesseract.
- [x] **TC37** — Bật/tắt "luôn nổi" của Chat PDF không mất lịch sử: lịch sử chat lưu trong session Python (tách state khỏi view), sau khi Qt recreate cửa sổ sẽ rebuild lại nội dung từ session.
- [x] **TC38** — Tóm tắt file PDF scan tự động chạy OCR ngầm (trong worker thread, dừng khi đủ 6000 ký tự) rồi mới tóm tắt; text OCR cũng dùng cho trích xuất dữ liệu hợp đồng. Máy chưa cài Tesseract thì báo hướng dẫn rõ ràng.
- [x] **TC39** — Preview in ở chế độ 2 trang chuyển trang đúng: nút Trước/Sau dùng `nextPage()/previousPage()` của PDF.js (tự nhảy đủ một spread) thay vì ±1 số trang.
- [x] **TC40** — Chọn in ngang/dọc thấy preview đổi theo ngay (xoay trang preview 90°) và toàn bộ job in giữ đúng hướng đã chọn (ảnh trang được xoay để khớp khổ giấy).
- [x] **TC41** — Ngày kích hoạt license không còn lệch khi gỡ app cài lại: server lưu `first_activated_at` của lần kích hoạt đầu tiên và neo `expires_at` theo mốc đó (có backfill cho key cũ). **Lưu ý: cần deploy `vps_license_service.py` + `vps_models.py` lên VPS mới có hiệu lực.**
- [x] Dọn dẹp kèm theo: sửa mojibake tiếng Việt trong API (`main_api.py`), bỏ fallback mật khẩu admin hardcode, gỡ mật khẩu VPS hardcode khỏi các script deploy (chuyển sang biến môi trường `THREET_VPS_PASSWORD` qua `vps_secret.py`), đồng bộ version 1.0.24 về `app/version.py` (single source of truth), lọc language pack bị lỗi encoding.

## 4. Hệ thống máy chủ & Dữ liệu (Backend & Infra)
- [x] **API Cấp Key:** Code chuẩn FastAPI trên VPS. Logic tự động phát sinh mã đơn hàng (ORD-xxx) và cấp Key theo từng gói (3TR-E, 3TR-P, 3TR-B).
- [x] **Hệ thống check Update:** Cập nhật ngầm (Silent check update) và tự động tải file thực thi để nâng cấp phiên bản.
- [x] **Hệ thống gửi Email:** Tự động gửi Email cấp Key bản quyền cho khách hàng và thông báo cho Admin khi có đơn hàng mới.
- [x] Đã hoàn thiện script cài đặt và release bản build Windows `.exe`.
