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

## 3. Đợt sửa lỗi Test Case QA — TC27–TC41 (06/07/2026, chờ tester retest)
- [x] **TC27** — Xóa nét bôi vẽ (highlight/gạch dưới/gạch ngang): click trái hoặc chuột phải trực tiếp vào nét vẽ → menu "🗑️ Xóa nét vẽ". Nét dài bị PDF tách thành nhiều khúc (`id-0`, `id-1`…) được chuẩn hóa về ID gốc nên xóa một phát là sạch cả nét, trên cả file PDF lẫn overlay UI. Click trái chỉ kích hoạt khi không kéo chọn chữ nên không ảnh hưởng bôi đen văn bản.
- [x] **TC28** — Tắt thanh tìm kiếm (Ctrl+F) hoặc xóa trắng ô tìm kiếm là highlight biến mất ngay: thêm `clear_search()` gửi query rỗng + `findbarclose`, reset `findController` và dọn class highlight còn sót trong text layer.
- [x] **TC29** — Hover vào vùng ghi chú/annotation có viền nét đứt xanh + đổ bóng icon để nhận biết (CSS `pdfjs_overrides.css`).
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
