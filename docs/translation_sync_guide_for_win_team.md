# TÀI LIỆU ĐỒNG BỘ TÍNH NĂNG DỊCH THUẬT (DÀNH CHO TEAM WINDOWS)

Tài liệu này mô tả chi tiết toàn bộ các tính năng Dịch Thuật (Translate) vừa được hoàn thiện trên bản Mac tối nay. Team Windows cần bám sát tài liệu này để check chéo, bổ sung code và đảm bảo luồng kiến trúc (đặc biệt là VPS) của 2 nền tảng hoàn toàn đồng nhất.

---

## 1. TỔNG QUAN TÍNH NĂNG MỚI (CẦN CHECK & BỔ SUNG)

### 1.1. Tự động nhận diện ngôn ngữ (Auto-detect)
- **Tính năng:** Khi người dùng chọn ngôn ngữ nguồn là "🔍 Tự động nhận diện", hệ thống sẽ đọc 500 ký tự đầu tiên để đoán xem đó là tiếng gì, sau đó tự động thiết lập ngôn ngữ nguồn cho engine dịch.
- **Chi tiết UI:** Trả về kết quả dưới dạng thẻ xanh "✅ Ngôn ngữ phát hiện: English" trên thanh trạng thái và góc giao diện.

### 1.2. Giao diện 3 Tab Độc Lập
Đã thiết kế lại giao diện hộp thoại dịch thuật (`app/ai_translate_dialog.py`) chia làm 3 tab riêng biệt để tránh rối mắt:
1. **✏️ Đoạn văn bản:** Cho phép copy/paste text tự do.
2. **📄 Trang hiện tại:** Tự động trích xuất text của 1 trang PDF hiện tại bằng `pdfplumber` và dịch.
3. **📚 Toàn tài liệu:** Cho phép dịch hàng loạt từ Trang A -> Trang B (hoặc tất cả), có thanh Progress Bar hiển thị % tiến độ, và cho phép xuất toàn bộ bản dịch ra file `.txt`.

### 1.3. Cấu trúc 1 Nút Bấm Chức Năng
- Thay vì để nhiều nút "Dịch bằng AI", "Dịch bằng Google" gây rối, giao diện chỉ có **1 nút DUY NHẤT** (VD: "🚀 Dịch toàn tài liệu").
- Nút này sẽ đọc cấu hình từ thẻ Combo Box (Engine) ở trên cùng của cửa sổ để quyết định dùng thuật toán nào.

---

## 2. KIẾN TRÚC 3 ENGINE DỊCH THUẬT & ĐỊNH HƯỚNG VPS

Đây là phần quan trọng nhất để 2 team không bị lệch định hướng kinh doanh. Team Windows cần đảm bảo logic code có đủ 3 nhánh này:

### Nhánh 1: 🤖 Dịch bằng AI (Gemini/OpenAI/Claude)
- **Cách hoạt động:** Gửi API theo cấu hình AI của phần mềm.
- **Mục đích:** Dịch chuẩn xác nhất, giữ nguyên ngữ cảnh. Hỗ trợ cho tài khoản trả phí hoặc khách hàng có API Key.

### Nhánh 2: 🌐 Google Translate (Miễn phí)
- **Cách hoạt động:** Gọi API ngầm (unofficial API qua `client=gtx`) bằng thư viện `urllib.request`. 
- **Ưu điểm:** Tốc độ bàn thờ, hoàn toàn miễn phí, KHÔNG CẦN API KEY. Do phần mềm chạy dạng Desktop App trên IP của khách hàng nên cực kỳ an toàn, không sợ Google chặn rate limit như làm Web.
- **Mục đích:** Tính năng cơ bản cho bản Free.

### Nhánh 3: 💾 Từ điển Offline (Tải từ VPS)
- **Định hướng chiến lược chung:** Đây là tính năng dành cho tệp doanh nghiệp muốn bảo mật tuyệt đối, không gửi dữ liệu ra ngoài Internet.
- **Cách hoạt động hiện tại (Team Windows cần clone theo):**
  - Tự động tạo thư mục `offline_dicts` trong thư mục App Data.
  - Khi chưa có mạng VPS, phần mềm tự tạo file mô phỏng `en_vi.json` chứa 10 từ vựng cơ bản.
  - Thuật toán đọc file JSON đó và quét hàm `Regex` thay thế từ vựng Word-by-word (tra từ điển cục bộ). 
  - Kết quả trả về phải được dán nhãn `[Chế độ Offline Từ Điển]` ở đầu để User biết là nó đang chạy ngầm cục bộ.
- **Tương lai (Cả 2 team sẽ làm sau):** Sẽ viết API gọi VPS để tải bộ Database SQLite (50.000 từ) hoặc model Argos Translate (1GB) về bỏ vào thư mục `offline_dicts` này.

---

## 3. THƯ VIỆN BỔ SUNG & KỸ THUẬT (DEPENDENCIES)

Team Windows check file `requirements.txt` và đảm bảo:

1. **`pdfplumber`**: Thư viện bắt buộc để trích xuất text từ PDF (dành cho Tab 2 và Tab 3).
2. **Luồng xử lý (Threading)**: Mọi tác vụ gọi API dịch thuật và trích xuất PDF **BẮT BUỘC** phải được ném vào `QThread` chạy ngầm. **TUYỆT ĐỐI KHÔNG** dùng hàm lambda chạy ngược từ Background Thread để chèn chữ (`setPlainText`) lên UI, sẽ gây sập app (Segmentation fault). Hãy dùng cơ chế `Signal -> Slot (QueuedConnection)` để truyền dữ liệu từ ngầm lên UI chính.
3. **Thư viện Google Translate**: Không cài thêm thư viện bên ngoài. Đã dùng thuật toán HTTP Get qua `urllib.request` tích hợp sẵn của Python để giữ ứng dụng nhẹ nhất có thể.

---
**Yêu cầu:** Team Windows đọc kỹ file `packages/ai/translate.py` và `app/ai_translate_dialog.py` trên nhánh git mới nhất để copy & đồng bộ UI và luồng xử lý.
