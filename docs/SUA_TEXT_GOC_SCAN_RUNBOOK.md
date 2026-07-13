# Runbook thực thi: Sửa text gốc chính xác cho PDF scan

**Vai trò file này**: checklist tự thực thi, tự kiểm tra từng bước. Đọc từ trên xuống, làm tới đâu tick tới đó, KHÔNG bỏ bước xác minh. Dựa trên `docs/SUA_TEXT_GOC_SCAN_IMPLEMENTATION_PLAN.md` — đọc file đó trước nếu cần lý do/bối cảnh, file này chỉ có hành động + lệnh kiểm tra.

**Quy tắc khi thực thi**:
- Sau MỖI bước sửa code: chạy `py_compile` ngay, KHÔNG dồn nhiều thay đổi rồi mới kiểm.
- Không xóa/đổi hành vi nhánh PDF vector (`_apply_text_edit_vector`) — chỉ thêm mới, không sửa code cũ nếu không bắt buộc.
- File thật để test: `C:\Users\HieuPC\Desktop\QD 719.pdf` (đã có OCR sẵn, 43 trang).
- Nếu 1 bước xác minh FAIL: dừng lại, đọc lại code, sửa, xác minh lại — không sang bước tiếp theo với bước trước còn fail.

---

## Bước 0 — Chuẩn bị / baseline

- [ ] `cd "C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win"`, chạy `git status` — ghi nhận trạng thái sạch/bẩn trước khi bắt đầu.
- [ ] Chạy toàn bộ test suite baseline: `./.venv/Scripts/python -m pytest tests/ -q` — ghi lại số test pass hiện tại (kỳ vọng: khớp số đã biết từ trước, không có fail nào do việc khác).
- [ ] Đọc lại `app/actions/edit.py` vùng `on_click()` (khoảng dòng 2694-2870) để có số dòng CHÍNH XÁC hiện tại trước khi sửa (số dòng có thể lệch so với plan doc do các commit sau này).

## Bước 1 — Viết `_sample_text_ink_color()`

- [ ] Mở `app/actions/edit.py`, tìm hàm `_sample_background_color` (đã có sẵn).
- [ ] Thêm hàm `_sample_text_ink_color()` NGAY SAU `_sample_background_color`, copy đúng code mẫu trong `SUA_TEXT_GOC_SCAN_IMPLEMENTATION_PLAN.md` mục 4.1.
- [ ] `./.venv/Scripts/python -m py_compile app/actions/edit.py` — phải sạch.
- [ ] **Xác minh bằng dữ liệu thật ngay lập tức** (không đợi tới cuối), chạy script sau và xác nhận output đúng như mô tả:

```bash
cd "C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win"
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python -c "
import sys
sys.path.insert(0, '.')
from app.actions.edit import _sample_text_ink_color
path = r'C:\Users\HieuPC\Desktop\QD 719.pdf'
# box cua chu 'UY' da do o phien truoc (toa do PDF pt, khong phai pixel)
# fitz bbox top-down: (113.5, 52.5, 140.8, 68.0), page_h=842
# quy doi sang box (left, bottom, right, top) he PDF (goc duoi-trai):
page_h = 842.0
box = (113.5, page_h - 68.0, 140.8, page_h - 52.5)
color = _sample_text_ink_color(path, 1, box)
print('Mau muc uoc luong:', color)
assert color is not None, 'FAIL: tra ve None'
r, g, b = color
assert r < 0.3 and g < 0.3 and b < 0.3, f'FAIL: mau qua sang, ky vong toi (gan RGB 33,31,39/255): {color}'
print('PASS: mau toi, hop ly (ky vong ~ (0.13, 0.12, 0.15))')
"
```

- [ ] Kỳ vọng output: `color ≈ (0.13, 0.12, 0.15)` (khớp RGB(33,31,39)/255 đã đo ở phiên trước) và dòng `PASS`. Nếu ra màu gần trắng (>0.7) → thuật toán lọc percentile sai, kiểm tra lại `dark_percentile`/hướng sort.

## Bước 2 — (Tùy chọn) Viết `_estimate_bold_from_ink_density()`

- [ ] Nếu làm: copy code mẫu mục 4.2 của plan doc, đặt sau `_sample_text_ink_color`.
- [ ] `py_compile` lại.
- [ ] Nếu KHÔNG làm bước này: `_apply_text_edit_scan` ở Bước 4 dùng cứng `is_bold = False`, ghi rõ trong code bằng comment `# ponytail: bold luôn False cho scan, thêm heuristic khi cần`.

## Bước 3 — Viết `_apply_text_edit_vector()`

- [ ] Tìm toàn bộ logic hiện có trong `on_click()` áp dụng cho nhánh KHÔNG phải scan (đường `use_span_box=True`, phần `if span_info: if use_span_box: ...`).
- [ ] Trích xuất thành hàm riêng `_apply_text_edit_vector(window, state, page_num, pick_box, new_text, styles)` theo mẫu mục 3.2 — trả về 1 `dict` op giống cấu trúc `op` hiện có trong `on_click` (`type`, `page_number`, `box`, `text`, `font_size`, `font_color`, `font_family`, `bold`, `baseline`, `is_existing_edit`, v.v. — copy đúng các key hiện có, không tự bịa key mới).
- [ ] `py_compile`. Hàm này CHƯA được gọi ở đâu — chỉ tồn tại độc lập, sẽ nối dây ở Bước 5.

## Bước 4 — Viết `_apply_text_edit_scan()`

- [ ] Theo mẫu mục 3.3 của plan doc. Điểm bắt buộc phải đúng (tự kiểm bằng cách đọc lại code vừa viết):
  - [ ] Biến `box` được gán **DUY NHẤT** từ `pick_box` — grep lại trong hàm vừa viết, xác nhận **KHÔNG có dòng nào** gán `box = span_info["box"]` hay tương tự.
  - [ ] `font_color` gọi `_sample_text_ink_color`, KHÔNG đọc `span_info["font_color"]`.
  - [ ] `patch_image` gọi `_build_scan_patch` với box đã có `patch_pad`.
- [ ] `py_compile`.
- [ ] Lệnh tự kiểm cụ thể (grep để chắc chắn không lỡ tay để lọt code cũ):

```bash
cd "C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win"
grep -n "_apply_text_edit_scan" -A 40 app/actions/edit.py | grep -n "span_info\[.box.\]\|span_info\['box'\]"
```

- [ ] Kỳ vọng: **KHÔNG có output nào** (grep không match gì trong thân hàm `_apply_text_edit_scan`). Nếu có match → BUG, sửa ngay trước khi đi tiếp.

## Bước 5 — Nối dây: sửa `on_click()` thành hàm điều phối

- [ ] Sửa phần đầu `on_click()`: sau khi có `new_text`/`state`/box đã chuẩn hoá (left/bottom/right/top), thay toàn bộ khối logic cũ (`span_info = _find_pdf_span(...)`, `is_scan_page = ...`, các nhánh `if/else` dài) bằng:

```python
box = (left, bottom, right, top)
is_scan_page = _page_is_scan_text(base_snapshot, int(pageNum))
if is_scan_page:
    op = _apply_text_edit_scan(window, state, int(pageNum), box, text_value, styles)
else:
    op = _apply_text_edit_vector(window, state, int(pageNum), box, text_value, styles)
```

- [ ] **CẨN THẬN**: `on_click()` hiện tại còn xử lý case `text_value` rỗng (xóa text, không chèn text mới) — xem lại code gốc dòng ~2824-2840 (nhánh `elif patch_info is not None:`) và ~2841-2849 (nhánh `else:` redact thường). Đảm bảo 2 hàm mới (`_apply_text_edit_vector`/`_apply_text_edit_scan`) **vẫn xử lý đúng case xóa text** (khi `new_text` rỗng) — không chỉ case thay text. Nếu cấu trúc op trả về giống hệt op cũ thì phần code sau đó (`state["ops"].append(op)`, `_render_edit_state`, `reload_document`) không cần đổi gì.
- [ ] `py_compile` toàn file `edit.py`.

## Bước 6 — Chạy lại toàn bộ test suite

- [ ] `./.venv/Scripts/python -m pytest tests/ -q -p no:cacheprovider`
- [ ] So với baseline ở Bước 0: **số test pass phải >= baseline, KHÔNG có test nào fail mới**. Đặc biệt chú ý `tests/test_edit_ocr_font.py` (test hiện có cho vùng code này).
- [ ] Nếu có fail: đọc traceback, đây gần như chắc chắn là do đổi cấu trúc/tên biến trong lúc tách hàm — sửa cho khớp lại, không sửa test để "cho qua".

## Bước 7 — Viết 4 test case mới (mục 5.1 plan doc)

- [ ] Thêm vào `tests/test_edit_ocr_font.py`:
  1. `test_sample_text_ink_color_reads_dark_ink_not_background` — dựng ảnh PIL giả (nền trắng + chữ đen/xám vẽ bằng `ImageDraw`), nhúng vào PDF qua reportlab (xem cách các test khác trong file này đã làm để tái dùng helper), gọi `_sample_text_ink_color`, assert màu trả về TỐI (mỗi kênh < 0.4) và KHÁC màu nền (mỗi kênh > 0.7 chênh lệch so với nền trắng).
  2. `test_sample_text_ink_color_handles_colored_ink` — vẽ chữ màu xanh dương đậm (vd `(20, 30, 160)`) thay vì đen, assert kênh Blue trong kết quả > kênh Red (tức không bị ép về đen/xám trung tính).
  3. `test_edit_scan_position_matches_pick_box_not_span` — mock/monkeypatch `_find_pdf_span` trả về span có `box` CỐ Ý lệch xa so với `pick_box` truyền vào; gọi `_apply_text_edit_scan`; assert `op["box"] == pick_box` (không bị kéo theo span).
  4. `test_edit_vector_position_uses_span_box` — tương tự nhưng gọi `_apply_text_edit_vector` với PDF có text thật, assert vị trí trả về KHÔNG PHẢI `pick_box` gốc nếu `pick_box` cố ý hơi lệch so với span thật (tức xác nhận có snap, đúng hành vi mong muốn cho nhánh vector).
- [ ] `./.venv/Scripts/python -m pytest tests/test_edit_ocr_font.py -v` — cả 4 test mới phải PASS, không skip (skip chỉ chấp nhận nếu do thiếu Tesseract, không phải do lỗi code).

## Bước 8 — Test thủ công trên file thật (bắt buộc, không được bỏ qua)

- [ ] Dọn cache tạm trước khi test (tránh nhiễu từ session cũ): `rm -rf "$LOCALAPPDATA/Temp/reader_pdf_edit"`
- [ ] Mở app với `QD 719.pdf`, đợi thông báo "Đã nhận diện văn bản...".
- [ ] Bôi đen "ỦY BAN NHÂN DÂN" (hoặc cụm tương tự), bấm Sửa text gốc, nhập text thay thế NGẮN HƠN 1-2 ký tự (để dễ nhận biết đây là bản đã sửa).
- [ ] Quan sát: vị trí text mới có nằm ĐÚNG chỗ vừa bôi đen không (so với hành vi cũ đã biết là hay "nhảy").
- [ ] Quan sát: màu chữ mới có TỐI/ĐEN gần giống các chữ xung quanh không (không phải đen tuyệt đối nổi bật khác biệt nếu bản scan gốc màu nhạt/xám).
- [ ] Lặp lại ở tiêu đề "QUYẾT ĐỊNH" (cỡ chữ khác) — xác nhận size vẫn hợp lý.
- [ ] Mở song song 1 file PDF thường (convert Word, có sẵn trong repo — vd file test hoặc bất kỳ file .docx→pdf nào có) — sửa text gốc — xác nhận **không có hồi quy** (vẫn chính xác như trước khi có thay đổi này).
- [ ] Ghi lại kết quả quan sát bằng chữ (không chỉ "có vẻ ổn") — mô tả cụ thể lệch bao nhiêu (nếu còn), màu có khớp không.

## Bước 9 — Dọn dẹp & tổng kết

- [ ] Kiểm tra `git diff --stat` — chỉ có `app/actions/edit.py` (+có thể `tests/test_edit_ocr_font.py`) bị đổi, không lem sang file khác không liên quan.
- [ ] Đọc lại toàn bộ diff 1 lượt bằng mắt trước khi coi là xong — tìm code chết/trùng lặp có thể dọn (vd nếu logic cũ trong `on_click` còn sót lại đoạn không dùng tới nữa sau khi tách hàm).
- [ ] Cập nhật checklist ở cuối `SUA_TEXT_GOC_SCAN_IMPLEMENTATION_PLAN.md` (tick các mục đã xong).
- [ ] Báo cáo tóm tắt cho người dùng: đã sửa gì, test nào pass, kết quả quan sát thủ công ở Bước 8 — **không tự ý commit**, chờ người dùng xác nhận.

---

## Tiêu chí HOÀN THÀNH (định nghĩa "xong")

Tất cả điều sau đều đúng:
1. Bước 6 và Bước 7: toàn bộ test pass, không fail, không giảm số lượng.
2. Bước 8: quan sát bằng mắt trên file thật xác nhận vị trí KHÔNG còn nhảy sai + màu chữ KHÔNG còn luôn đen tuyệt đối.
3. Bước 8 phần PDF thường: không có hồi quy.
4. Bước 9: diff sạch, đúng phạm vi, đã báo cáo, CHƯA commit (chờ người dùng).

Nếu bất kỳ điều nào ở trên chưa đạt — CHƯA được báo là "xong" với người dùng.
