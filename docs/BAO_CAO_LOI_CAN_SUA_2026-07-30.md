# Báo cáo lỗi cần sửa — 2026-07-30

> **Chỉ dẫn bắt buộc khi sửa (đọc trước khi động vào bất kỳ mục nào dưới đây):**
> Khi sửa: phải đọc kỹ code liên quan trước khi sửa, sửa đúng nguyên nhân gốc (không chỉ vá triệu chứng), sửa dứt điểm. Chỉ tập trung sửa đúng lỗi được liệt kê, không lan man sang phần khác. TUYỆT ĐỐI không được xóa hoặc làm mất bất kỳ tính năng nào đang có — chỉ sửa lỗi.

Đây là báo cáo triage — mỗi mục có đủ file:line + nguyên nhân để người sửa không cần điều tra lại từ đầu. Thứ tự: crash trước, hiệu năng sau, cosmetic cuối.

---

## A. Lỗi gây crash ứng dụng ("văng ứng dụng")

### A1. [Mức độ: CRASH] [Trạng thái: xác nhận còn sống] Ghi đè file PDF trong lúc thumbnail vẫn đang render nền → access violation cứng
**Vị trí:**
- Chỗ thiếu guard (KHÔNG kiểm tra trước khi ghi file): `app/actions/edit.py:1964` (`save_edits`), `app/actions/edit.py:2032` (`save_edits_quiet`), `app/actions/edit.py:2038` (`save_edits_as`), `app/actions/ocr.py:388` (`ocr_current_page`), `app/actions/ocr.py:428` (`ocr_full_document`), `app/actions/sign.py:2032` (`sign_with_pfx`), `app/actions/sign.py:2172` (`sign_document`), `app/actions/sign.py:2390` (`sign_handwritten`), `app/actions/sign.py:2786` (`sign_document_batch`), `app/actions/pages.py:285` (`rotate_pages_action`), `app/actions/pages.py:449` (`merge_pdfs_action`), `app/actions/pages.py:583` (`split_pdf_action`)
- Cơ chế guard đã có nhưng chỉ 1 nơi dùng: `app/sidebar.py:226-239` (`ThumbnailSidebar.is_loading()`), được gọi duy nhất tại `app/actions/auto_ocr.py:152-169` (`_sidebar_is_loading`)
- Bằng chứng crash thật trong `app_log.txt`: `app/sidebar.py:48` (`ThumbnailLoader.run`) → `packages/pdf_engine/pdfium_engine.py:92` (`render_page_rgb`) → `OSError: exception: access violation reading 0x0000...` → `Fatal Python error: Aborted` (crash toàn tiến trình, không bắt được bằng try/except vì là lỗi native, không phải Python exception).

**Nguyên nhân gốc:** `ThumbnailLoader` chạy trên `threading.Thread` nền, giữ 1 document handle pypdfium2 mở trong lúc lặp render các trang. Nếu file trên đĩa bị ghi đè (save/OCR/ký số/xoay trang/gộp/tách) trong lúc handle này còn sống, pypdfium2 có thể crash cứng (access violation ở tầng C, kill toàn bộ process). `app/sidebar.py` đã tự nhận diện đúng rủi ro này và cung cấp `is_loading(pdf_path)` để caller kiểm tra trước khi ghi — nhưng chỉ auto-OCR dùng, còn lại **10 hàm ghi file khác hoàn toàn không gọi**.

**Hướng sửa đề xuất:** Đưa guard vào 1 chỗ dùng chung (helper ghi file ở `app/actions/_pdf_save.py`) để tất cả các hàm trên đi qua cùng 1 điểm kiểm tra `is_loading()` trước khi thay file — sửa 1 lần ở gốc thay vì vá từng hàm.

---

### A2. [Mức độ: CRASH] [Trạng thái: xác nhận còn sống] `QThread.terminate()` khi người dùng huỷ tải xuống
**Vị trí:** `app/actions/document_converter.py:90-94`
```
while thread.isRunning():
    QApplication.processEvents()
    if progress_dlg.wasCanceled():
        thread.terminate()
        return False
```
**Nguyên nhân gốc:** `terminate()` giết thread ngay tại điểm nó đang chạy (kể cả đang giữa 1 lệnh I/O mạng), không cho thread dọn dẹp. Đây là pattern nguy hiểm đã biết của Qt/threading — có thể để lại state hỏng hoặc crash tiến trình, không chỉ raise exception Python thường.

**Hướng sửa đề xuất:** Thay bằng 1 cờ huỷ (cancel flag) mà thread tự kiểm tra giữa các chunk tải, không dùng `terminate()`.

---

### A3. [Mức độ: CRASH] [Trạng thái: CHƯA XÁC NHẬN — cần điều tra thêm trước khi sửa] `libshiboken: Internal C++ object đã bị xoá` (QThread / QWebEngineView)
**Vị trí:** Chưa xác định được điểm gọi cụ thể trong thời gian điều tra.
**Đã kiểm tra:**
- `app/ai_translate_dialog.py:737-752` — **ĐÃ CÓ guard đúng**: `closeEvent` chặn đóng dialog (`event.ignore()`) nếu QThread còn `isRunning()`. Không phải nguồn gây lỗi này.
- `app/actions/piper_tts_manager.py:322` (`DownloadThread`) — không tìm thấy `closeEvent`/`isRunning()` guard tương ứng trên dialog sở hữu nó → nghi vấn, nhưng chưa lần ra được chắc chắn.
- Chưa tìm ra điểm nào tạo crash `QWebEngineView` đã bị xoá.

**Hướng sửa đề xuất:** Trước khi sửa, cần rà lại toàn bộ các nơi dùng `QThread` (`app/ai_task_runner.py`, `app/dialogs.py`, `app/window.py`, `app/actions/export.py`, `app/actions/piper_tts_manager.py`) xem dialog/widget sở hữu có `closeEvent`/guard chặn đóng khi thread còn chạy hay không, theo đúng pattern đã đúng ở A này (`ai_translate_dialog.py`). **Không suy đoán sửa khi chưa xác định được điểm gọi thật.**

---

## B. Lỗi hiệu năng ("chạy lag")

### B1. [Mức độ: HIỆU NĂNG] [Trạng thái: xác nhận còn sống — nguyên nhân chính của "ký số bị lag"] Quét USB/PKCS11 token chạy đồng bộ trên UI thread, mỗi lần quét tự khởi chạy lại toàn bộ file .exe của app cho từng driver ứng viên
**Vị trí:**
- `packages/signing/windows_provider.py:652-708` (`WindowsSigningProvider.list_tokens`) — cache TTL chỉ **8 giây** (`windows_provider.py:638: self._tokens_cache_ttl_seconds: float = 8.0`), nên gần như mọi thao tác ký số cách nhau quá 8s (rất hay gặp: đọc tài liệu 1 lúc rồi mới ký) đều phải quét lại từ đầu.
- `windows_provider.py:662` gọi `_candidate_paths()` (quét registry + filesystem đệ quy tới 4 cấp qua nhiều thư mục CA — VNPT, Viettel, FPT, BKAV...) — chi phí filesystem/registry, không phải chi phí chính.
- `windows_provider.py:677-679`: với mỗi driver hợp lệ tìm được, mở 1 `ThreadPoolExecutor` (song song, không phải tuần tự) gọi `_probe_driver_tokens(path)` cho từng driver.
- **Điểm nặng nhất:** `windows_provider.py:506-509`:
  ```python
  command = (
      [sys.executable, "--pkcs11-list-tokens", path]
      if getattr(sys, "frozen", False)
      else [sys.executable, "-c", code, path]
  )
  ```
  Trong bản build đã đóng gói (`frozen=True`, tức bản cài thật user dùng), `sys.executable` chính là **`3T_Reader.exe`** — mỗi driver ứng viên sẽ khởi chạy lại **toàn bộ tiến trình app đóng gói** (PyInstaller onedir hàng trăm MB, đầy đủ DLL Qt/WebEngine dù worker mode thoát sớm ở `main.py:36-39`) làm subprocess, timeout tới 10s/driver (`windows_provider.py:516`). Việc tạo tiến trình cho 1 bundle PyInstaller onedir lớn luôn tốn nhiều trăm ms tới vài giây, dù các driver chạy song song.
- **Toàn bộ chuỗi trên chạy ĐỒNG BỘ trên UI thread**, không có QThread/worker nào bọc ngoài, tại **tất cả** các điểm gọi:
  - `app/actions/sign.py:1888-1893` (`check_token`, gắn trực tiếp vào nút "Kiểm tra USB ký số" — `app/window.py:720`, `app/window.py:971`)
  - `app/actions/sign.py:1461-1462` (bên trong `sign_document`/`sign_document_batch`)
  - `app/actions/sign.py:1461-1462` (bên trong `UnsignedSignatureSetupDialog.__init__`, xem mục B2 bên dưới)

**Nguyên nhân gốc:** thiết kế probe PKCS11 bằng cách relaunch chính file .exe đã đóng gói làm subprocess dò driver, chạy đồng bộ trên UI thread, cache quá ngắn (8s) nên gần như luôn phải quét lại.

**Hướng sửa đề xuất:** bọc `list_tokens()`/`detect_driver()` trong QThread + worker (đã có sẵn pattern `_TokenPresenceWorker` ở `app/window.py:230` để tham khảo, dùng cho việc kiểm tra USB định kỳ nền — nhưng đó là bản "có/không có token", KHÁC với `list_tokens()` đầy đủ thông tin chứng thư dùng khi ký); tăng `_tokens_cache_ttl_seconds` hợp lý hơn 8s; cân nhắc cache kết quả song song với `_TokenPresenceWorker` định kỳ 15s đã có sẵn thay vì quét lại từ đầu mỗi lần người dùng bấm ký.

---

### B2. [Mức độ: HIỆU NĂNG] [Trạng thái: xác nhận còn sống — liên quan trực tiếp tới cả "mở file cũ lag" lẫn "ký số lag"] Click vào ô ký số chưa ký trong file đã mở → quét token đồng bộ ngay trong constructor của dialog
**Vị trí:** `app/window.py:2229-2265` (`_on_signature_clicked`) → `app/actions/sign.py:1422-1462` (`UnsignedSignatureSetupDialog.__init__`, dòng 1461-1462 gọi `get_signing_provider()` + `_list_signing_tokens(provider)` trực tiếp trong `__init__`, cùng chi phí như mục B1).

**Nguyên nhân gốc:** giống hệt B1, nhưng đường vào khác — người dùng chỉ cần **mở 1 file PDF đã có sẵn ô ký số chưa ký (rất điển hình cho "file cũ" đã làm việc trước đó) và click vào ô đó**, dialog sẽ tự quét PKCS11 đồng bộ ngay trong `__init__`, dù có `QProgressDialog` + 1 lần `processEvents()` (`app/window.py:2251-2256`) — không đủ để tránh UI đơ vì chỉ bơm event loop 1 lần, không phải vòng lặp async thật.

**Hướng sửa đề xuất:** cùng hướng B1 — chuyển quét token ra nền, dialog chỉ hiển thị kết quả khi có; đây có thể chính là nguồn gốc cảm giác "mở file cũ bị lag" nếu file đó có ô ký số.

---

### B3. [Mức độ: HIỆU NĂNG] [Trạng thái: đã kiểm tra kỹ — phần lớn KHÔNG phải nguyên nhân] Khởi động app ("mở app quá lag")
Đã rà lại kỹ hơn lần trước, kết luận: phần lớn startup **đã được defer đúng cách**, không phải nguồn lag chính:
- License check (`packages/license_client/vps_client.py:224-234`, `validate_cached`) — đường phổ biến (offline Ed25519 verify hợp lệ) trả về ngay, việc gọi server chạy nền (`_validate_server_background`), không block.
- AI config, update check, USB token monitor — đều `QTimer.singleShot` (`app/window.py:314,318,3672`).
- Không có thư viện nặng (`openai`, `anthropic`, `pyhanko`, `pdf2docx`, `pdfplumber`, `openpyxl`...) được import ở top-level của các module `app/actions/*.py` được `app/window.py` import — đã grep toàn bộ, không có kết quả.
- `packages/pdf_engine/__init__.py:15` khởi tạo `PdfiumEngine()` ở mức module — nhưng constructor rỗng (không I/O), chi phí không đáng kể.
- `packages/signing/windows_provider.py`, `packages/ocr/engine.py` — không có code chạy ở mức module (chỉ định nghĩa `def`/`class`), không quét gì lúc import.

**Điểm khả nghi duy nhất, mức độ nhẹ, CHƯA XÁC NHẬN LÀ NGUYÊN NHÂN CHÍNH:** `app/language_manager.py:675-685` (`get_translation`) — với ngôn ngữ mặc định "vi" thì đa số key có sẵn trong `BUILTIN_TRANSLATIONS` nên trả về ngay (dòng 677), **không đọc file**; chỉ khi key KHÔNG có trong builtin mới rơi vào `load_language_pack()` (dòng 640-650, đọc + parse JSON từ đĩa) — và hàm này **không cache theo `code`**, nên nếu nhiều trong số 42 lần gọi `self._t()` lúc dựng UI (`app/window.py`, đếm được 42 chỗ) đều miss builtin, file JSON pack sẽ bị đọc lại nhiều lần liên tiếp cho cùng 1 ngôn ngữ. Với người dùng dùng "vi" mặc định thì tác động gần như bằng 0; nếu dùng ngôn ngữ khác chưa cover đủ builtin thì có thể có vài chục lần đọc file thừa lúc khởi động — không phải chi phí lớn (file JSON nhỏ) nhưng là 1 chỗ đáng dọn nếu muốn tối ưu thêm.

**Kết luận cho B3:** chi phí khởi động lớn nhất khả năng cao đến từ việc khởi tạo `QWebEngineView` (Chromium embed, `app/window.py:26`) — vốn có trong kiến trúc (PDF.js chạy trong Chromium), không phải bug sửa được ở tầng code app. Nếu người dùng cảm thấy "mở app lag" theo nghĩa mở 1 **file cụ thể** bị chậm (không phải mở app trống), khả năng cao là đang gặp B1/B2 (quét PKCS11) chứ không phải khởi động app thuần tuý — xem thêm B4.

**Hướng sửa đề xuất (nếu muốn tối ưu thêm, không phải bug):** cache `load_language_pack()` theo `code` (vd `functools.lru_cache`) để tránh đọc lại file JSON nhiều lần trong 1 phiên.

---

### B4. [Mức độ: HIỆU NĂNG] [Trạng thái: xác nhận 1 phần — outline lớn; phần "token scan" xem B2] Mở file PDF cũ (đã làm việc trước đó) bị lag
Tách 2 nguyên nhân riêng biệt đã tìm được cho "mở file cũ lag":

1. **Đã xác nhận, liên quan tới file có ô ký số chưa ký:** xem mục **B2** ở trên — không phải do "file cũ" nói chung, mà do file đó có sẵn ô ký số và người dùng thao tác với nó.
2. **Xác nhận 1 phần, liên quan tới file có mục lục (TOC/outline) lớn:** `app/sidebar.py:469-498` (`BookmarkSidebar._read_outline`) mở file bằng pikepdf và đệ quy duyệt toàn bộ outline (`_collect`, dòng 481-495) **đồng bộ trên UI thread**, được gọi mỗi lần mở file tại `app/window.py:2279` (`_load_toc_for_active`). Với file có outline sâu/nhiều mục (thường gặp ở file "cũ" đã làm việc nhiều, có TOC đầy đủ hơn file mới tạo) chi phí này tăng theo số mục outline, không cache, không chạy nền.
3. **Không tìm thấy** cơ chế "migration/version-upgrade" nào chỉ chạy cho file chưa từng mở trước đó — không có bằng chứng cho giả thuyết này, coi như đã loại trừ.

**Hướng sửa đề xuất:** với (2), cân nhắc đưa `_read_outline` chạy nền (giống pattern `ThumbnailLoader`) nếu file có outline lớn; với (1) xem hướng sửa ở B2.

---

## C. Lỗi đã kiểm tra và XÁC NHẬN ĐÃ FIX / không còn tái hiện (liệt kê để không ai mất công điều tra lại)

- **[Đã fix]** `'PySide6.QtWidgets.QComboBox' object has no attribute 'currentFont'`: đã kiểm tra toàn bộ nơi dùng `font_combo`/`_font_combo` hiện tại (`app/insert_text_dialog.py:124` dùng đúng `QFontComboBox.currentFont()`; `app/actions/edit.py:1573-1701`, `app/pdf_inline_editor.py:138-338`, `app/ocr_dialog.py:130-135` đều là `QComboBox` thường và đều gọi đúng `.currentText()`). Log cũ, không còn tái hiện.
- **[Đã fix]** `'PDFViewerWidget' object has no attribute 'page'`: không còn nơi nào gọi `viewer.page(...)` trực tiếp trên `PDFViewerWidget`; tất cả đã dùng đúng `self._web_view.page()` (`app/pdf_viewer.py:245,268,472,560,575,587,605`).
- **[Đã fix]** `SyntaxError: invalid character '—' (U+2014)` tại `app/ai_chat_dialog.py:175`: docstring hiện tại dùng dấu gạch ngang thường `-`, không còn ký tự em-dash gây lỗi cú pháp.
- **[Chưa xác định được, khả năng cao là log cũ — không ưu tiên điều tra thêm]:** `unterminated f-string literal (detected at line 291)`, `unsupported format character ';' (0x3b) at index 8572`, `'_TextEditDialog' object has no attribute '_font_combo'`, `save to original must be incremental`, file tạm `work_*.pdf` bị mất. `app_log.txt` không có timestamp và đã được xác nhận chứa nhiều lỗi lịch sử đã fix (xem 3 mục trên) — không nên vá mù các mục này khi chưa tái hiện được trên code hiện tại.
- **[Còn sống nhưng mức độ thấp, không khẩn]** Lỗi `charmap codec can't encode character` (Tiếng Việt) khi `print()` trên console cp1252 của Windows — cùng loại lỗi gặp lại trong chính session vá lỗi này (ở script deploy, không thuộc app). Không gây crash toàn app, chỉ mất log/output tại chỗ gọi `print()`. Không ưu tiên trừ khi muốn dọn log sạch.

---

## D. Cosmetic

### D1. [Mức độ: COSMETIC] [Trạng thái: xác nhận còn sống, đã tìm ra nguyên nhân khả dĩ] Icon PDF không đổi khi xem ở chế độ "Details" trong Explorer sau khi đặt 3T Reader làm app mặc định
**Vị trí:** `installer_script.iss:112`
```
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden
```
Đối chiếu với `installer_script.iss:68,71` (đã set đúng `DefaultIcon` registry cho `3TReader.PDF` và `Applications\3T_Reader.exe`) và `installer_script.iss:120-127` (`SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, 0, 0)` sau cài đặt).

**Nguyên nhân gốc (khả dĩ):** `ie4uinit.exe -show` không phải cờ xoá icon cache — cờ thường dùng để ép Windows rebuild toàn bộ icon cache database (vốn cache theo nhiều size/slot khác nhau, Details view có thể đọc từ 1 slot cache riêng chưa được làm mới bởi `SHChangeNotify`) là `ie4uinit.exe -ClearIconCache` (chữ C hoa).

**Hướng sửa đề xuất:** thêm/thay bằng `ie4uinit.exe -ClearIconCache` trong `[Run]`.
