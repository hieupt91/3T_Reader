# QUY TRÌNH SỬA LỖI QUÁN TRIỆT — 3T Reader

> Bổ sung cho `FIX_RULES.md`. Khi người dùng nêu lỗi **và trỏ vào file này**,
> đọc xong rồi làm ĐÚNG theo quy trình dưới đây — không tự chế cách khác.
>
> **Câu thần chú**: *Sửa đúng một lỗi, ở đúng một chỗ, với diff nhỏ nhất — sau
> khi đã thực sự hiểu lỗi.* Diff nhỏ ở SAI chỗ không phải "gọn", đó là bug thứ hai.

---

## 0. NGUYÊN TẮC TỐI THƯỢỢNG (đọc trước mọi thứ)

1. **Chỉ sửa đúng lỗi đang được nêu.** Không "tiện tay" sửa/cải tiến thứ khác.
2. **Không làm ảnh hưởng tính năng khác.** Mỗi thay đổi phải trả lời được:
   "code này còn ai gọi nữa, sửa xong họ có hỏng không?"
3. **Hiểu trước, sửa sau.** Cấm sửa khi chưa tái hiện được lỗi và chưa chỉ ra
   được ĐÚNG dòng gây lỗi. Đoán mò = tạo bug mới.
4. **Không tự commit.** Báo cáo, chờ người dùng xác nhận (theo `FIX_RULES.md`).
5. **Sửa tận gốc, không vá triệu chứng** — nhưng "tận gốc" nghĩa là đúng chỗ
   tất cả caller đi qua, KHÔNG phải sửa lan ra nhiều nơi.

---

## 1. GIAI ĐOẠN HIỂU — bắt buộc, không được bỏ

Trước khi gõ 1 ký tự sửa code:

### 1.1. Tái hiện lỗi bằng bằng chứng cụ thể
- Chạy được lỗi (script/headless/mở app) và **thấy** nó, có số liệu/ảnh/log.
- KHÔNG chấp nhận "chắc là do...". Nếu chưa tái hiện được → chưa đủ hiểu để sửa.
- Với lỗi hiển thị (vị trí/màu/render): render ra ảnh và **nhìn bằng mắt**, đo
  toạ độ/pixel thật. Với lỗi crash: đọc traceback đầy đủ trong `app_log.txt`.

### 1.2. Tìm ROOT CAUSE, không phải triệu chứng
- Đi ngược từ triệu chứng về dòng code đầu tiên sai. Hỏi "tại sao" đến tận cùng.
- Ví dụ thật (phiên này): "chữ nhảy lên trên" → triệu chứng. Root cause: đặt
  `baseline=None` → renderer rơi vào `_draw_text_box` tính vị trí theo box đã
  phình cao → đẩy baseline lên 5pt. Sửa triệu chứng (nudge xuống 5pt) là SAI;
  sửa gốc là trả lại baseline đúng.

### 1.3. Đánh giá BÁN KÍNH ẢNH HƯỞNG (blast radius) — trước khi sửa
- `grep` mọi caller của hàm/biến sắp sửa: nó được gọi từ đâu, mấy nơi?
- Hàm này có phục vụ NHIỀU luồng không? (vd một hàm dùng chung cho cả PDF
  thường lẫn scan, cho cả bôi đen lẫn click).
- Liệt kê ra giấy (trong đầu/ghi chú) các tính năng có thể bị ảnh hưởng.
- **Nếu sửa 1 nhánh mà nhánh khác dùng chung code → tách nhánh, đừng đổi chung.**

---

## 2. GIAI ĐOẠN ĐÁNH GIÁ RỦI RO — quyết định CÁCH sửa an toàn nhất

Cân nhắc theo thứ tự ưu tiên (chọn cách rủi ro thấp nhất mà vẫn sửa gốc):

| Ưu tiên | Cách sửa | Khi nào |
|---|---|---|
| 1 | Thêm điều kiện/nhánh mới, KHÔNG đụng code cũ đang đúng | Lỗi chỉ ở 1 loại đầu vào/1 trường hợp |
| 2 | Sửa tại 1 hàm dùng chung (choke point) | Mọi caller đều cần fix giống nhau |
| 3 | Tách hàm chung thành 2 khi 2 luồng cần hành vi khác | Trộn logic gây bug (vd scan vs vector) |
| 4 | Đổi hành vi hàm cũ | Chỉ khi 100% chắc mọi caller đều muốn hành vi mới |

**Quy tắc vàng khi có 2 luồng (A và B) dùng chung code và chỉ A lỗi:**
- KHÔNG sửa code chung theo kiểu làm B đổi hành vi.
- Rẽ nhánh sớm: `if <đúng loại A>: xử lý riêng A / else: giữ nguyên B`.
- Ví dụ thật: "sửa text gốc" — trang scan (A) và PDF vector (B) phải rẽ nhánh
  theo `is_scan_page`. Sửa scan **tuyệt đối không** đổi nhánh vector đang chạy tốt.

---

## 3. GIAI ĐOẠN SỬA — tối thiểu, kỷ luật

- Diff nhỏ nhất khả thi. Mỗi dòng thêm/sửa phải phục vụ đúng lỗi đang sửa.
- **Không** đổi tên biến, format lại, "dọn dẹp" nhân tiện trong cùng lần sửa lỗi
  (làm review khó, che mất thay đổi thật, dễ lẫn regression).
- Sau MỖI thay đổi nhỏ: `py_compile` ngay, không dồn.
- Comment ngắn nêu LÝ DO (constraint), không mô tả code làm gì.

### Loại bỏ code chồng chéo / không dùng — CÓ ĐIỀU KIỆN
- Chỉ xóa khi: (a) `grep` toàn repo xác nhận **0 caller** (kể cả gọi động qua
  tên, JS, webchannel), và (b) không phải file đang deploy khác nhánh.
- Nếu là code chết chắc chắn NẰM TRONG vùng đang sửa → xóa luôn cho sạch.
- Nếu code chết ở CHỖ KHÁC không liên quan lỗi → ghi chú lại, ĐỪNG xóa trong
  lần sửa lỗi này (tách việc, tránh lan man).

---

## 4. GIAI ĐOẠN KIỂM CHỨNG — không xong nếu chưa qua hết

- [ ] `py_compile` các file đã sửa: sạch.
- [ ] `pytest tests/ -q`: số pass **>= baseline**, KHÔNG fail mới. So với số đã
      ghi trước khi sửa.
- [ ] **Tái hiện lại đúng kịch bản lỗi** → xác nhận đã hết (bằng ảnh/số liệu,
      không phải "có vẻ ổn").
- [ ] **Kiểm hồi quy các tính năng liên quan** đã liệt kê ở mục 1.3 — đặc biệt
      nhánh code dùng chung (vd sửa scan xong phải thử lại PDF vector).
- [ ] Diff sạch, đúng phạm vi (`git diff --stat` chỉ đụng file cần đụng).
- [ ] Báo cáo: sửa file nào, phạm vi ảnh hưởng, đã kiểm gì. **Chưa commit.**

---

## 5. CẠM BẪY ĐÃ BIẾT CỦA 3T READER (tra trước khi sửa vùng liên quan)

| Vùng | Cạm bẫy | Phải làm |
|---|---|---|
| **pypdfium2** (mọi `pdfium.PdfDocument(...)`) | Thư viện KHÔNG thread-safe. Gọi từ 2 thread cùng lúc → access violation, sập cả app (không try/except bắt được) | Bọc trong `PDFIUM_LOCK` (`packages/pdf_engine/pdfium_engine.py`) |
| **Signal Qt từ thread nền** | Nối `signal.connect(lambda...)` khi worker chạy ở background thread → slot chạy nhầm trên background thread → thao tác GUI/QTimer sập âm thầm | Nối vào **bound-method của QObject sống ở main thread** (xem `_AutoOcrRelay`, `_SigningLoopRelay`, `sidebar._on_loader_*`) |
| **Sửa/chèn text** (`app/actions/edit.py`) | Scan và PDF vector là 2 luồng khác nhau. Trộn logic gây "nhảy điểm", "tô trắng mảng", "nhảy baseline" | Rẽ nhánh theo `is_scan_page`. Scan: ngang từ box chọn, **dọc bó khít theo span OCR**, baseline Y từ OCR, màu từ `_sample_text_ink_color`. Vector: span PyMuPDF ghi đè cả vị trí+style |
| **`_build_scan_patch`** | Vá box quá cao (theo chọn chuột) → tô trắng cả khoảng dòng trên/dưới | Bó box khít theo span trước khi vá |
| **webchannel** (`app/webchannel.py`) | Thêm slot vào bridge thật mà quên thêm vào proxy → JS gọi lỗi "not a function" | Mỗi slot mới phải có mặt ở CẢ bridge thật LẪN proxy tương ứng |
| **License client** (`packages/license_client/vps_client.py`) | Tin cache JSON không ký → bypass license | Chỉ cấp quyền từ token Ed25519 đã verify; `_offline_status` không được trả active từ cache |
| **Backend VPS** | Code deploy thật ở nhánh `phase1-backend:server/license-api/app/` (1285 dòng), KHÁC `main_api.py` snapshot ở nhánh này | Sửa backend phải làm trên đúng bản đang chạy, không deploy nhầm snapshot |
| **File rời rạc nhiều bản** | `main.py` gọi tính năng qua `app/actions/*` — nhiều closure lồng nhau (vd `on_click` trong `edit_existing_text`) | Đọc kỹ scope closure trước khi tách; tách sai gây circular import / mất biến |

---

## 6. CASE STUDY THẬT (bài học xương máu trong repo này)

**Lỗi gốc**: "sửa text gốc" trên file scan bị lệch vị trí + màu luôn đen.

**Cái làm ĐÚNG**: tách nhánh scan/vector; đọc màu mực từ pixel thật; đo số liệu
thật trên `QD 719.pdf` trước khi sửa; tái hiện bằng render + nhìn ảnh.

**Cái làm SAI (gây regression, phải sửa lại nhiều vòng)** — để tránh lặp lại:
1. **Vứt `baseline` (đặt = None)** vì tưởng baseline OCR không tin được → thực
   ra baseline DỌC của OCR chính xác, vứt đi làm chữ nhảy lên 5pt. → *Bài học:
   đừng vứt dữ liệu đang đúng chỉ vì một phần khác của nó nhiễu. Tách phần đúng
   (dọc) khỏi phần nhiễu (ngang).*
2. **Bỏ luôn "bó box theo span"** khi sửa phần vị trí ngang → làm miếng vá cao
   bằng cả vùng chọn chuột → tô trắng 1 mảng. → *Bài học: khi "sửa vị trí" chỉ
   động đến 1 chiều (ngang), ĐỪNG đụng chiều còn lại (dọc) đang đúng.*
3. **Sửa rộng nhiều vòng** thay vì đánh giá kỹ 1 lần → mỗi vòng lại đẻ lỗi mới.
   → *Bài học: dừng lại, tái hiện đủ, hiểu trọn round-trip toạ độ rồi mới sửa
   một phát đúng.*
4. **Viết test/repro assert nhầm hàm phụ** (chỉ kiểm tra lẻ `_page_is_scan_text` thay vì toàn bộ logic `OR` thực tế của code) → tự gây báo động giả (false alarm) làm hoang mang và mất thời gian đi tìm lỗi không có thật. → *Bài học: khi viết script tái hiện/verify, phải mô phỏng ĐÚNG luồng logic/điều kiện mà app đang chạy (end-to-end component), không test một hàm con lẻ loi rồi vội vàng kết luận.*

**Kết luận rút ra**: một thay đổi "nhỏ và hợp lý trên giấy" vẫn có thể phá tính
năng nếu chưa hiểu hết luồng. Luôn tái hiện + nhìn kết quả thật sau khi sửa.

---

## 7. CHECKLIST NGẮN (in ra, làm theo mỗi lần)

```
[ ] Tái hiện được lỗi + có bằng chứng (ảnh/số liệu/log)
[ ] Chỉ ra ĐÚNG dòng root cause (không phải triệu chứng)
[ ] grep caller — biết blast radius, liệt kê tính năng liên quan
[ ] Chọn cách sửa rủi ro thấp nhất (ưu tiên thêm nhánh, không đổi code chung)
[ ] Diff tối thiểu, không dọn dẹp/đổi tên nhân tiện
[ ] py_compile sạch
[ ] pytest >= baseline, không fail mới
[ ] Tái hiện lại → xác nhận HẾT lỗi (bằng ảnh/số liệu)
[ ] Thử lại tính năng liên quan (nhánh dùng chung) — không hồi quy
[ ] Báo cáo file/phạm vi/đã kiểm gì — CHƯA commit
```
