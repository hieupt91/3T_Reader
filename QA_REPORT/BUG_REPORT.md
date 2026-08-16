# Bug Report — phiên test mở rộng (đa-tab + file nặng + thao tác chi tiết)

## BUG-QA-01: Lỗi "[WinError 5] Access is denied" khi tự động lưu chú thích lúc mở file mới

- **Severity:** P2 (tự phục hồi, không mất dữ liệu, nhưng hiện lỗi gây hoang mang cho người dùng)
- **Environment:** 3T Reader 1.0.34.3, Windows, app cài tại `C:\Program Files\3T Reader`
- **Precondition:** Mở 1 file PDF mới trong khi thư mục chứa file đó đã có 1 file PDF khác vừa/đang được xử lý (annotation auto-save)
- **Exact steps:**
  1. Mở `heavy1_dao_giao_original.pdf` (711MB) từ `QA_REPORT/test_fixtures/`
  2. Quan sát status bar ngay sau khi trang đầu render xong
- **Expected:** Không có lỗi hiện ra, hoặc nếu có cơ chế retry thì không hiển thị lỗi kỹ thuật thô cho người dùng
- **Actual:** Status bar hiện: `Chưa lưu được chú thích, sẽ thử lại: [WinError 5] Access is denied: 'C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\QA_REPORT\test_fixtures\.3t_stage_yujjndn1.pdf' -> ...`. Vài giây sau tự retry thành công, hiện "Đã tự động lưu chú thích."
- **Reproducibility:** ALWAYS — tái hiện được ở cả `heavy1_dao_giao_original.pdf` VÀ `heavy4_uone_catalog.pdf` (2/2 lần thử với 2 file khác nhau, tên staging file khác nhau mỗi lần: `.3t_stage_yujjndn1.pdf`, `.3t_stage_afujw_h4.pdf`, `.3t_stage_vt7w6mdw.pdf`)
- **Impact:** Không mất dữ liệu (tự phục hồi), nhưng người dùng cuối nhìn thấy thông báo lỗi kỹ thuật tiếng Anh ("WinError 5: Access is denied") ngay khi mở file — gây lo lắng không cần thiết, đặc biệt với người dùng không rành kỹ thuật.
- **Suggested investigation area:** Cơ chế auto-save chú thích/staging (`.3t_stage_*.pdf`) tạo file tạm ngay trong thư mục chứa file nguồn — khả năng cao là race condition: file handle của lần mở/OCR trước đó (hoặc antivirus/indexing của Windows) vẫn đang giữ khoá thư mục trong khoảnh khắc file mới được mở. Nên: (a) thử tạo file staging ở thư mục temp riêng thay vì cùng thư mục nguồn, hoặc (b) không hiển thị lỗi kỹ thuật thô ra status bar ở lần thử đầu nếu cơ chế retry gần như luôn thành công.

## BUG-QA-02 (quan sát, chưa đủ bằng chứng): Ký tự có dấu mất glyph trong nội dung PDF

- **Severity:** P3 / chưa xác nhận
- Xem chi tiết ở `FULL_TEST_REPORT.md` mục "Phát hiện đáng chú ý" — nghi lỗi font của file test tự tạo, cần test lại bằng file PDF tiếng Việt có dấu thật để kết luận chắc chắn.

## BUG-QA-01: ĐÃ SỬA

Xem `app/actions/annotate.py` — chỉ hiện raw exception ở lần retry áp chót thay vì ngay từ đầu. Test regression: `tests/test_annotation_queue.py::test_flush_retry_hides_raw_exception_until_near_final_attempt` (fail trên code cũ, pass trên code mới, xác nhận qua git stash).

## Kết quả test bổ sung (chèn ảnh, xuất file, ký PFX)

- **Chèn ảnh** (bug #21): chèn `test_insert_image.png` vào `medium_50pages.pdf`, xác nhận đúng flow object-action-session (kéo/resize/Enter xác nhận), ảnh vẫn hiển thị đúng sau khi chuyển tab đi và quay lại — **PASS**, xác nhận fix bug #21 hoạt động đúng trên app thật.
- **Xuất Văn bản** (Tệp → Bảo mật Xuất → Văn bản): xuất `medium_50pages.pdf` ra `.txt` thành công, nội dung khớp đúng từng trang — **PASS**.
- **Ký PFX** (Ký số → Ký PFX): full flow vẽ vùng ký → xác nhận vị trí → chọn `qa_test_signer.pfx` → nhập mật khẩu → xem thông tin chữ ký → lưu file → xác nhận ghi đè — toàn bộ UI flow hoạt động đúng, không crash. Bước cuối (áp chữ ký thật) bị từ chối với `PathBuildingError` từ `pyhanko_certvalidator` — **đây là hành vi ĐÚNG**, vì `qa_test_signer.pfx` là chứng thư tự ký (self-signed), không có chuỗi tin cậy tới CA gốc, nên bị LTV validation từ chối đúng thiết kế bảo mật. Không phải bug.
- **Ký số USB Token thật**: máy có gắn token thật (phát hiện `CD Drive Viettel-CA_v6`), nhưng việc nhập mã PIN token là thao tác bảo mật thật — mình không tự nhập PIN (không biết và không nên đoán mã bảo mật của bạn). Để bạn tự test tay khi cần.
- **Ghép/Tách PDF**: chưa kịp test trong phạm vi thời gian phiên này.

## Ghi chú kỹ thuật automation (không phải bug app): Windows dialog navigation

Trong lúc test, phát hiện: gõ text trực tiếp (cả `SendInput` Unicode lẫn VK-code) vào các ô nhập trong dialog của app KHÔNG vào được (do UIPI chặn input tổng hợp tới cửa sổ chạy elevated) — **nhưng dán clipboard (Ctrl+V) thì hoạt động bình thường**. Đây là giới hạn của phương pháp automation, không phải lỗi của 3T Reader.

## Không phát hiện thêm bug P0/P1 nào trong các thao tác đã test trực tiếp:
- Xoay phải trang (rotate) — PASS
- Xoá trang có xác nhận, không thể hoàn tác — PASS, đúng cảnh báo
- Đánh số trang (2 bước dialog: chọn vị trí → số bắt đầu) — PASS, không giật hình (xác nhận fix bug #23 hoạt động đúng)
- Cảnh báo "Tài liệu rất lớn" khi mở thêm file nặng trong lúc đã có file nặng khác đang mở — PASS, đúng cơ chế bảo vệ RAM
- Multi-tab với 3 file 700MB+ đồng thời (heavy1/2/3) + 2 file trung bình (heavy4/5) + 2 file nhỏ = 7 tab — app ổn định suốt, RAM chỉ ~747MB-879MB (không phình theo dung lượng file gốc — cơ chế render lazy/stream hiệu quả), không có tab nào lẫn nội dung với tab khác
