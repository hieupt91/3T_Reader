# QUY TRÌNH SỬA LỖI — 3T Reader (Mac & Win)

> Đọc file này TRƯỚC khi bắt tay sửa bất kỳ lỗi nào.
> Mục tiêu: sửa **đúng một lỗi đang báo**, không lan man, không làm hỏng
> tính năng khác, không để chồng chéo code.
> Bản ngắn: xem thêm [`FIX_RULES.md`](FIX_RULES.md).

---

## 0. Nguyên tắc vàng

1. **Chỉ sửa đúng lỗi đang được báo.** Không tiện tay "cải tiến" thứ khác.
2. **Đọc trước — sửa sau.** Hiểu đúng luồng code liên quan rồi mới đụng.
3. **Không đoán.** Tái hiện lỗi bằng dữ liệu thật, xác minh nguyên nhân trước khi sửa.
4. **Tối thiểu hoá thay đổi.** Sửa ít dòng nhất có thể để trị đúng gốc.
5. **Không làm mất/hỏng tính năng khác.** Kiểm lại các luồng liên quan sau khi sửa.
6. **Rà chồng chéo code.** Trước khi thêm, tìm xem đã có hàm/logic tương tự chưa.

---

## 1. Trước khi sửa — HIỂU LỖI

- [ ] Đọc kỹ mô tả lỗi + xem ảnh/chụp màn hình nếu có.
- [ ] Xác định **chính xác 1 triệu chứng** cần trị lần này. Nếu báo gộp nhiều
      triệu chứng → tách ra, làm từng cái, đừng trộn.
- [ ] **Tái hiện lỗi**: chạy app / viết script nhỏ với **file/dữ liệu thật** để
      thấy tận mắt. Không sửa khi chưa tái hiện được.
- [ ] Tìm đúng file/hàm chịu trách nhiệm (grep theo từ khoá, lần theo luồng gọi).
- [ ] Đọc **trọn luồng** đó (từ nơi nhận input đến nơi ra kết quả), không đọc mảnh.

## 2. Trước khi sửa — RÀ CHỒNG CHÉO

- [ ] Hàm/logic mình định thêm **đã tồn tại chưa**? (grep tên hàm, từ khoá).
      → Nếu có, TÁI DÙNG, đừng viết bản thứ hai.
- [ ] Có **đường code trùng lặp** làm cùng việc không? (vd nhiều nơi cùng reload,
      cùng detect span...). Nếu có → đây thường CHÍNH LÀ nguồn lỗi (gọi 2 lần,
      đè nhau). Gộp/bỏ bớt thay vì thêm.
- [ ] Thay đổi này có đụng **cùng file/hàm** mà tính năng khác đang dùng không?
      Liệt kê các caller trước khi đổi chữ ký hàm / hành vi.

## 3. Khi sửa

- [ ] Sửa đúng điểm gốc, **không rải rác** nhiều chỗ cho "chắc ăn".
- [ ] Giữ nguyên hành vi các nhánh không liên quan.
- [ ] Nếu buộc đổi hành vi dùng chung (vd contract với VPS, engine PDF dùng chung
      Win/Mac) → **giữ nguyên contract**, không tự đổi.
- [ ] Comment ngắn giải thích **vì sao** sửa (không chỉ sửa gì) để lần sau không
      bị lặp lỗi.

## 4. Sau khi sửa — KIỂM CHỨNG

- [ ] `python -m py_compile` (và `node --check` với file .js) — không lỗi cú pháp.
- [ ] **Tái chạy đúng kịch bản lỗi** → xác nhận đã hết.
- [ ] **Chạy thử tính năng liên quan** để chắc không làm hỏng:
      - sửa text → thử cả click 1 từ, bôi đen cụm, sửa nhiều lần liên tiếp.
      - đụng viewer/reload → thử cuộn giữa trang rồi thao tác, xem có nhảy không.
      - đụng ký số / OCR / xuất → chạy 1 lượt cơ bản.
- [ ] Chạy test liên quan (`pytest tests/...`). Nếu có test đỏ → xác định là do
      mình hay **đỏ sẵn từ trước** (so với nhánh gốc), ghi rõ.
- [ ] Nếu thay đổi lớn/rủi ro: tạo tag/backup trước (`git tag backup/...`,
      `git stash`), để lỡ hỏng còn khôi phục.

## 5. Báo cáo khi xong (bắt buộc)

Ghi rõ, ngắn gọn:
- **Nguyên nhân gốc** (1–2 câu).
- **Đã sửa file nào**, sửa gì.
- **Phạm vi ảnh hưởng** (còn đụng gì khác không).
- **Đã kiểm chứng gì** (kịch bản nào, test nào).
- Còn **giới hạn/nợ** gì (nếu có).

## 6. Commit

- Mặc định **không commit** cho tới khi người dùng đồng ý.
- Khi được đồng ý: **commit riêng từng lỗi/tính năng**, message rõ nguyên nhân +
  cách sửa. Chỉ `git add` đúng các file thuộc lỗi đó, không gom lẫn WIP khác.
- Không tự ý `push` / `force-push` / rebuild container / deploy khi chưa được phép
  (đặc biệt với repo & VPS dùng chung Win/Mac).

---

## 7. Bẫy thường gặp trong dự án này (nhớ để tránh)

- **Redact = hộp trắng che, KHÔNG xoá chữ gốc trong stream.** Đọc lại text sau
  khi sửa sẽ thấy 2 span chồng nhau (cũ bị che + mới). Khi detect phải ưu tiên
  span khớp đúng text đang thao tác (`prefer_text`), kẻo nhắm nhầm span cũ.
- **Text-layer PDF nhúng/chữ nghiêng hay lệch.** Đừng tin toạ độ/█text từ trình
  duyệt tuyệt đối: lấy *text* từ selection, lấy *vị trí* bằng PyMuPDF `search_for`.
- **macOS: Ctrl+chuột trái bị đổi thành chuột phải (button=2)** và bật context
  menu. Xử lý chuột có Ctrl phải tính tới điều này.
- **Reload viewer gây nhấp nháy + dễ nhảy trang.** Nếu overlay đủ thể hiện thì
  ưu tiên overlay; nếu buộc reload thì đừng ép `currentPageNumber`, khôi phục
  scroll theo cả vị trí lẫn tỉ lệ.
- **PyMuPDF/fitz là AGPL.** Bản Mac thương mại đã gỡ; đừng vô tình nhập lại
  `import fitz` vào luồng chạy thật (chỉ được dùng ở chỗ đã chấp nhận, vd đọc
  metadata offline nội bộ nếu có quy ước rõ).
- **Nhánh Mac (`piper-vps-sync`/`phase1-mac`) khác kiến trúc bản Win.** Mục nào
  Win đặc thù thì review luồng tương ứng của Mac, KHÔNG bê thẳng code Win sang.

---

## 8. Mẫu nhắn giao việc cho mỗi lỗi

```
Lỗi số X: [mô tả triệu chứng cụ thể + file/thao tác tái hiện].
Đọc QUY_TRINH_SUA_LOI.md và làm theo:
- chỉ sửa đúng lỗi này, không lan man
- rà chồng chéo code trước khi thêm
- kiểm chứng không làm hỏng tính năng khác
- xong báo: nguyên nhân, file sửa, phạm vi ảnh hưởng, đã test gì
```
