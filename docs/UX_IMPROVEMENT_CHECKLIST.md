# 3T Reader — UX Improvement Checklist

> Checklist cải thiện trải nghiệm người dùng, so sánh với Foxit Reader / Adobe Acrobat.
> Mỗi mục có: mô tả vấn đề, ảnh hưởng UX, cách sửa, mức ưu tiên.
>
> **Ưu tiên:** `P0` = mất dữ liệu/blocker, `P1` = rất khó chịu, `P2` = khó chịu, `P3` = nhỏ nhặt

---

## 1. CHÈN TEXT — Thiếu trực quan, workflow phức tạp

### 1.1 Không thấy preview trước khi chèn

- [ ] **P1** — Sau khi gõ text trong overlay, user phải Ctrl+Enter → đợi rebuild → mới thấy kết quả trên PDF
  - **Vấn đề:** Không có "what you see is what you get" — user không biết text sẽ trông thế nào trước khi chèn
  - **So sánh:** Foxit hiện preview实时 trên PDF, Acrobat hiện bounding box rõ ràng
  - **Cách sửa:** Render text实时 trong overlay bằng canvas thay vì textarea, hoặc thêm preview panel bên cạnh

### 1.2 Overlay text quá nhỏ, khó thấy

- [ ] **P1** — Textarea overlay chỉ có border 2px solid #1A7AFF, rất dễ bỏ qua trên PDF có nhiều nội dung
  - **Vấn đề:** Không có badge label rõ ràng, không có animation attention-grab
  - **Cách sửa:** Thêm pulsing border animation, badge "VĂN BẢN MỚI" nổi bật, shadow lớn hơn

### 1.3 Font mặc định 14px — quá nhỏ cho nhiều PDF

- [ ] **P2** — Font size mặc định 14px, không tự động scale theo zoom level hoặc font size xung quanh
  - **Vấn đề:** User phải手动调整 size mỗi lần chèn
  - **Cách sửa:** Auto-detect font size từ text gần nhất, hoặc nhớ preference user

### 1.4 Không có font selection

- [ ] **P2** — Chỉ có font size, color, bold, underline — không có font family selection
  - **Vấn đề:** Không match font với nội dung hiện có trong PDF
  - **Cách sửa:** Thêm dropdown chọn font (Arial, Times New Roman, Courier, etc.)

### 1.5 Phím tắt không rõ ràng

- [ ] **P2** — Ctrl+Enter để chèn không hiển thị anywhere trong UI
  - **Vấn đề:** User phải đọc docs hoặc mò
  - **Cách sửa:** Hiển thị hint trong overlay: "Ctrl+Enter để chèn · Esc để hủy"

---

## 2. CHÈN ẢNH — Thiếu crop, compression

### 2.1 Không có crop功能

- [ ] **P1** — User只能resize整个ảnh, không crop được phần thừa
  - **So sánh:** Foxit cho phép crop trước khi chèn
  - **Cách sửa:** Thêm crop overlay trước khi chèn

### 2.2 Không có image compression

- [ ] **P2** — Ảnh 10MB sẽ chèn nguyên vào PDF → file PDF tăng size đáng kể
  - **Cách sửa:** Auto-compress ảnh về 150 DPI trước khi chèn, hoặc hỏi user quality

### 2.3 Không preview ảnh trước khi pick

- [ ] **P2** — File picker không có preview — user phải nhớ tên file
  - **Cách sửa:** Dùng QFileDialog với preview enabled

---

## 3. TÔ SÁNG (HIGHLIGHT) — Selection không ổn định

### 3.1 Selection hay mất khi scroll

- [ ] **P0** — PDF.js selection mất khi user scroll ra ngoài viewport → highlight thất bại
  - **Vấn đề:** `_get_selection_payload_sync()` đọc selection nhưng selection đã bị browser garbage collect
  - **Cách sửa:** Cache selection rects ngay khi selectionchange event fire, không đợi user click highlight

### 3.2 Error message không rõ ràng

- [ ] **P1** — "Da nhan duoc van ban boi den nhung chua lay duoc toa do tren trang PDF" — user không hiểu phải làm gì
  - **Cách sửa:** "Hãy bôi đen text trên trang PDF, sau đó nhấn nút Tô sáng. Nếu text quá dài, hãy chọn đoạn ngắn hơn."

### 3.3 Không có highlight color picker

- [ ] **P2** — Chỉ có 1 màu vàng mặc định, không cho user chọn màu
  - **So sánh:** Foxit có 5+ màu highlight
  - **Cách sửa:** Thêm color picker popup khi click highlight

### 3.4 Không có "highlight all occurrences"

- [ ] **P2** — Không có tính năng highlight tất cả occurrences của 1 từ
  - **So sánh:** Acrobat có "Highlight All" trong Find panel
  - **Cách sửa:** Thêm option "Tô sáng tất cả" khi search

---

## 4. CHỮ KÝ (SIGNATURE PAD) — Thiếu undo, smoothing

### 4.1 Không có undo — chỉ có clear all

- [ ] **P1** — Vẽ sai 1 nét → phải xóa toàn bộ và vẽ lại
  - **So sánh:** Foxit có multi-level undo cho signature drawing
  - **Cách sửa:** Lưu history các nét, thêm nút Undo (Ctrl+Z)

### 4.2 Không có line smoothing

- [ ] **P1** — Vẽ bằng chuột tạo ra đường răng cưa, không mượt
  - **Vấn đề:** Không có smoothing algorithm — raw mouse points
  - **Cách sửa:** Thêm Catmull-Rom hoặc Bezier smoothing cho nét vẽ

### 4.3 Không có pressure sensitivity

- [ ] **P2** — Nét vẽ đều 2px, không có biến thiên độ dày
  - **So sánh:** Acrobat hỗ trợ stylus pressure
  - **Cách sửa:** Tùy chọn pen size thay vì pressure (vì chuột không có pressure)

### 4.4 Không có resize/crop signature

- [ ] **P2** — Vẽ xong không crop được phần trắng thừa
  - **Cách sửa:** Auto-crop bounding box của nét vẽ, hoặc cho phép manual crop

### 4.5 Canvas quá nhỏ

- [ ] **P2** — Canvas 520x180px, rất khó vẽ chữ ký đẹp bằng chuột
  - **Cách sửa:** Tăng canvas size, hoặc cho phép zoom canvas

---

## 5. SIDEBAR — Thiếu tính năng

### 5.1 Không có drag-to-reorder pages

- [ ] **P1** — Không kéo thả trang để sắp xếp lại
  - **So sánh:** Foxit cho phép drag pages trong sidebar
  - **Cách sửa:** Thêm drag-and-drop trong QListWidget

### 5.2 Không có page context menu

- [ ] **P2** — Right-click thumbnail không có menu (delete, rotate, extract, insert after)
  - **Cách sửa:** Thêm QMenu với các thao tác trang

### 5.3 Không có bookmark editing

- [ ] **P2** — Chỉ hiển thị bookmarks, không thêm/sửa/xóa được
  - **So sánh:** Acrobat cho phép edit bookmarks
  - **Cách sửa:** Thêm right-click menu cho bookmarks

### 5.4 Thumbnail quality thấp

- [ ] **P2** — scale=0.3 rất mờ trên màn hình HiDPI
  - **Cách sửa:** Tăng scale lên 0.5 hoặc dùng devicePixelRatio

### 5.5 Không có search trong bookmarks

- [ ] **P3** — PDF có nhiều bookmarks → không search được
  - **Cách sửa:** Thêm search box filter

---

## 6. RIBBON BAR — Nhóm nút chưa rõ ràng

### 6.1 Nhóm nút quá nhiều trong 1 tab

- [ ] **P1** — Tab "Chỉnh sửa" có quá nhiều nút, không biết bắt đầu từ đâu
  - **Cách sửa:** Nhóm lại thành: "Văn bản" | "Ảnh" | "Vẽ" | "Đối tượng"

### 6.2 Icon không直观

- [ ] **P2** — Nhiều icon SVG custom, user không nhận ra chức năng
  - **Cách sửa:** Thêm text label rõ ràng hơn, hoặc dùng standard icons

### 6.3 Thiếu tooltips chi tiết

- [ ] **P2** — Tooltip chỉ có 1 dòng, không giải thích cách dùng
  - **Cách sửa:** Thêm multi-line tooltip với shortcut keys

### 6.4 Không có quick access toolbar

- [ ] **P3** — Không có thanh công cụ nhanh cho các thao tác hay dùng
  - **So sánh:** Foxit có Quick Access Toolbar
  - **Cách sửa:** Thêm customizable toolbar ở trên ribbon

---

## 7. AI FEATURES — Dialog UX kém

### 7.1 AI Settings dialog quá dài

- [ ] **P1** — Settings dialog có 7 providers, mỗi provider có 3-4 fields → scroll mỏi
  - **Cách sửa:** Tab-based hoặc accordion layout cho từng provider

### 7.2 Không có "Copy" button cho AI response

- [ ] **P2** — User phải manual select + copy text từ AI response
  - **Cách sửa:** Thêm nút Copy mỗi response block

### 7.3 Không có token/cost counter

- [ ] **P2** — Không biết đã dùng bao nhiêu tokens, tốn bao nhiêu tiền
  - **Cách sửa:** Hiển thị token count + estimated cost

### 7.4 AI Chat dialog không resizable

- [ ] **P3** — Dialog cố định kích thước, không resize được
  - **Cách sửa:** Cho phép resize + remember size

---

## 8. EXPORT — Thiếu options

### 8.1 Không có batch export

- [ ] **P2** — Chỉ export 1 file mỗi lần
  - **Cách sửa:** Thêm "Export All Pages" hoặc batch mode

### 8.2 Không có export quality settings

- [ ] **P2** — PDF→Image không cho chọn DPI/quality
  - **Cách sửa:** Thêm settings dialog với DPI slider (72-300)

### 8.3 Không có export preview

- [ ] **P3** — Không preview được trước khi export
  - **Cách sửa:** Thêm preview panel trong export dialog

---

## 9. GENERAL UX — Thông báo, phím tắt, trạng thái

### 9.1 Status messages quá ngắn

- [ ] **P1** — "Đã chèn văn bản" hiện 4 giây rồi biến mất — user không đọc kịp
  - **Cách sửa:** Tăng thời gian hiện, hoặc thêm notification panel

### 9.2 Error messages tiếng Việt không dấu

- [ ] **P1** — Nhiều error message thiếu dấu: "Khong tim thay tai lieu" thay vì "Không tìm thấy tài liệu"
  - **Vấn đề:** Thiếu chuyên nghiệp, user không hiểu
  - **Cách sửa:** Audit tất cả error messages, đảm bảo có dấu

### 9.3 Không có "Are you sure?" khi đóng file chưa lưu

- [ ] **P0** — Đóng tab khi có edits chưa lưu → mất dữ liệu không警告
  - **Cách sửa:** Thêm confirmation dialog: "Bạn có thay đổi chưa lưu. Lưu trước khi đóng?"

### 9.4 Không có recent files trong ribbon

- [ ] **P2** — Recent files chỉ trong welcome tab, không trong ribbon/menu
  - **Cách sửa:** Thêm Recent Files submenu trong File menu

### 9.5 Không có drag-drop file vào app

- [ ] **P2** — Không kéo thả file PDF vào cửa sổ để mở
  - **Cách sửa:** Thêm drag-drop support cho QWebEngineView

### 9.6 Zoom không giữ vị trí con trỏ

- [ ] **P2** — Ctrl+Scroll zoom nhảy về góc trái trên thay vì vị trí chuột
  - **Cách sửa:** Implement cursor-centered zoom

### 9.7 Không có "Go to page" input trong status bar

- [ ] **P3** — Phải dùng Ctrl+G dialog thay vì nhập trực tiếp
  - **Cách sửa:** Thêm page number input trong status bar

---

## 10. ANNOTATION PANEL — Thiếu quản lý

### 10.1 Không có annotation list panel

- [ ] **P1** — Không xem được danh sách tất cả annotations trong document
  - **So sánh:** Acrobat có Comments panel liệt kê tất cả
  - **Cách sửa:** Thêm panel hiển thị list annotations với filter (highlight/note/underline)

### 10.2 Không có annotation search

- [ ] **P2** — Không search được trong annotations
  - **Cách sửa:** Thêm search box trong annotation panel

### 10.3 Không có annotation export

- [ ] **P2** — Không export được annotations ra file riêng
  - **Cách sửa:** Thêm "Export Annotations" → JSON/FDF format

### 10.4 Không có annotation import

- [ ] **P3** — Không import annotations từ file khác
  - **Cách sửa:** Thêm "Import Annotations" từ FDF/JSON

---

## SUMMARY

| Priority | Count | Focus Area |
|----------|-------|------------|
| **P0** | 2 | Selection loss, data loss on close |
| **P1** | 12 | Preview, undo, error messages, UX flow |
| **P2** | 22 | Features, options, polish |
| **P3** | 8 | Nice-to-have |
| **Tổng** | **44** | |

---

## ƯU TIÊN THỰC HIỆN

### Phase 1 — Fix blockers (P0 + critical P1)
1. ✅ Fix selection loss khi scroll
2. ✅ Thêm "unsaved changes" confirmation
3. ✅ Fix error messages có dấu
4. ✅ Thêm hint text trong overlays

### Phase 2 — Core UX (P1)
5. ✅ Signature pad undo + smoothing
6. ✅ Highlight color picker
7. ✅ Annotation list panel
8. ✅ AI settings refactor

### Phase 3 — Polish (P2)
9. Image crop + compression
10. Sidebar enhancements
11. Export options
12. Drag-drop support

---

*Cập nhật: 2026-06-04*
