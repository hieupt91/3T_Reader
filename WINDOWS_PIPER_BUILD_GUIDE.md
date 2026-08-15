# Hướng Dẫn Tích Hợp Piper TTS Dành Cho Nhóm Phát Triển Windows

Chào anh em team Windows, tính năng **Đọc Offline cực mượt (Piper TTS)** đã được viết xong và push lên branch `release-1.0.7-baseline-ocr-ai`.

Để đóng gói (Build) phần mềm 3T Reader bằng `PyInstaller` thành công trên Windows mà không bị lỗi engine Piper, anh em làm theo các bước sau nhé:

## 1. Chuẩn bị Engine Piper cho Windows
- Tải file lõi của Piper cho Windows (`piper_windows_amd64.zip`) từ trang chủ Github của Piper (hoặc trong nhóm chia sẻ nội bộ).
- Giải nén ra, bạn sẽ thấy file `piper.exe` và các file `*.dll` đi kèm (như `onnxruntime.dll`, `espeak-ng.dll` v.v.).
- Copy toàn bộ các file này (bao gồm `piper.exe` và các thư viện dll) bỏ vào một thư mục tên là `piper_bin`.
- Đặt thư mục `piper_bin` nằm ở thư mục gốc của project (ngang hàng với `main.py`).

## 2. Cấu trúc thư mục trước khi Build
Đảm bảo project có cấu trúc sau:
```text
3T_Reader/
├── main.py
├── app/
├── piper_bin/
│   ├── piper.exe
│   ├── onnxruntime.dll
│   ├── ... (các file dll khác)
```

## 3. Lệnh Build với PyInstaller
Khi chạy lệnh PyInstaller, anh em phải chỉ định để nó chép thư mục `piper_bin` vào bên trong thư mục cài đặt gốc. Thêm cờ `--add-data` như sau (chú ý dấu chấm phẩy `;` trên Windows):

```bash
pyinstaller --name "3T Reader" --add-data "piper_bin;piper_bin" --windowed main.py
```

## 4. Test sản phẩm
Sau khi Build xong:
- Người dùng cuối cài đặt phần mềm ra sẽ không cần phải cài thêm bất cứ môi trường Python hay C++ nào cả.
- Khi người dùng click nút "Cửa hàng Giọng AI" -> Ứng dụng sẽ tự động tải các gói giọng từ VPS về máy của họ.
- Code ở `app/actions/piper_tts_manager.py` đã được team Mac thiết kế để tự động nhận diện `os.name == 'nt'` và gọi chính xác `piper_bin\piper.exe` rồi. Anh em không cần sửa dòng code nào nữa đâu nhé!

Chúc anh em Build thuận lợi! 🚀
