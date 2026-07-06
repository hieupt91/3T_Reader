# Báo cáo sửa lỗi Test Case TC27–TC41 — Bàn giao Tester

**Ngày cập nhật:** 06/07/2026
**Nhánh:** `piper-vps-sync`
**Trạng thái chung:** Đã sửa xong 15/15 test case Fail — **chờ tester retest trên build mới**.

Tham chiếu chi tiết kỹ thuật từng lỗi: `BAO_CAO_TONG_HOP_PHAN_TICH_LOI.md` (phân tích) và `docs/2_DA_LAM.md` (mục 3 — nội dung đã sửa).

---

## Bảng trạng thái

| TC | Lỗi | Mức độ | Trạng thái | File chính đã sửa |
|---|---|---|---|---|
| TC27 | Thiếu nút xóa nét bôi vẽ | High | ✅ Đã sửa | `app/actions/annotate.py` |
| TC28 | Giữ màu highlight khi tắt search | Medium | ✅ Đã sửa | `app/actions/document.py`, `app/search_panel.py` |
| TC29 | Thiếu hiệu ứng hover vùng ghi chú | Low | ✅ Đã sửa | `assets/css/pdfjs_overrides.css` |
| TC30 | Sửa text gốc chập chờn | High | ✅ Đã sửa | `app/actions/edit.py` |
| TC31 | Preview font/in nghiêng sai | Medium | ✅ Đã sửa | `app/pdf_inline_editor.py`, `assets/js/inline_text_bridge.js` |
| TC32 | Đơ lag khi Undo nhiều nét vẽ | High | ✅ Đã sửa | `app/actions/annotate.py` |
| TC33 | Mất thumbnail sau đặt mật khẩu | Critical | ✅ Đã sửa | `app/actions/document_ops.py` |
| TC34 | Màn hình đen sau xóa mật khẩu | Critical | ✅ Đã sửa | `app/actions/document_ops.py` |
| TC35 | Xuất nhiều ảnh không gom ZIP | Low | ✅ Đã sửa | `app/actions/document_ops.py` |
| TC36 | OCR kém với font phức tạp | Medium | ✅ Đã sửa | `packages/ocr/engine.py` |
| TC37 | Mất lịch sử Chat PDF khi tắt luôn nổi | Critical | ✅ Đã sửa | `app/ai_chat_dialog.py` |
| TC38 | Không auto-OCR trước khi tóm tắt | Critical | ✅ Đã sửa | `app/ai_summarize_dialog.py` |
| TC39 | Không chuyển trang khi in 2 trang | Medium | ✅ Đã sửa | `app/window.py` |
| TC40 | Preview in ngang không đổi | Medium | ✅ Đã sửa | `app/window.py` |
| TC41 | Sai ngày kích hoạt khi cài lại | High | ✅ Đã sửa (chờ deploy VPS) | `vps_license_service.py`, `vps_models.py` |

---

## Checklist retest

### TC27 — Xóa nét bôi vẽ
1. Tạo highlight/gạch dưới/gạch ngang trên một dòng → click trái (hoặc chuột phải) vào nét → chọn "🗑️ Xóa nét vẽ" → nét biến mất ngay.
2. Tạo nét kéo qua nhiều dòng, click vào một khúc bất kỳ để xóa → toàn bộ nét biến mất, không sót khúc con.
3. Đóng mở lại file sau khi xóa → file thật không còn annotation.
4. Bôi đen chọn chữ đè lên vùng có highlight → thao tác chọn chữ vẫn bình thường (menu xóa không nhảy ra khi đang kéo chọn).

### TC28 — Clear highlight tìm kiếm
1. Ctrl+F, nhập từ khóa → bấm Đóng/Esc → highlight biến mất.
2. Ctrl+F, nhập từ khóa → xóa trắng ô tìm kiếm → highlight biến mất ngay.
3. Chuyển trang/zoom rồi lặp lại → highlight tạm không quay lại.

### TC29 — Hover ghi chú
1. Rê chuột vào icon/vùng ghi chú → có viền nét đứt xanh + hiệu ứng nhận biết; rời chuột → hết hiệu ứng.

### TC30 — Sửa text gốc
1. Chọn chế độ sửa text gốc, click nhiều vùng văn bản khác nhau (đầu dòng, cuối dòng, chữ nhỏ) → nhận diện đều, font/cỡ/màu lấy đúng theo chữ gốc.

### TC31 — Preview chèn chữ
1. Chọn công cụ chèn chữ → đổi font sang `Times New Roman`, `Calibri`, `Consolas` → preview đổi ngay.
2. Bật/tắt in nghiêng, đậm, gạch chân → preview phản ánh tức thời; mặc định KHÔNG nghiêng.
3. Chèn xong lưu, mở lại file, sửa lại text đã chèn → prefill giữ đúng font + in nghiêng.

### TC32 — Undo nét vẽ
1. Vẽ liên tục nhiều nét → Ctrl+Z nhanh nhiều lần → nét biến mất theo từng lần bấm, không đơ, không chớp trắng.
2. Đợi vài giây (autosave) rồi đóng/mở lại file → các nét đã Undo không còn trong PDF.

### TC33 / TC34 — Mật khẩu PDF
1. Đặt mật khẩu → thumbnail sidebar còn nguyên, nhảy trang bình thường.
2. File có mật khẩu → Xóa mật khẩu → nội dung hiển thị lại bình thường, không màn hình đen; thumbnail còn nguyên.
3. Làm liên tiếp: đặt pass → xóa pass → đặt lại → không lỗi.

### TC35 — Xuất ảnh
1. Xuất `Tất cả trang` hoặc dải `1-3` → thư mục đích chỉ có MỘT file `*_images.zip`, không có ảnh lẻ; mở ZIP đủ ảnh.
2. Xuất `Trang hiện tại` → vẫn ra một file ảnh đơn như cũ.

### TC36 — OCR font phức tạp
1. OCR file scan chất lượng thấp/font lạ → so kết quả với bản build cũ, kỳ vọng chính xác hơn rõ rệt.

### TC37 — Chat PDF luôn nổi
1. Chat vài câu → bật "luôn nổi" → tắt "luôn nổi" → lịch sử còn nguyên, nút đóng hoạt động.

### TC38 — Tóm tắt file scan
1. Mở PDF scan (toàn ảnh) → bấm Tóm tắt → hệ thống tự OCR ngầm rồi trả bản tóm tắt (không còn báo "không tìm thấy văn bản").
2. Máy chưa cài Tesseract → hiện hướng dẫn cài OCR thay vì lỗi khó hiểu.

### TC39 / TC40 — In ấn
1. Hộp thoại In → chế độ xem 2 trang → bấm "Trang sau/Trang trước" → nhảy đúng từng cặp trang.
2. Chọn in Ngang → preview xoay ngang theo ngay; bản in ra đúng hướng đã chọn.

### TC41 — Ngày kích hoạt license (cần deploy VPS trước)
1. Ghi lại ngày kích hoạt/hết hạn hiện tại của Key → gỡ app, cài lại, active lại Key cũ → ngày kích hoạt gốc và ngày hết hạn KHÔNG đổi.

---

## Verify dev đã chạy (06/07/2026)
- PASS: `py_compile` toàn bộ file Python đã sửa.
- PASS: `node --check assets/js/inline_text_bridge.js`.
- PASS: `pytest tests -q` → **244 passed, 24 skipped, 0 failed**.
- Các mục UI (toàn bộ 15 TC) bắt buộc retest thủ công trên build mới.

## Ghi chú triển khai
- **TC41 chỉ có hiệu lực sau khi deploy** `vps_license_service.py` + `vps_models.py` lên VPS license.
- Script deploy giờ đọc mật khẩu VPS từ biến môi trường: `$env:THREET_VPS_PASSWORD = "..."` (không còn hardcode).
- Nét vẽ/ghi chú tạo từ build cũ có thể mang màu/opacity cũ — retest với nét tạo mới trên build mới.
