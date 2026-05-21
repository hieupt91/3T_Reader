# Hướng dẫn UI & Branding — 3T Reader

> Dành cho: Đội phát triển Windows  
> Mục tiêu: Giao diện Windows **giống hệt** macOS — cùng logo, màu sắc, layout

---

## 1. Màu sắc thương hiệu

| Tên | Màu | Hex | Dùng ở đâu |
|---|---|---|---|
| Cam chính | 🟠 | `#FF6600` | Nút chính, logo chữ "Reader", highlight |
| Cam đậm | 🟠 | `#FF4400` | Gradient button hover |
| Xanh navy | 🔵 | `#1A3C9E` | Logo chữ "3T", header About dialog |
| Xanh đậm | 🔵 | `#0D1E6A` | Gradient logo mark |
| Nền tối | ⬛ | `#0f0f13` | Background viewer, sidebar tối |
| Card tối | ⬛ | `#1A1A2E` | Feature cards (dark mode) |
| Card sáng | ⬜ | `#F2F4FB` | Feature cards (light mode) |

---

## 2. Logo & Icon

### File logo

```
assets/
├── logo_mark.svg    # Icon vuông 100×100 — dùng làm app icon (taskbar/dock)
└── logo_full.svg    # Logo ngang 420×110 — dùng trong welcome screen & About
```

### Dùng logo làm app icon (taskbar Windows)

```python
# main.py
from app.icon_utils import app_logo_icon
app = QApplication(sys.argv)
app.setWindowIcon(app_logo_icon(256))
```

### Render logo SVG trong widget

```python
# Cần PySide6-Addons hoặc PySide6 đầy đủ có QtSvgWidgets
from PySide6.QtSvgWidgets import QSvgWidget

logo_path = os.path.join(ASSETS_DIR, "logo_full.svg")
logo_widget = QSvgWidget(logo_path)
logo_widget.setFixedSize(QSize(280, 74))
logo_widget.setStyleSheet("background:transparent;")
```

> **Windows note:** Nếu `QSvgWidget` báo lỗi, cài thêm:
> ```cmd
> pip install PySide6-Addons
> ```
> hoặc dùng `app/icon_utils.py` → `app_logo_icon()` qua `QSvgRenderer`.

---

## 3. Màn hình chào mừng (Welcome Screen)

**File:** `app/welcome_widget.py`

### Bố cục

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│           [Logo 3T Reader SVG - 280×74]             │
│      "ĐỌC MỌI LÚC – HIỂU MỌI NƠI" (tagline)       │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ 📄 Xem   │ │ ✏️ Chỉnh │ │ 🔏 Ký số│ │ 🔍 OCR │ │
│  │   PDF    │ │   sửa    │ │  USB     │ │   AI   │ │
│  │  nhiều   │ │  inline  │ │ Token    │ │  (sắp) │ │
│  │   tab    │ │  Foxit   │ │          │ │        │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│                                                     │
│       [🟠 Mở tệp PDF]   [⬜ Mở gần đây]            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Theme-aware (tự đổi theo Dark/Light)

```python
# welcome_widget.py
def changeEvent(self, event):
    from packages.qt_compat.QtCore import QEvent
    if event.type() == QEvent.Type.PaletteChange:
        self._apply_theme_styles()
    super().changeEvent(event)

def _apply_theme_styles(self):
    from styles.theme import is_dark
    card_bg = "#1A1A2E" if is_dark() else "#F2F4FB"
    card_border = "#2A2A4A" if is_dark() else "#D8DCF0"
    title_color = "#E8EEFF" if is_dark() else "#1A2060"
    desc_color = "#8080B0" if is_dark() else "#4A4A7A"
    # áp dụng stylesheet cho các card
```

### Nút "Mở tệp PDF" — style mẫu

```python
btn_open.setStyleSheet("""
    QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #FF7700, stop:1 #FF4400);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 32px;
        font-size: 14px;
        font-weight: 700;
    }
    QPushButton:hover { background: #FF9900; }
    QPushButton:pressed { background: #DD4400; }
""")
```

---

## 4. Toolbar — Logo + Brand text

**File:** `app/window.py` → `_build_toolbar()`

```
┌──────────────────────────────────────────────────────────────┐
│ [🔷32px] 3TReader │ [Mở][Gần đây][Lưu][In] │ [◀][1][▶]...  │
└──────────────────────────────────────────────────────────────┘
```

Code mẫu (đã có trong window.py):

```python
from PySide6.QtSvgWidgets import QSvgWidget

_logo_w = QSvgWidget(logo_mark_path)
_logo_w.setFixedSize(QSize(32, 32))
_logo_w.setStyleSheet("background:transparent;")

_brand_text = QLabel(
    "<b style='color:#1A3C9E;font-size:13px;letter-spacing:1px;'>3T</b>"
    "<span style='color:#FF6600;font-size:13px;font-weight:600;'>Reader</span>"
)
```

---

## 5. About Dialog

**File:** `app/about_dialog.py`

### Bố cục

```
┌─────────────────────────────────────────────┐
│  ╔═══════════════════════════════════════╗  │
│  ║  [Logo Full SVG — 280×74]             ║  │  ← Header gradient navy
│  ║  3T Reader — Trợ lý tài liệu thông  ║  │
│  ╚═══════════════════════════════════════╝  │
│                                             │
│  Phiên bản:    1.0.2                        │
│  Nền tảng:     macOS / Windows              │
│  Tính năng:    PDF, Ký số, AI/OCR (sắp)    │
│  Công nghệ:    Python, PySide6, PDF.js      │
│                                             │
│  © 2026 3T Company. All rights reserved.   │
│                                             │
│                    [🟠 Đóng]               │
└─────────────────────────────────────────────┘
```

### Header gradient

```python
header.setStyleSheet("""
    QFrame {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
            stop:0 #0D1E6A, stop:1 #1A3C9E);
        border-radius: 8px 8px 0 0;
        padding: 20px;
    }
""")
```

---

## 6. Icon toolbar — màu theo chức năng

Tất cả icon là SVG trong `assets/icons/`. Màu được set theo nhóm:

| Nhóm | Màu | Ví dụ icon |
|---|---|---|
| File/Nav | `#5b9cf6` (xanh dương) | folder_open, history, chevron |
| Lưu/Edit | `#4fc080` (xanh lá) | save, save_as, merge_pdf |
| Ký số | `#b060e0` (tím) | sign_draw, fit_page |
| Phá hủy | `#e05050` (đỏ) | delete_page, redact, trash |
| Giao diện | `#f0c050` (vàng) | sun, brightness_up, highlight |
| Điều hướng | `#a0a0c0` (xám) | chevron_left, chevron_right |

Hàm render SVG với màu tuỳ chỉnh:

```python
# app/icon_utils.py
from app.icon_utils import svg_icon

icon = svg_icon("folder_open.svg", size=20, color="#5b9cf6")
action.setIcon(icon)
```

Hàm `svg_icon()` đọc file SVG, thay `#212121` (màu gốc) bằng màu chỉ định, render ra `QIcon`.

---

## 7. Theme Dark/Light

**File:** `styles/theme.py`

```python
from styles.theme import toggle_theme, is_dark

# Kiểm tra theme hiện tại
if is_dark():
    # áp dụng màu tối
else:
    # áp dụng màu sáng

# Chuyển đổi theme
toggle_theme()
```

Dùng `pyqtdarktheme` làm base, sau đó custom thêm qua stylesheet.

---

## 8. Checklist để UI Windows = Mac

- [ ] Clone branch `phase1-mac`
- [ ] Cài `pip install PySide6==6.11.0 pyqtdarktheme==0.1.7`
- [ ] Chạy `python main.py` — welcome screen hiện logo đúng chưa?
- [ ] Mở file PDF — toolbar có logo 3T góc trái không?
- [ ] Bấm "Giới thiệu 3T Reader" trong menu Help — About dialog hiện đúng không?
- [ ] Chuyển Dark/Light — welcome screen cards đổi màu theo không?
- [ ] Logo app hiện trên taskbar Windows không?

---

## 9. File quan trọng cần xem

| File | Mô tả |
|---|---|
| `app/welcome_widget.py` | Toàn bộ màn hình chào mừng |
| `app/about_dialog.py` | About dialog |
| `app/icon_utils.py` | `svg_icon()`, `app_logo_icon()` |
| `app/window.py` | Toolbar brand, menu Help, welcome tab |
| `assets/logo_mark.svg` | Logo icon (app icon) |
| `assets/logo_full.svg` | Logo đầy đủ |
| `assets/icons/*.svg` | 34 icon toolbar |
| `styles/theme.py` | Dark/Light toggle |
| `packages/qt_compat/QtSvgWidgets.py` | Compat layer cho QSvgWidget |

---

*Cập nhật: 2026-05-21 | Branch: phase1-mac*
