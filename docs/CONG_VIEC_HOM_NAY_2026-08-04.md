# Công việc cần xử lý — 2026-08-04

Trạng thái xác nhận trực tiếp trên code (`git log`, `grep`) tại HEAD (`85a6b29`, nhánh `piper-vps-sync`), không suy đoán từ tài liệu cũ.

## 1. Bug mới — cảnh báo "Chưa lưu xong chú thích" hiện sai khi chỉ đọc tài liệu

**Đã sửa (phương án 1)** — chỉ chặn đóng tab/app khi có **chú thích do người dùng** thao tác chưa lưu; nếu chỉ còn OCR nền ghi thất bại thì bỏ qua batch OCR đó và cho đóng bình thường (OCR sẽ tự chạy lại lần mở file sau).

- **Hiện tượng**: mở app/tab lâu, không thao tác chú thích gì, khi đóng tab hoặc thoát app vẫn bị chặn bởi hộp thoại "Chưa lưu xong chú thích" (`app/window.py:2427`, `:3632`).
- **Root cause**: hộp thoại này dùng chung `_AnnotationOpQueue` (`app/actions/annotate.py:95`) với **auto-OCR chạy nền** — mỗi trang scan OCR xong sẽ tự enqueue một lệnh ghi PDF vào đúng hàng đợi "chú thích" này (`app/actions/auto_ocr.py:192`, gọi `_queue_annotation_op`). Người dùng không hề bấm công cụ chú thích nào nhưng auto-OCR đã tự tạo "thay đổi chưa lưu" thay họ.
- **Vì sao im lặng lúc đang đọc, chỉ lộ ra lúc đóng**: nếu 1 lần ghi thất bại (`app/actions/annotate.py:190-197`), hàng đợi chỉ báo qua status bar 3.5 giây (`showMessage(...)`) rồi tự retry sau 1.2s — **lặp vô hạn, không giới hạn số lần thử**, rất dễ bị bỏ lỡ nếu người dùng đang đọc chứ không nhìn status bar. Đến lúc đóng tab/app, `_close_tab`/`closeEvent` gọi `flush_all()` lại thất bại y hệt → hiện dialog chặn.
- **Ảnh hưởng**: sai thông điệp (đổ lỗi "chú thích" cho lỗi do OCR nền), và về nguyên tắc hàng đợi có thể retry vô hạn trong nền tiêu tốn CPU nếu nguyên nhân ghi lỗi (khóa file, quyền ghi, antivirus...) không tự hết.

### Đã sửa — báo cáo theo FIX_RULES.md

- **File đã sửa**:
  - `app/actions/annotate.py` — `_AnnotationOpQueue` gắn cờ `is_user_edit` cho mỗi item trong `_pending` (mặc định `True`); `has_pending()`/`has_pending_annotations()` thêm tham số `user_only`; thêm `drop_ocr_pending()` để bỏ riêng các item OCR chưa ghi kịp mà không đụng tới item của người dùng.
  - `app/actions/auto_ocr.py` — dòng gọi `_queue_annotation_op(..., is_user_edit=False)` khi enqueue kết quả OCR nền.
  - `app/window.py` — 2 điểm chặn đóng (`_close_tab` dòng ~2420, `closeEvent` dòng ~3624): chỉ hiện dialog cảnh báo + chặn đóng khi `has_pending_annotations(..., user_only=True)` còn `True`; nếu chỉ còn OCR nền thất bại thì gọi `drop_ocr_pending()` rồi cho đóng bình thường.
- **Phạm vi ảnh hưởng**: chỉ thay đổi *điều kiện chặn khi đóng tab/thoát app*. Không đổi hành vi lưu chú thích thật của người dùng (vẫn chặn đóng như cũ nếu có chú thích chưa lưu), không đổi luồng OCR, không đổi cách flush/ghi file. Không áp dụng phương án 2 (giới hạn số lần retry) — ngoài phạm vi lỗi đang báo, để dành nếu phát sinh riêng.
- **Đã kiểm tra**:
  - `pytest tests/test_annotation_queue.py` — 6/6 pass (test cũ không cần sửa vì `is_user_edit`/`user_only` đều có default giữ nguyên hành vi cũ).
  - `pytest tests/` toàn bộ — 328 pass, 3 fail. Cả 3 fail đã xác nhận **pre-existing** (fail giống hệt khi `git stash` bỏ toàn bộ thay đổi này): `test_annotation_search_line_marks.py::test_underline_and_strikeout_can_use_current_search_query_without_selection`, `test_stability_contracts.py::test_ai_chat_session_persists_history_to_disk`, `test_viewer_annotation_regressions.py::test_tc42_strict_selection_does_not_search_duplicate_text` — không liên quan tới thay đổi này.
- **Chưa commit** (mặc định theo FIX_RULES.md — chỉ commit khi bạn ghi rõ).

## 2. Rủi ro pháp lý còn treo từ audit 30/07 — CHƯA XỬ LÝ

- **PyMuPDF (AGPL-3.0) vẫn còn `import fitz` / `fitz.open()`** tại `app/actions/edit.py` và `app/pdf_text_editor.py` (đã grep xác nhận lại hôm nay, không phải tồn đọng cũ đã fix). Đây là hạng mục 🔴 Critical duy nhất của audit `docs/audit_2026-07-30/`, cần quyết định business (mua license Artifex hay thay bằng pypdfium2/pikepdf) trước — không phải việc code có thể tự quyết.

## 3. Đã xác nhận FIXED (không cần làm lại)

| Hạng mục audit 30/07 | Trạng thái | Commit |
|---|---|---|
| Khóa ghi PDF không nhất quán giữa các module (H1) | ✅ Fixed 30/07 | `f264763` |
| Cache token PKCS11 không khóa (M-medium) | ✅ Fixed | `e5d5685` |
| 3 dialog hard-code dark mode (License/OCR/Audit-log) | ✅ Fixed | `286c51c` |
| iTaxViewer install treo không timeout/hủy (H3) | ✅ Fixed | `28e8acf` |
| Gemini/HuggingFace thiếu thư viện khi đóng gói | ✅ Fixed | `e80d946` |

## 4. Việc treo cũ chưa làm (từ `docs/3_CHUA_LAM.md`, chưa verify lại hôm nay)

- [ ] Tester retest TC27–TC41 trên build mới, cập nhật `docs/Test Case 3T Reader.xlsx`.
- [ ] Deploy `vps_license_service.py` + `vps_models.py` lên VPS license.
- [ ] Đổi mật khẩu VPS (mật khẩu cũ từng lộ trong Git), xóa `pass.txt` khỏi lịch sử Git (`git filter-repo`), chuyển sang SSH key.
- [ ] Build bản Windows mới (installer + portable) để bàn giao tester.
