# Ghi chú Cập nhật Piper TTS (Đồng bộ Mac & Win)

Trong quá trình ráp nối tính năng Đọc sách bằng AI (Piper TTS) từ nhánh Windows sang macOS, đội Mac đã phát hiện và vá một số lỗi logic/cấu trúc có thể ảnh hưởng đến cả 2 nền tảng. Team Win cần lưu ý và đồng bộ lại nếu đang dùng chung mã nguồn:

## 1. Lỗi mất đường dẫn URL cập nhật (Cập nhật thất bại)
**Nguyên nhân:** Khi duyệt danh sách giọng nói từ VPS (`index.json`), hàm `fetch_available_piper_voices` cũ sẽ bỏ qua (`continue`) những giọng đã tồn tại ở local. Hậu quả là những giọng local này bị gán `onnx_url=""`. Khi người dùng bấm "Tải về / Cập nhật" để lấy bản mới nhất từ VPS, phần mềm bị báo lỗi `unknown url type: ''`.
**Cách fix (Đã áp dụng trên Mac):** 
Chuyển sang cơ chế hợp nhất (Merge/Upsert). Dùng `voices_by_id` dictionary để cập nhật `onnx_url` và `json_url` của máy chủ đè vào thông tin local, thay vì skip. 

## 2. Lỗi Crash đột ngột (EXC_BAD_ACCESS) khi tải lỗi / Tải xong
**Nguyên nhân:** Khởi tạo `DownloadThread(voice, self)` với `parent=self` (là QDialog). Khi xuất hiện cảnh báo lỗi hoặc người dùng đóng cửa sổ, cơ chế Garbage Collection của PySide6 sẽ phá hủy Dialog kèm theo Thread đang chưa kịp dọn dẹp bộ nhớ, gây Crash toàn bộ ứng dụng.
**Cách fix (Đã áp dụng trên Mac):**
Gỡ bỏ tham chiếu parent: `self.dl_thread = DownloadThread(voice)`. Thêm kết nối tự dọn dẹp: `self.dl_thread.finished.connect(self.dl_thread.deleteLater)`.

## 3. Lỗi chặn chứng chỉ bảo mật mạng (SSL)
**Nguyên nhân:** Trên một số máy Mac hoặc Windows thiếu chứng chỉ gốc (Root CA), `urllib.request` sẽ từ chối tải file từ VPS hoặc HuggingFace (báo lỗi `CERTIFICATE_VERIFY_FAILED`).
**Cách fix (Đã áp dụng trên Mac):**
Trong hàm `_open_no_proxy`, tiêm thêm context bỏ qua kiểm duyệt SSL:
```python
import ssl
ssl_context = ssl._create_unverified_context()
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ssl_context),
    urllib.request.ProxyHandler({})
)
```

## 4. Xử lý UI thân thiện khi máy chủ không có giọng đọc
**Cách fix (Đã áp dụng trên Mac):**
Khi ấn Tải/Cập nhật, nếu `voice.onnx_url` rỗng (giọng local cũ không có trên VPS hiện tại), hiện cảnh báo màu vàng "Giọng đọc này không có trên máy chủ để tải/cập nhật" thay vì báo lỗi mạng hoặc Crash ngầm.

---
**Hành động tiếp theo:**
Đội Win vui lòng `git pull` bản `release-1.0.7-baseline-ocr-ai` mới nhất để thừa hưởng bản sửa lỗi toàn diện này vào `app/actions/piper_tts_manager.py`.
