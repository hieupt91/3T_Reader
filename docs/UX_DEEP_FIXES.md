# 3T Reader — Deep UX Fixes (Code-Level Checklist)

> Checklist chi tiết đến file, dòng code, cách sửa cụ thể cho từng vấn đề UX.

---

## FIX 1: Selection loss khi scroll (P0)

**File:** `app/pdf_viewer.py` + `assets/js/pdfjs_ui_hooks.js`
**Vấn đề:** PDF.js selection bị garbage collect khi scroll → `_get_selection_payload_sync()` trả về rỗng
**Cách sửa:**
- [x] Trong `pdfjs_ui_hooks.js`: cache selection rects ngay khi `selectionchange` fire, không đợi Python query
- [x] Tăng cache timeout từ 15s lên 60s
- [x] Thêm fallback: nếu rects rỗng, dùng `window.getSelection().getRangeAt(0).getClientRects()` để rebuild

```javascript
// Trong selectionchange handler — cache ngay:
document.addEventListener('selectionchange', function() {
    var sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
        var payload = collectSelectionPayload();
        if (payload.rects.length > 0) {
            payload.timestamp = Date.now();
            window.__3tLastSelectionPayload = payload;
        }
    }
}, true);
```

---

## FIX 2: Unsaved changes confirmation (P0)

**File:** `app/window.py`
**Vấn đề:** Đóng tab/file khi có edits chưa lưu → mất dữ liệu
**Cách sửa:**
- [x] Override `closeEvent()` trong `PDFReaderApp`
- [x] Check `_get_edit_state()` hoặc `_annotation_undo_stack`
- [x] Hiện confirmation dialog: "Bạn có thay đổi chưa lưu. Lưu trước khi đóng?"

```python
def closeEvent(self, event):
    if self._has_unsaved_changes():
        reply = QMessageBox.question(
            self, "Chưa lưu thay đổi",
            "Bạn có thay đổi chưa lưu. Lưu trước khi đóng?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Save:
            self._save_current_file()
        elif reply == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
    event.accept()
```

---

## FIX 3: Error messages có dấu (P1)

**File:** Tất cả files trong `app/actions/`
**Vấn đề:** Nhiều string thiếu dấu tiếng Việt
**Cách sửa:** Audit và fix tất cả strings thiếu dấu:

| File | Line | Hiện tại | Sửa thành |
|------|------|----------|-----------|
| `annotate.py:109` | `"Da tu dong luu chu thich."` | `"Đã tự động lưu chú thích."` |
| `annotate.py:114` | `"Chua luu duoc chu thich, se thu lai: {exc}"` | `"Chưa lưu được chú thích, sẽ thử lại: {exc}"` |
| `annotate.py:173-176` | `"Mot so thay doi chu thich chua luu xong..."` | `"Một số thay đổi chú thích chưa lưu xong..."` |
| `annotate.py:825` | `"Da sua ghi chu trang"` | `"Đã sửa ghi chú trang"` |
| `annotate.py:835` | `"Chua luu xong cac thay doi ghi chu..."` | `"Chưa lưu xong các thay đổi ghi chú..."` |
| `annotate.py:855` | `"Da xoa ghi chu trang"` | `"Đã xóa ghi chú trang"` |
| `annotate.py:1865-1880` | `"gach duoi"`, `"gach ngang"`, `"to sang"` | `"gạch dưới"`, `"gạch ngang"`, `"tô sáng"` |
| `annotate.py:1887` | `"Khong tim thay tai lieu dang mo."` | `"Không tìm thấy tài liệu đang mở."` |
| `annotate.py:1896-1898` | `"Da nhan duoc van ban boi den..."` | `"Đã nhận được văn bản bôi đen..."` |
| `signature_pad.py:164` | `"Quan ly mau chu ky"` | `"Quản lý mẫu chữ ký"` |
| `signature_pad.py:170` | `"Tao, them, sua, xoa va chon mau chu ky:"` | `"Tạo, thêm, sửa, xóa và chọn mẫu chữ ký:"` |
| `signature_pad.py:176-181` | `"Tao bang ve tay"`, `"Them tu anh"`, etc. | `"Tạo bằng vẽ tay"`, `"Thêm từ ảnh"`, etc. |

---

## FIX 4: Overlay hint text (P1)

**File:** `assets/js/inline_text_bridge.js`
**Vấn đề:** User không biết Ctrl+Enter để chèn
**Cách sửa:**
- [x] Thêm hint badge trong overlay: `"✏️ Ctrl+Enter để chèn · Esc để hủy"`
- [x] Thêm hint trong image overlay: `"🖼️ Enter để chèn · Esc để hủy"`

```javascript
// Trong inline_text_bridge.js — thêm hint badge:
var hint = document.createElement('div');
hint.textContent = 'Ctrl+Enter để chèn · Esc để hủy';
hint.style.cssText = 'position:absolute;bottom:-22px;left:0;white-space:nowrap;'
    + 'font-size:9px;color:#888;background:transparent;pointer-events:none;';
ov.appendChild(hint);
```

---

## FIX 5: Signature pad undo + smoothing (P1)

**File:** `app/signature_pad.py`
**Vấn đề:** Không có undo, đường vẽ răng cưa
**Cách sửa:**

### 5a. Undo
- [x] Thêm `_strokes: list[list[QPoint]]` trong `DrawingCanvas`
- [x] Mỗi `mouseReleaseEvent` → append stroke mới
- [x] `undo()` → pop stroke cuối, redraw
- [x] Thêm Ctrl+Z shortcut

```python
def __init__(self, ...):
    ...
    self._strokes: list[list[QPoint]] = []
    self._current_stroke: list[QPoint] = []

def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
        self._drawing = True
        self._current_stroke = [event.position().toPoint()]
        self._has_content = True

def mouseReleaseEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
        self._drawing = False
        if self._current_stroke:
            self._strokes.append(self._current_stroke)
            self._current_stroke = []

def undo(self):
    if self._strokes:
        self._strokes.pop()
        self._redraw_all()

def _redraw_all(self):
    self._image.fill(self._bg_color)
    p = QPainter(self._image)
    pen = QPen(self._pen_color, self._pen_size, ...)
    p.setPen(pen)
    for stroke in self._strokes:
        for i in range(1, len(stroke)):
            p.drawLine(stroke[i-1], stroke[i])
    p.end()
    self.update()
    self._has_content = bool(self._strokes)
```

### 5b. Line smoothing
- [x] Thêm Catmull-Rom smoothing trong `mouseMoveEvent`

```python
def mouseMoveEvent(self, event):
    if self._drawing:
        point = event.position().toPoint()
        self._current_stroke.append(point)
        # Smooth: dùng 4 điểm gần nhất
        if len(self._current_stroke) >= 4:
            p0 = self._current_stroke[-4]
            p1 = self._current_stroke[-3]
            p2 = self._current_stroke[-2]
            p3 = self._current_stroke[-1]
            # Catmull-Rom interpolation
            for t in [0.25, 0.5, 0.75]:
                x = catmull_rom(p0.x(), p1.x(), p2.x(), p3.x(), t)
                y = catmull_rom(p0.y(), p1.y(), p2.y(), p3.y(), t)
                # Draw smoothed segment
        ...
```

---

## FIX 6: Highlight color picker (P1)

**File:** `app/actions/annotate.py`
**Vấn đề:** Chỉ có 1 màu vàng mặc định
**Cách sửa:**
- [x] Thêm `_highlight_colors` dict với 5+ màu
- [x] Hiện popup menu khi click highlight button
- [x] Lưu preference user

```python
_HIGHLIGHT_COLORS = {
    "yellow":  {"pdf": [1.0, 1.0, 0.0], "overlay": "rgba(250,204,21,.35)", "label": "Vàng"},
    "green":   {"pdf": [0.0, 1.0, 0.0], "overlay": "rgba(34,197,94,.35)",  "label": "Xanh lá"},
    "blue":    {"pdf": [0.0, 0.5, 1.0], "overlay": "rgba(59,130,246,.35)", "label": "Xanh dương"},
    "pink":    {"pdf": [1.0, 0.4, 0.7], "overlay": "rgba(236,72,153,.35)", "label": "Hồng"},
    "orange":  {"pdf": [1.0, 0.6, 0.0], "overlay": "rgba(249,115,22,.35)", "label": "Cam"},
}
```

---

## FIX 7: Thumbnail quality (P2)

**File:** `app/sidebar.py:31`
**Vấn đề:** `scale=0.3` rất mờ trên HiDPI
**Cách sửa:**
- [x] Dùng `devicePixelRatio()` để tính scale phù hợp

```python
from packages.qt_compat.QtWidgets import QApplication
screen = QApplication.primaryScreen()
dpi_ratio = screen.devicePixelRatio() if screen else 1.0
scale = 0.3 * dpi_ratio  # HiDPI → 0.6, thường → 0.3
rendered = doc.render_page_rgb(page_number, scale=scale)
```

---

## FIX 8: Page context menu (P2)

**File:** `app/sidebar.py`
**Vấn đề:** Right-click thumbnail không có menu
**Cách sửa:**
- [x] Thêm `contextMenuEvent` trong `ThumbnailSidebar`
- [x] Menu items: Xóa trang, Xoay, Trích xuất, Chèn trang sau

```python
def contextMenuEvent(self, event):
    item = self.list.itemAt(event.pos())
    if not item:
        return
    page_no = self.list.row(item) + 1
    menu = QMenu(self)
    menu.addAction("Xóa trang", lambda: self._delete_page(page_no))
    menu.addAction("Xoay 90°", lambda: self._rotate_page(page_no))
    menu.addAction("Trích xuất", lambda: self._extract_page(page_no))
    menu.exec(event.globalPos())
```

---

## FIX 9: Annotation list panel (P1)

**File:** Tạo mới `app/annotation_panel.py`
**Vấn đề:** Không xem được danh sách annotations
**Cách sửa:**
- [x] Tạo `AnnotationPanel(QDockWidget)` hiển thị list annotations
- [x] Filter theo type (highlight/note/underline/strikeout)
- [x] Click → navigate đến annotation
- [x] Right-click → edit/delete

---

## FIX 10: AI Settings refactor (P1)

**File:** `app/actions/ai_actions.py`
**Vấn đề:** Settings dialog quá dài, 7 providers trong 1 scroll
**Cách sửa:**
- [x] Tách thành tabs: "OpenAI" | "Anthropic" | "Gemini" | "Khác"
- [x] Mỗi tab chỉ hiện fields cho provider đó
- [x] Thêm "Test Connection" button cho mỗi provider

---

## FIX 11: Unsaved annotation warning (P1)

**File:** `app/actions/annotate.py`
**Vấn đề:** Annotations trong queue chưa flush → user đóng file → mất
**Cách sửa:**
- [x] Trong `_AnnotationOpQueue.flush()`: nếu fail, hiện warning rõ ràng
- [x] Thêm `_has_pending_annotations()` check trước khi đóng file

---

## FIX 12: Zoom centered on cursor (P2)

**File:** `app/window.py` (zoom handlers)
**Vấn đề:** Ctrl+Scroll zoom về góc trái trên
**Cách sửa:**
- [x] Lấy cursor position trước khi zoom
- [x] Sau zoom, scroll để cursor position giữ nguyên

---

## FIX 13: Highlight/Underline/Strikeout icons giống nhau (P1)

**File:** `app/window.py:662-670`
**Vấn đề:** Cả 3 nút dùng cùng `highlight.svg`, chỉ khác màu (vàng/xanh/đỏ) — ở 28px rất khó phân biệt
**So sánh:** Foxit dùng icon khác nhau cho mỗi tool
**Cách sửa:**
- [x] Tạo `underline.svg`, `strikeout.svg` riêng biệt
- [x] Hoặc thêm text label rõ ràng hơn

---

## FIX 14: Thiếu keyboard shortcuts cho annotation tools (P1)

**File:** `app/window.py:599-766`
**Vấn đề:** Highlight, underline, strikeout, insert text, insert image không có phím tắt
**So sánh:** Acrobat có Ctrl+U cho underline
**Cách sửa:**
- [x] Ctrl+Alt+H (highlight), Ctrl+Alt+U (underline), Ctrl+Alt+K (strikeout)
- [x] Hiển thị shortcut trong tooltip

---

## FIX 15: Text edit dialog nói "Lưu thay đổi" khi tạo mới (P1)

**File:** `app/actions/edit.py:1101`
**Vấn đề:** Button nói "Lưu thay đổi" ngay cả khi tạo text mới
**Cách sửa:**
- [x] Truyền `is_edit` flag vào dialog
- [x] "Chèn văn bản" khi tạo mới, "Lưu thay đổi" khi edit

---

## FIX 16: InlineEditPanel không hỗ trợ light theme (P1)

**File:** `app/pdf_inline_editor.py:92-103`
**Vấn đề:** Panel hardcode dark theme — user light theme thấy panel đen trên nền trắng
**Cách sửa:**
- [x] Thêm light theme styles
- [x] Detect `is_dark()` và apply phù hợp

---

## FIX 17: Signature pad thiếu pen size control (P1)

**File:** `app/signature_pad.py:34`
**Vấn đề:** Pen size cố định 2px, không có slider — chữ ký quá mỏng
**Cách sửa:**
- [x] Thêm pen size slider (1-10) vào SignaturePadDialog

---

## FIX 18: Bookmark tree expandAll() overwhelming (P2)

**File:** `app/sidebar.py:341`
**Vấn đề:** `expandAll()` mở tất cả — PDF outline sâu sẽ rất dài
**Cách sửa:**
- [x] Chỉ expand level 1, collapse sâu hơn

---

## FIX 19: AI Chat WindowStaysOnTop quá aggressive (P2)

**File:** `app/ai_chat_dialog.py:136`
**Vấn đề:** Dialog nổi trên tất cả apps
**Cách sửa:**
- [x] Bỏ WindowStaysOnTopHint, hoặc thêm toggle

---

## FIX 20: "Xóa obj" dùng developer jargon (P2)

**File:** `app/window.py:681`
**Vấn đề:** Label "Xóa obj" — user không hiểu
**Cách sửa:**
- [x] Đổi thành "Xóa đối tượng"

---

## FIX 21: Minimum box enforcement silent (P2)

**File:** `app/actions/edit.py:1267-1270`
**Vấn đề:** Tự expand vùng quá nhỏ mà không告知 user
**Cách sửa:**
- [x] Hiện toast: "Vùng quá nhỏ, đã tự động mở rộng"

---

## ƯU TIÊN THỰC HIỆN

### Tuần 1 — P0 blockers
- [x] FIX 1: Selection loss
- [x] FIX 2: Unsaved changes confirmation

### Tuần 2 — P1 critical
- [x] FIX 3: Error messages có dấu
- [x] FIX 4: Overlay hint text
- [x] FIX 5: Signature undo + smoothing

### Tuần 3 — P1 important
- [x] FIX 6: Highlight color picker
- [x] FIX 9: Annotation list panel
- [x] FIX 10: AI settings refactor
- [x] FIX 13: Distinct icons for highlight/underline/strikeout
- [x] FIX 14: Keyboard shortcuts for annotation tools
- [x] FIX 15: Text edit dialog button label
- [x] FIX 16: InlineEditPanel light theme
- [x] FIX 17: Signature pen size control

### Tuần 4 — P2 polish
- [x] FIX 7: Thumbnail quality
- [x] FIX 8: Page context menu
- [x] FIX 11: Unsaved annotation warning
- [x] FIX 12: Zoom centered on cursor
- [x] FIX 18: Bookmark expand behavior
- [x] FIX 19: AI Chat stays-on-top
- [x] FIX 20: "Xóa obj" label
- [x] FIX 21: Minimum box enforcement feedback

---

*Cập nhật: 2026-06-04*
