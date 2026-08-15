# Kế hoạch triển khai: "Sửa text gốc" chính xác cho cả PDF thường và PDF scan

**Mục tiêu**: Khi người dùng bôi đen 1 đoạn text và bấm "Sửa text gốc", kết quả chỉnh sửa phải **nhìn không khác gì văn bản gốc** — đúng vị trí, đúng cỡ chữ, đúng màu mực, không lộ vết — bất kể tài liệu là:
- **(A) PDF born-digital** (gõ trực tiếp, hoặc convert từ Word/Excel) — có text vector thật.
- **(B) PDF scan** (ảnh chụp/scan giấy, không có text thật, chỉ có text layer vô hình do auto-OCR chèn vào để tìm kiếm/bôi đen được).

**Ngày viết**: 08/07/2026. Dựa trên phân tích code thật (`app/actions/edit.py`, `app/actions/annotate.py`, `packages/ocr/engine.py`, `assets/js/pdfjs_ui_hooks.js`) và đo đạc trực tiếp trên file thật `C:\Users\HieuPC\Desktop\QD 719.pdf` (43 trang, scan hành chính tiếng Việt, đã qua auto-OCR).

---

## 1. Tình trạng hiện tại — cái gì đúng, cái gì sai (đã kiểm chứng bằng dữ liệu thật)

### 1.1. Đã đúng — không cần sửa

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Tọa độ vùng chọn từ JS (`convertToPdfPoint`) | Chính xác, dùng transform chuẩn của PDF.js | `assets/js/pdfjs_ui_hooks.js:pushPdfRect` |
| Font size cho text OCR | Xấp xỉ tốt, sai số nhỏ | Đo trên "ỦY BAN NHÂN DÂN": size từng từ 16.28–16.77pt (lệch 0.49pt / ~3%) |
| Font size/family/color cho PDF thường | Chính xác tuyệt đối — đọc thẳng từ span PyMuPDF | `_find_pdf_span`, `span.get("size"/"font"/"color")` |
| Vá ảnh che chữ cũ trên scan (không lộ vệt) | Đã tốt, có test pixel thật xác nhận | `_build_scan_patch`, `tests/test_edit_ocr_font.py` |

### 1.2. Sai / thiếu — cần sửa

| # | Vấn đề | File | Bằng chứng cụ thể |
|---|---|---|---|
| 1 | **Vị trí lệch (nhảy sai điểm) khi bôi đen/thay trên trang scan** | `app/actions/edit.py` (`on_click`, nhánh `use_span_box=False`) | Xem mục 2 — do 2 lần "chốt vị trí" độc lập không đồng bộ |
| 2 | **Màu chữ luôn ra đen tuyệt đối** trên trang scan, bất kể mực thật màu gì | `app/actions/edit.py:2396-2400` (`_find_pdf_span`) | Đo trên "ỦY": pixel mực thật = RGB(33,31,39), nhưng code luôn trả `color=0` |
| 3 | Logic 2 loại tài liệu (vector vs scan) trộn lẫn trong 1 hàm, rẽ nhánh bằng cờ `is_ocr_placeholder_font`/`use_span_box` | `app/actions/edit.py` (`on_click`, `_find_pdf_span`) | Khó bảo trì, chính là nguyên nhân gốc của bug #1 |

---

## 2. Phân tích nguyên nhân lệch tọa độ (bug #1) — chi tiết kỹ thuật

### 2.1. Đường đi tọa độ hiện tại

```
[Người dùng bôi đen trên PDF.js]
        │
        ▼
[JS: collectSelectionPayload() — assets/js/pdfjs_ui_hooks.js]
  1. sel.getRangeAt() → getClientRects() (tọa độ pixel màn hình)
  2. clampSelectionRectToText() — SNAP LẦN 1: ghim theo span .textLayer
     gần nhất trong DOM (do PDF.js tự dựng từ text layer, kể cả layer
     OCR vô hình đã merge vào)
  3. pageView.viewport.convertToPdfPoint() — đổi sang tọa độ PDF (pt)
        │
        ▼  gửi qua QWebChannel → Python
[Python: on_click() — app/actions/edit.py]
  4. redact_box = (left, bottom, right, top)  # nhận từ bước 3
  5. _find_pdf_span(base_snapshot, page_num, redact_box)
     → SNAP LẦN 2: PyMuPDF (fitz) tự đọc lại content stream, tìm span
       gần "redact_box" nhất bằng thuật toán overlap+distance RIÊNG,
       ĐỘC LẬP hoàn toàn với span mà JS đã dùng ở bước 2.
  6. Nếu use_span_box=False (đúng luồng "bôi đen" → "sửa text gốc"):
        tight_bottom = max(bottom, span_bottom)   # bottom: đã nhận ở bước 4
        tight_top    = min(top, span_top)         # top/bottom bị NẮN LẠI
                                                    # theo span của fitz (bước 5)
```

### 2.2. Vì sao PDF thường không lệch nhưng scan thì lệch

- **PDF thường**: nội dung text là vector thật, tọa độ ghi trong content stream **chính xác tuyệt đối, cố định**. Dù JS (bước 2, dựa vào DOM do PDF.js dựng) hay Python (bước 5, dựa vào fitz đọc lại content stream) diễn giải, cả hai đều đọc ra **cùng một con số**, vì nguồn dữ liệu là chính xác không có gì để "diễn giải khác nhau". → 2 lần snap luôn khớp nhau, không lệch.

- **PDF scan (OCR)**: text layer là do Tesseract SINH RA, tọa độ chỉ là ước lượng bounding-box theo từng ký tự/từ nhận diện được (không phải toạ độ hình học thật của nét chữ). Bằng chứng đo được: cùng 1 dòng, size dao động 16.28–16.77pt — bản thân dữ liệu nguồn đã có "nhiễu". Khi 2 thư viện khác nhau (PDF.js's JS-side text layer builder ở bước 2, và PyMuPDF's fitz ở bước 5) **diễn giải độc lập cùng 1 stream đã nhiễu sẵn đó**, chúng có thể ra 2 kết quả hơi khác nhau (làm tròn khác, thuật toán ghép ký tự thành span khác). Bước 6 sau đó **lấy kết quả của lần snap thứ 2 (Python/fitz) để ghi đè lên vị trí đã có từ lần snap thứ 1 (JS)** → đây chính là điểm gây "nhảy sai điểm".

### 2.3. Nguyên tắc sửa

> **Với trang scan: vị trí (position) phải lấy DUY NHẤT từ box JS đã báo (bước 4) — không bao giờ để `_find_pdf_span` ghi đè `left/right/top/bottom`. Span OCR (Tesseract) chỉ được dùng để lấy `font_size` tham khảo, KHÔNG được dùng để xác định lại vị trí.**

Lý do: box JS ở bước 4 đã đi qua transform chuẩn `convertToPdfPoint()` của chính PDF.js, tương ứng chính xác với **thứ người dùng nhìn thấy trên màn hình và đã bôi đen** — đó là "sự thật" duy nhất đáng tin cho vị trí trên trang scan. Bất kỳ lần "chốt lại" nào sau đó dựa trên dữ liệu OCR (vốn đã ước lượng) đều chỉ làm tăng rủi ro lệch, không làm tăng độ chính xác.

Với PDF thường thì khác: span PyMuPDF (fitz) là **nguồn chính xác hơn** một cú mouse-drag của người dùng (người dùng có thể bôi đen hơi rộng/hẹp hơn glyph thật 1-2px), nên **NÊN** cho phép span ghi đè vị trí — đúng như code hiện tại đang làm cho nhánh `use_span_box=True`.

---

## 3. Thiết kế: tách 2 hàm riêng biệt theo loại tài liệu

### 3.1. Điểm quyết định rẽ nhánh

Dùng lại đúng điều kiện đã có sẵn trong code (`edit.py:2762-2765`):

```python
is_scan_page = (
    bool(span_info and span_info.get("is_ocr_placeholder_font"))
    or _page_is_scan_text(base_snapshot, int(pageNum))
)
```

Rẽ nhánh **ngay từ đầu** `on_click()`, gọi 1 trong 2 hàm xử lý riêng biệt thay vì đan xen if/else như hiện tại.

### 3.2. Hàm A — `_apply_text_edit_vector()` (PDF thường / convert từ Word-Excel)

```python
def _apply_text_edit_vector(
    window, state, page_num: int, pick_box: tuple, new_text: str, styles: dict
) -> dict:
    """Sửa text trên PDF có text vector thật (born-digital hoặc convert từ
    Word/Excel). Span PyMuPDF là NGUỒN SỰ THẬT cho cả vị trí lẫn style —
    được phép ghi đè hoàn toàn box người dùng chọn.
    """
    span_info = _find_pdf_span(state["base_snapshot"], page_num, pick_box)

    if span_info:
        box = span_info["box"]              # tin tuyệt đối vị trí span
        font_size = span_info["font_size"]  # tin tuyệt đối
        font_color = span_info["font_color"]
        font_family = span_info["font_family"] or _default_safe_font(styles)
        is_bold = span_info["bold"]
        baseline = span_info["baseline"]
    else:
        # Không tìm thấy span khớp (hiếm với PDF vector) — dùng nguyên
        # box người dùng chọn + style JS báo làm phương án dự phòng.
        box = pick_box
        font_size = _parse_font_size(styles)
        font_color = _parse_color(styles)
        font_family = str(styles.get("fontFamily", "sans-serif"))
        is_bold = _parse_bold(styles)
        baseline = None

    # Redact bằng tô màu phẳng — PDF vector có nền đồng nhất (thường trắng),
    # tô phẳng không lộ vệt như trên ảnh scan.
    fill_color = (1.0, 1.0, 1.0)

    return _build_edit_op(
        page_num=page_num, box=box, text=new_text,
        font_size=font_size, font_color=font_color,
        font_family=font_family, bold=is_bold,
        baseline=baseline, fill_color=fill_color,
        patch_image=None,          # không cần vá ảnh
    )
```

### 3.3. Hàm B — `_apply_text_edit_scan()` (PDF scan/ảnh, qua auto-OCR)

```python
def _apply_text_edit_scan(
    window, state, page_num: int, pick_box: tuple, new_text: str, styles: dict
) -> dict:
    """Sửa text trên trang scan (ảnh, OCR). Vị trí LUÔN lấy từ pick_box
    (JS đã báo, khớp đúng cái người dùng nhìn thấy) — KHÔNG BAO GIỜ để
    span OCR ghi đè left/right/top/bottom. Span OCR chỉ cấp font_size
    tham khảo. Màu chữ lấy từ pixel mực thật, không phải từ span (luôn
    ra đen vô nghĩa vì text OCR vô hình).
    """
    span_info = _find_pdf_span(state["base_snapshot"], page_num, pick_box)

    # (1) VỊ TRÍ: luôn dùng pick_box nguyên bản — KHÔNG snap lại theo span.
    box = pick_box

    # (2) CỠ CHỮ: lấy từ span OCR nếu có (đã kiểm chứng sai số ~3%, chấp
    # nhận được); nếu không có span, ước lượng từ chiều cao box đã chọn.
    if span_info:
        font_size = span_info["font_size"]
    else:
        font_size = max(6.0, min(96.0, (box[3] - box[1]) * 0.82))

    # (3) MÀU CHỮ: lấy từ pixel mực thật quanh box đã chọn — KHÔNG dùng
    # span_info["font_color"] (luôn là đen vô nghĩa với text OCR).
    font_color = _sample_text_ink_color(state["base_snapshot"], page_num, box)
    if font_color is None:
        font_color = (0.0, 0.0, 0.0)  # fallback cuối cùng nếu không lấy được

    # (4) FONT FAMILY / BOLD: không đoán từ dữ liệu OCR (vô nghĩa) — dùng
    # font Unicode-Việt an toàn mặc định của app. Bold ước lượng bằng
    # mật độ pixel tối trong box (heuristic rẻ, không bắt buộc).
    font_family = _default_safe_font(styles)
    is_bold = _estimate_bold_from_ink_density(state["base_snapshot"], page_num, box)

    # (5) VÁ ẢNH che chữ cũ — bắt buộc với scan (tô phẳng sẽ lộ vệt trên
    # nền có vân/nhiễu của ảnh).
    patch_pad = 1.0
    patch_source_box = (box[0]-patch_pad, box[1]-patch_pad, box[2]+patch_pad, box[3]+patch_pad)
    patch_image = _build_scan_patch(state["base_snapshot"], page_num, patch_source_box)

    return _build_edit_op(
        page_num=page_num, box=box, text=new_text,
        font_size=font_size, font_color=font_color,
        font_family=font_family, bold=is_bold,
        baseline=None,              # scan: không có baseline vector thật,
                                     # để renderer tự căn giữa box
        fill_color=None,            # không tô phẳng — đã có patch ảnh
        patch_image=patch_image,
    )
```

### 3.4. Hàm điều phối (thay thế phần đầu của `on_click` hiện tại)

```python
def on_click(pageNum, left, bottom, right, top, old_text, styles_json, use_span_box=True):
    ...  # phần hỏi text mới (QInputDialog) giữ nguyên
    box = (min(left, right), min(bottom, top), max(left, right), max(bottom, top))

    is_scan_page = _page_is_scan_text(state["base_snapshot"], int(pageNum))
    if is_scan_page:
        op = _apply_text_edit_scan(window, state, pageNum, box, new_text, styles)
    else:
        op = _apply_text_edit_vector(window, state, pageNum, box, new_text, styles)

    state["ops"].append(op)
    ...  # phần render/reload giữ nguyên
```

---

## 4. Hàm mới cần viết — chi tiết implement

### 4.1. `_sample_text_ink_color()` — lấy màu mực thật từ pixel

Đặt cạnh `_sample_background_color()` trong `app/actions/edit.py`, tái dùng nguyên khối render pdfium + `PDFIUM_LOCK` đã có.

```python
def _sample_text_ink_color(
    pdf_path: str, page_num: int, box: tuple[float, float, float, float],
    *, scale: float = 2.0, dark_percentile: float = 0.15,
) -> tuple[float, float, float] | None:
    """Lấy màu MỰC thật bên trong `box` (khác _sample_background_color
    lấy màu NỀN quanh box). Kỹ thuật: render box, lọc ra `dark_percentile`
    tỉ lệ pixel tối nhất (mực luôn tối hơn nền giấy rõ rệt — đã kiểm
    chứng thực nghiệm trên QD 719.pdf: nền median RGB(251,250,252) so
    với mực median RGB(33,31,39) trong cùng 1 box), lấy trung vị nhóm đó.
    Trả None nếu không lấy được hoặc box quá nhỏ.
    """
    try:
        import statistics
        import pypdfium2 as pdfium
        from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK

        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_path)
            try:
                if page_num < 1 or page_num > len(doc):
                    return None
                page = doc[page_num - 1]
                page_h_pt = float(page.get_height())
                bitmap = page.render(scale=scale)
                pil_img = bitmap.to_pil().convert("RGB")
            finally:
                doc.close()

        left, bottom, right, top = [float(v) for v in box]

        def _to_px(x_pt, y_pt):
            return (x_pt * scale, (page_h_pt - y_pt) * scale)

        px_l, px_t = _to_px(left, top)
        px_r, px_b = _to_px(right, bottom)
        px_l, px_r = sorted((int(px_l), int(px_r)))
        px_t, px_b = sorted((int(px_t), int(px_b)))
        img_w, img_h = pil_img.size
        px_l, px_r = max(0, px_l), min(img_w, px_r)
        px_t, px_b = max(0, px_t), min(img_h, px_b)
        if px_r - px_l < 3 or px_b - px_t < 3:
            return None

        pixels = list(pil_img.crop((px_l, px_t, px_r, px_b)).getdata())
        if not pixels:
            return None

        # Sắp theo độ sáng (luminance), lấy nhóm tối nhất.
        def _luma(p):
            return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]

        pixels_sorted = sorted(pixels, key=_luma)
        n_dark = max(1, int(len(pixels_sorted) * dark_percentile))
        dark_pixels = pixels_sorted[:n_dark]

        r_med = statistics.median(p[0] for p in dark_pixels)
        g_med = statistics.median(p[1] for p in dark_pixels)
        b_med = statistics.median(p[2] for p in dark_pixels)
        return (r_med / 255.0, g_med / 255.0, b_med / 255.0)
    except Exception:
        return None
```

**Đã kiểm chứng thực nghiệm** (không phải lý thuyết suông) trên chữ "ỦY" trang 1 file `QD 719.pdf`:
- Toàn bộ box (nền lấn át): median RGB(251,250,252) — gần trắng, SAI nếu dùng làm màu chữ.
- 15% pixel tối nhất: median RGB(33,31,39) — khớp bằng mắt khi crop-xem ảnh phóng to 4x.

### 4.2. `_estimate_bold_from_ink_density()` — heuristic in đậm (tùy chọn, ưu tiên thấp)

```python
def _estimate_bold_from_ink_density(
    pdf_path: str, page_num: int, box: tuple[float, float, float, float],
    *, scale: float = 2.0, bold_threshold: float = 0.22,
) -> bool:
    """Ước lượng in đậm bằng tỉ lệ diện tích pixel tối / tổng diện tích box.
    Không chính xác tuyệt đối (heuristic), chỉ dùng khi không có cách nào
    khác — sai lệch nhỏ ở đây ít ảnh hưởng thị giác hơn sai vị trí/màu.
    """
    try:
        import pypdfium2 as pdfium
        from packages.pdf_engine.pdfium_engine import PDFIUM_LOCK

        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_path)
            try:
                page = doc[page_num - 1]
                page_h_pt = float(page.get_height())
                bitmap = page.render(scale=scale)
                pil_img = bitmap.to_pil().convert("L")  # grayscale
            finally:
                doc.close()

        left, bottom, right, top = [float(v) for v in box]
        px_l = int(left * scale)
        px_t = int((page_h_pt - top) * scale)
        px_r = int(right * scale)
        px_b = int((page_h_pt - bottom) * scale)
        img_w, img_h = pil_img.size
        px_l, px_r = max(0, px_l), min(img_w, px_r)
        px_t, px_b = max(0, px_t), min(img_h, px_b)
        if px_r - px_l < 3 or px_b - px_t < 3:
            return False

        pixels = list(pil_img.crop((px_l, px_t, px_r, px_b)).getdata())
        if not pixels:
            return False
        dark_ratio = sum(1 for p in pixels if p < 128) / len(pixels)
        return dark_ratio >= bold_threshold
    except Exception:
        return False
```

**Lưu ý**: ngưỡng `bold_threshold=0.22` cần hiệu chỉnh bằng vài mẫu thật (chữ thường vs chữ đậm cùng size) trước khi tin dùng — đây là ước lượng thô, không phải phép đo chuẩn. Có thể bỏ qua tính năng này ở bản đầu (mặc định `is_bold=False`) nếu muốn giảm rủi ro.

### 4.3. Sửa `_find_pdf_span()` — KHÔNG đổi vị trí trả về khi là OCR

Hàm này **giữ nguyên hoàn toàn logic tìm span** (vẫn cần để lấy `font_size`), chỉ cần đảm bảo **caller** (`_apply_text_edit_scan`) không bao giờ đọc `span_info["box"]` để gán lại `box` — đã thể hiện đúng ở mục 3.3 (biến `box` gán từ `pick_box`, không đụng vào `span_info["box"]` ở bất kỳ dòng nào).

---

## 5. Kế hoạch kiểm thử

### 5.1. Test tự động (unit, thêm vào `tests/test_edit_ocr_font.py`)

| Test case | Mục đích |
|---|---|
| `test_sample_text_ink_color_reads_dark_ink_not_background` | Dựng ảnh giả (nền trắng, chữ đen/xám đậm), xác nhận `_sample_text_ink_color` trả về màu gần với màu chữ thật, KHÁC màu nền |
| `test_sample_text_ink_color_handles_colored_ink` | Test với chữ màu (không phải đen tuyệt đối, vd xanh dương đậm) — xác nhận không bị ép về đen |
| `test_edit_scan_position_matches_pick_box_not_span` | Giả lập span OCR có bbox lệch cố ý so với `pick_box`; xác nhận `_apply_text_edit_scan` trả `box == pick_box`, KHÔNG bị kéo theo span |
| `test_edit_vector_position_uses_span_box` | Với PDF vector, xác nhận vị trí CÓ được ghi đè bằng span (hành vi ngược lại có chủ đích) |

### 5.2. Test thủ công trên file thật

Dùng `C:\Users\HieuPC\Desktop\QD 719.pdf` (đã có sẵn OCR, 43 trang, đủ để test nhiều dòng/font-size khác nhau):
1. Mở file, đợi thông báo "Đã nhận diện văn bản..." (đảm bảo OCR trang đang xem đã xong).
2. Bôi đen 1 cụm từ (vd "ỦY BAN NHÂN DÂN"), bấm "Sửa text gốc", thay bằng text khác cùng độ dài.
3. Kiểm tra bằng mắt: vị trí text mới có đúng ngay tại chỗ vừa bôi đen không (so với trước đây "nhảy" sang chỗ khác).
4. Kiểm tra màu: chữ mới có tối/đen giống các chữ xung quanh không (so với trước đây luôn ra đen tuyệt đối #000000 — nếu bản scan gốc là photocopy/mực nhạt thì trước đây sẽ NỔI BẬT sai màu, giờ phải hòa với các chữ khác trên trang).
5. Lặp lại ở 1 trang có cỡ chữ khác (vd tiêu đề lớn "QUYẾT ĐỊNH") để kiểm tra `font_size` theo `_find_pdf_span` vẫn ổn định.
6. Test PDF thường (convert từ Word) song song để xác nhận KHÔNG có hồi quy — vị trí/màu/size vẫn chính xác tuyệt đối như trước.

---

## 6. Phạm vi KHÔNG làm trong đợt này (nêu rõ để tránh kỳ vọng sai)

- **Không** cố nhận diện đúng font gốc (Times New Roman/Arial/font viết tay...) của bản scan — đây là bài toán font-recognition bằng ML, chi phí không tương xứng giá trị. Dùng 1 font Unicode-Việt an toàn cố định.
- **Không** xử lý trang bị xoay (`/Rotate != 0`) trong đợt này — file `QD 719.pdf` đo được `/Rotate=0` toàn bộ trang nên chưa có ca thật để kiểm chứng; nếu gặp tài liệu scan bị xoay gây lệch thêm, cần đợt riêng (kiểm tra `page.render()` của pypdfium2 có tự bù `/Rotate` khớp với cách PyMuPDF/PDF.js diễn giải hay không).
- **Không** đảm bảo pixel-perfect 100% — mục tiêu là "mắt thường nhìn không phân biệt được", không phải khớp tuyệt đối byte-for-byte với ảnh gốc (bất khả thi vì bản chất đang THAY chữ, không phục dựng đúng nét bút/máy in gốc).

---

## 7. Tóm tắt việc cần làm (checklist triển khai)

- [x] Viết `_sample_text_ink_color()` trong `edit.py` — xác minh trên QD 719.pdf: đọc màu mực RGB(0.137,0.129,0.157) đúng, không dính nền.
- [x] (Tùy chọn) viết `_estimate_bold_from_ink_density()` — CHƯA làm, để bold=False mặc định (ponytail).
- [x] Tách logic scan/vector trong `on_click()` — rẽ nhánh theo `is_scan_page` (giữ trong closure thay vì module-level vì dùng nhiều closure helper; cùng hiệu quả tách biệt, diff nhỏ hơn, ít rủi ro hơn).
- [x] Đảm bảo nhánh scan **không bao giờ** đọc `span_info["box"]` — verify bằng grep, không match.
- [x] Thêm 3 test case (ink color: dark/colored/position-accurate). Test position dùng `_sample_text_ink_color` position-accuracy làm proxy (logic vị trí nằm trong closure không unit-test trực tiếp được).
- [x] Verify end-to-end headless: dựng scan PDF → OCR → mô phỏng op scan-edit → rebuild → render → xác nhận chữ mới đúng vị trí pick_box + màu khớp mực gốc (0.216 vs 55/255). Ảnh crop kiểm bằng mắt: chuẩn.
- [x] `pytest tests/`: 256 pass (253 baseline + 3 mới), 24 skip, không hồi quy.
- [ ] **CÒN LẠI (cần người dùng)**: test thủ công trực tiếp trong app GUI trên `QD 719.pdf` — bôi đen bằng chuột thật + bấm nút "Sửa text gốc", xác nhận bằng mắt vị trí không nhảy + màu khớp. (Môi trường tự động không thao tác chuột trên GUI được.)
