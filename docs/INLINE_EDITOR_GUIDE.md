# Hướng dẫn kỹ thuật — Inline PDF Editor (Chèn Text / Chèn Ảnh)

> Dành cho: Đội phát triển Windows  
> Branch: `phase1-mac`  
> File chính: `app/pdf_inline_editor.py`, `app/actions/edit.py`

---

## 1. Tổng quan kiến trúc

Tính năng chèn text/ảnh hoạt động theo kiểu **Foxit-style** — người dùng tương tác trực tiếp trên canvas PDF, không có dialog popup trước.

```
[Người dùng bấm nút toolbar]
        │
        ▼
[Python: run_inline_text() / run_inline_image()]
        │
        ├─ Tạo QWebChannel + bridge Python↔JS
        ├─ Inject JavaScript vào PDF.js WebView
        ├─ Hiện panel nổi (font size, màu, Confirm/Cancel)
        └─ Chạy QEventLoop (block Python, chờ JS callback)
                │
                ▼
        [JS: người dùng click vào trang PDF]
                │
                ├─ Tạo overlay div + textarea (text mode)
                │  hoặc overlay div + img preview (image mode)
                ├─ Drag để di chuyển, kéo góc để resize
                └─ Ctrl+Enter / Enter để confirm
                        │
                        ▼
                [JS gọi bridge.confirmText() / bridge.confirmImage()]
                        │
                        ▼
                [Python nhận tọa độ PDF + text/path]
                [QEventLoop.quit()]
                        │
                        ▼
        [edit.py: thêm op vào edit_state]
        [rebuild_pdf_with_ops() → reload viewer]
```

---

## 2. Luồng chèn TEXT chi tiết

### 2.1 Entry point

```python
# app/actions/edit.py
@require_document(show_message=True)
def insert_text_to_pdf(window):
    from app.pdf_inline_editor import run_inline_text
    result = run_inline_text(window)
    # result = {page_number, box, text, font_size, color_tuple} hoặc None
```

### 2.2 `run_inline_text(window)` — `app/pdf_inline_editor.py`

```python
def run_inline_text(window) -> dict | None:
    web_view = _get_web_view(window)      # lấy QWebEngineView hiện tại
    bridge = InlineTextBridge(window)     # object Python nhận callback từ JS
    _setup_webchannel(web_view, window, "inlineTextBridge", bridge)
    # inject INLINE_TEXT_JS vào WebView
    # chạy QEventLoop (chờ JS confirm hoặc cancel)
    # trả về result dict hoặc None
```

### 2.3 Tọa độ PDF (quan trọng)

JS dùng PDF.js API để convert tọa độ màn hình → tọa độ PDF:

```javascript
var p1 = pageView.viewport.convertToPdfPoint(x_screen, y_screen);
// p1[0] = x (điểm PDF, gốc trái-dưới)
// p1[1] = y (điểm PDF, gốc trái-dưới)
```

Python nhận `(left, bottom, right, top)` theo hệ tọa độ PDF (gốc bottom-left).

PyMuPDF dùng hệ tọa độ ngược (gốc top-left) nên cần convert:

```python
# app/pdf_engine/pymupdf_engine.py — rebuild_pdf_with_ops()
page_h = page.rect.height
rect = fitz.Rect(pdf_left, page_h - pdf_top, pdf_right, page_h - pdf_bottom)
```

---

## 3. Luồng chèn ẢNH chi tiết

### 3.1 Entry point

```python
# app/actions/edit.py
@require_document(show_message=True)
def insert_image_to_pdf(window):
    # 1. Mở QFileDialog chọn ảnh
    image_path, _ = QFileDialog.getOpenFileName(...)
    # 2. Chạy inline editor
    from app.pdf_inline_editor import run_inline_image
    result = run_inline_image(window, image_path)
    # result = {page_number, box} hoặc None
```

### 3.2 Preview ảnh trong JS

Ảnh được encode thành base64 data URL và truyền vào JS:

```python
with open(image_path, "rb") as f:
    raw = f.read()
data_url = f"data:image/png;base64,{base64.b64encode(raw).decode()}"
web_view.page().runJavaScript(f"window.__3TInlineImageUrl = {repr(data_url)};")
```

JS dùng `window.__3TInlineImageUrl` để hiện `<img>` preview trực tiếp trên trang PDF.

---

## 4. Edit State — quản lý lịch sử thao tác

Mỗi tab PDF có 1 `_pdf_edit_state` riêng trên `window`:

```python
state = {
    "original_path": "/path/to/file.pdf",   # file gốc
    "base_snapshot": "/tmp/base_xxx.pdf",   # bản snapshot không bao giờ thay đổi
    "working_file":  "/tmp/work_xxx.pdf",   # file viewer đang hiển thị
    "ops": [                                # danh sách thao tác đã làm
        {
            "id": 1,
            "type": "text",                 # "text" | "image" | "rect"
            "page_number": 1,
            "box": (left, bottom, right, top),
            "text": "Nội dung...",
            "font_size": 14,
            "font_color": (0.0, 0.0, 0.0),
        },
        {
            "id": 2,
            "type": "image",
            "page_number": 2,
            "box": (50, 100, 300, 400),
            "image_path": "/path/to/img.png",
        },
    ],
    "next_id": 3,
}
```

`rebuild_pdf_with_ops(base_snapshot, working_file, ops)` tái tạo working_file từ base + toàn bộ ops mỗi lần có thay đổi. Cơ chế này cho phép Undo chỉ bằng cách `ops.pop()` rồi rebuild lại.

---

## 5. Font tiếng Việt khi render vào PDF

**Vấn đề:** Font `"helv"` (Helvetica) mặc định của PyMuPDF không hỗ trợ Unicode/tiếng Việt.

**Giải pháp:** Dùng font hệ thống qua `get_vietnamese_font_path()`:

```python
# packages/pdf_engine/pymupdf_engine.py
from packages.platform.fonts import get_vietnamese_font_path
font_path = get_vietnamese_font_path()
page.insert_textbox(
    rect, text,
    fontsize=font_size,
    fontfile=font_path,   # Arial.ttf, Tahoma.ttf, v.v.
    fontname="vifont",
    color=font_color,
)
```

**Trên Windows:** hàm `get_vietnamese_font_path()` tìm `tahoma.ttf` → `arial.ttf` → `segoeui.ttf` trong `C:\Windows\Fonts\`.

---

## 6. QWebChannel — Reconnect mỗi lần

**Vấn đề stale bridge:** Mỗi lần `run_inline_text()` được gọi, Python tạo 1 `QWebChannel` MỚI. Nếu JS còn giữ reference cũ sẽ không nhận được callback.

**Giải pháp:** JS luôn tạo `new QWebChannel(...)` từ đầu mỗi lần inject:

```javascript
// Trong INLINE_TEXT_JS — cuối file
function attach() {
    new QWebChannel(qt.webChannelTransport, function (ch) {
        window.__3TTextBridge = ch.objects.inlineTextBridge || null;
        startListen();
    });
}
attach();
```

**Không dùng singleton pattern** — không cache bridge vào biến global lâu dài.

---

## 7. Overlay không bị flash

**Vấn đề cũ:** Khi người dùng confirm, overlay JS bị xóa → PDF reload → có khoảng trắng 0.5-1.5 giây.

**Giải pháp hiện tại:** **Không xóa overlay** khi confirm. PDF.js tự xóa toàn bộ DOM khi reload, overlay biến mất tự nhiên cùng lúc PDF mới hiện ra.

```javascript
window.__3TTextCommit = function () {
    // ...
    br.confirmText(pageNumber, box.l, box.b, box.r, box.t, text);
    // KHÔNG gọi _clear() hay removeChild() ở đây
};
```

---

## 8. Cấu trúc file liên quan

```
app/
├── pdf_inline_editor.py      # InlineTextBridge, InlineImageBridge,
│                             # InlineEditPanel, INLINE_TEXT_JS,
│                             # INLINE_IMAGE_JS, run_inline_text(),
│                             # run_inline_image()
├── actions/
│   └── edit.py               # insert_text_to_pdf(), insert_image_to_pdf(),
│                             # _ensure_edit_state(), _render_edit_state(),
│                             # rebuild từ ops, undo_last_edit()
packages/
├── pdf_engine/
│   └── pymupdf_engine.py     # rebuild_pdf_with_ops() — render text/image/rect
│                             # vào PDF bằng PyMuPDF
└── platform/
    └── fonts.py              # get_vietnamese_font_path() — tìm font hệ thống
```

---

## 9. Lưu ý khi phát triển trên Windows

1. **Font path:** `get_vietnamese_font_path()` tự detect `C:\Windows\Fonts\` — không cần config thêm
2. **WebEngine sandbox:** Nếu WebView trắng, thêm vào đầu `main.py`:
   ```python
   os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
   ```
3. **QWebChannel transport:** Nếu bridge không kết nối được, kiểm tra `qt.webChannelTransport` đã sẵn sàng bằng cách retry:
   ```javascript
   if (!(window.qt && qt.webChannelTransport)) {
       setTimeout(attach, 100);
       return;
   }
   ```
4. **PyMuPDF version:** Dùng đúng `PyMuPDF==1.27.2.2`. Các version mới hơn có thể thay đổi API `insert_textbox`.

---

*Cập nhật: 2026-05-21 | Branch: phase1-mac*
