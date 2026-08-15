# 10 — Bug List

Danh sách bug cụ thể tìm được (race condition, deadlock, thread-safety, vòng lặp vô hạn, đệ quy, null-reference, off-by-one). Không lặp lại các bug đã tìm và sửa ở các phase trước trong phiên này (xem `01_Executive_Summary.md` bảng "đã xử lý").

## [High] [Confidence: High] #1 — Ghi file PDF không được khóa đồng bộ nhất quán giữa các module

**File/dòng**:
- Có khóa: `app/actions/annotate.py:29` (định nghĩa `_PDF_SAVE_LOCK`), dùng tại `annotate.py:176`, `annotate.py:2685`, `pages.py:424` (import tại `pages.py:418`).
- **Không có khóa**: `app/actions/sign.py`, `app/actions/edit.py`, `app/actions/document_ops.py` — xác nhận qua `grep -rl "_PDF_SAVE_LOCK" app/actions/*.py` chỉ trả về `annotate.py` và `pages.py`.
- `auto_ocr.py` an toàn gián tiếp (ghi qua `_queue_annotation_op`, dùng chung khóa này).

**Cơ chế lỗi**: autosave chú thích debounce 250-520ms (`_queue_annotation_op(..., delay_ms=250..520)`, ví dụ `annotate.py:1207,1908,2471,3171`). Nếu user bôi đen 1 đoạn rồi trong khoảng thời gian đó bấm Lưu (`edit.py`), Ký số (`sign.py`), hoặc Thêm watermark (`document_ops.py`) — 2 đường code độc lập cùng mở/đọc/ghi 1 file PDF không có phối hợp gì.

**Kịch bản kích hoạt**: bôi đen văn bản → bấm Ctrl+S hoặc "Ký tài liệu" ngay sau đó — luồng thao tác hoàn toàn bình thường, không phải trường hợp hiếm gặp.

**Tác động**: vì tất cả các bên ghi đều dùng chung pattern staged-file + `os.replace()` nguyên tử, bản thân file KHÔNG hỏng (không có trạng thái ghi dở dang). Nhưng là **last-writer-wins** — 1 trong 2 thao tác bị mất âm thầm (mất 1 highlight, hoặc mất 1 chữ ký/lần lưu vừa thực hiện). **Mất dữ liệu im lặng, không báo lỗi cho user.**

**Khác với bug đã sửa trong phiên này**: bug thumbnail-render (A1, đã sửa) là race giữa pypdfium2 đọc và file-replace; đây là race giữa 2 BÊN GHI với nhau, chưa được xử lý.

**Hướng sửa đề xuất**: mở rộng phạm vi `_PDF_SAVE_LOCK` (hoặc khóa tương đương) vào điểm ghi chung `app/actions/_pdf_save.py` — cùng tinh thần với cách A1 đã trung tâm hóa guard `is_loading()`.

## [Medium] [Confidence: Medium-High] #2 — `WindowsPkcs11Provider` là singleton dùng chung, cache không khóa, đọc/ghi từ 2 thread

**File/dòng**: `packages/signing/__init__.py:16-29` (`get_signing_provider()`, singleton module-level). `packages/signing/windows_provider.py:632-645` (`_tokens_cache`, `_tokens_cache_until`, `_selected_token` — thuộc tính instance thường, không khóa).

**Cơ chế**: cả `_TokenPresenceWorker` (nền, mỗi 15s) và các điểm gọi UI thread (`check_token`, `sign_document`, `UnsignedSignatureSetupDialog.__init__`) dùng chung 1 instance. Nếu cả 2 cùng thấy cache hết hạn tại 1 thời điểm, cả 2 chạy song song 1 lượt quét đầy đủ, rồi cả 2 cùng ghi `_tokens_cache`/`_tokens_cache_until` — ai ghi sau thắng. `detect_driver()`'s `self._selected_token = tokens[0]` (dòng 655) cùng lớp race.

**Tác động**: GIL của CPython đảm bảo gán thuộc tính đơn lẻ không bị "xé" (không crash/hỏng dữ liệu cấu trúc). Kịch bản xấu nhất thực tế: quét trùng lặp lãng phí, đọc tạm thời danh sách token cũ, hoặc — nếu user cắm nhiều USB ký số cùng lúc — `_selected_token` lật sang token sai, khiến 1 lần ký dùng nhầm danh tính người ký. Gây khó chịu/nhầm lẫn, không làm hỏng dữ liệu.

## [High] [Confidence: High] #3 — Vòng lặp chờ cài iTaxViewer không timeout, không nút hủy

**File/dòng**: `app/actions/document_converter.py:1004-1039` (`_run_itax_installer_silent`). `progress.setCancelButton(None)` (dòng 1032) loại bỏ hẳn nút hủy; `while proc.poll() is None: QApplication.processEvents()` (dòng 1034) không giới hạn thời gian. Dialog `WindowModal` (dòng 1031), khóa tương tác với cửa sổ chính.

**Cơ chế**: nếu tiến trình cài đặt iTaxViewer (bên thứ 3, không do 3T kiểm soát) treo vì bất kỳ lý do gì (prompt ẩn dù có `/VERYSILENT`, antivirus can thiệp, disk đầy), vòng lặp quay vô hạn. UI vẫn "sống" (event được pump) nhưng cửa sổ bị khóa window-modal, **không có nút, timeout, hay lối thoát nào trong app** ngoài kill process qua Task Manager.

**So sánh**: 2 vòng lặp `DownloadThread` trong cùng file (đã sửa phiên này) đều có giới hạn — request có `timeout=120`, và cả 2 giờ có nút hủy hoạt động thật. Chỗ này là 1 đường code khác, chưa được sửa cùng đợt.

## Đã kiểm tra kỹ, KHÔNG có bug

| Khu vực | Kết luận |
|---|---|
| `BookmarkSidebar._read_outline`'s `_collect` đệ quy (`app/sidebar.py:533-547`) | Không có giới hạn độ sâu tường minh, nhưng toàn bộ hàm bọc trong `try/except Exception: return []` — `RecursionError` là subclass `Exception`, bị bắt, trả về TOC rỗng thay vì crash. Chạy trên thread nền. Mức độ: Thông tin, không phải bug. |
| `app/window.py`'s `threading.Thread` duy nhất (`_start_update_check`, dòng 2598) | Kết nối signal qua bound-method đúng cách (không lambda), Qt tự queue đúng lên main thread. Có comment giải thích rõ lý do (né bug QThread ở PySide6 6.11+Python 3.14). |
| `app/actions/annotate.py` — quy tắc "bound-method cho signal cross-thread" | 0 chỗ `.connect(lambda` trong toàn file — quy tắc tự đặt ra được tuân thủ nhất quán. |
| `tts_dialog.py:806` vòng lặp poll TTS macOS | Có cờ hủy + `.terminate()`, chạy off-main-thread, và **chỉ áp dụng macOS** (N/A cho bản Windows này). |
| Số học trang 0-index/1-index | Kiểm tra mẫu ~13 điểm ở `pages.py`, `annotate.py` — nhất quán dùng `page_no - 1`/`page_num - 1` cho truy cập mảng. Vài chỗ dùng tham số `page_idx` đã convert sẵn thay vì `-1` inline — có vẻ chủ đích (quy ước đặt tên `_idx` vs `_no`), chưa trace hết mọi caller nên confidence Thấp cho phần này riêng. |

## Chưa điều tra đầy đủ (ghi nhận, không đoán)

Rủi ro null-reference chỉ được kiểm tra mẫu, chưa rà hệ thống — nhiều hàm action gọi `window.viewer.get_current_page()` bọc trong `try/except Exception: pass` rộng, sẽ nuốt luôn lỗi nếu `window.viewer` là `None` giống như bất kỳ lỗi nào khác. Chưa xác định được `window.viewer` có thực sự có thể là `None` tại các điểm gọi đó trong thực tế hay không.

## Tổng kết

| Mức độ | Số lượng |
|---|---|
| High | 2 |
| Medium | 1 |
| Đã kiểm tra, sạch | 5 khu vực |
| Chưa điều tra đủ | 1 mục (null-reference hệ thống) |
