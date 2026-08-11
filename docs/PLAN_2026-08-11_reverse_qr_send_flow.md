# Kế hoạch: Đảo chiều luồng gửi tài liệu — 3TReader hiện QR, ScanDoc quét để gửi

Trạng thái: **chưa triển khai** — tài liệu lập kế hoạch, viết trước khi code để
thống nhất phạm vi trước khi đụng vào giao thức P2P đang chạy ổn định.

## 0. Nguyên tắc chung (đã chốt với người dùng 11/08/2026)

> **Bên NHẬN luôn là bên tạo phiên** (hiện mã/QR) — bên GỬI luôn là bên kết
> nối tới phiên đó. Áp dụng đối xứng cho cả 2 chiều (máy tính nhận → máy
> tính tạo phiên; điện thoại nhận → điện thoại tạo phiên).

**Ràng buộc quan trọng khi áp dụng nguyên tắc này**: 3TReader desktop đã có
quyết định thiết kế từ trước là **không quét camera** (`transfer_receive_dialog.py`
dòng 6: "desktop không quét camera - quyết định UX đã chốt"), chỉ dán mã tay.
Vì vậy 2 chiều KHÔNG đối xứng hoàn toàn về mặt UI:

| Chiều | Bên nhận (tạo phiên) | Bên gửi (kết nối tới) | Cách bên gửi lấy mã |
|---|---|---|---|
| ScanDoc → 3TReader | 3TReader | ScanDoc | ScanDoc **quét QR bằng camera** (3TReader hiện QR) |
| 3TReader → ScanDoc | ScanDoc | 3TReader | 3TReader **dán mã tay** (ScanDoc hiện mã, không cần quét vì desktop không có luồng scan) |

Chiều 2 (3TReader → ScanDoc) hiện **chưa tồn tại bên ScanDoc** (chỉ desktop
có `transfer_send_dialog.py` tạo phiên sẵn, nhưng ScanDoc không có màn "Nhận
từ 3TReader" nào để join+nhận) — đây là tính năng MỚI hoàn toàn, không phải
chỉ đảo vai, xem mục 7.

## 1. Vấn đề hiện tại

Luồng gửi tài liệu hôm nay (`SendToDesktopView.swift` bên ScanDoc +
`transfer_receive_dialog.py` bên 3TReader):

```
ScanDoc bấm "Bắt đầu gửi"
    → tạo transfer_session (server)
    → hiện mã ra màn hình ScanDoc
    → người dùng ĐỌC/GÕ TAY mã đó sang 3TReader
    → 3TReader dán mã → tham gia phiên → nhận file
```

Yêu cầu mới: đảo lại, giống hệt trải nghiệm ghép nối thiết bị lúc kích hoạt
key (desktop hiện QR, ScanDoc quét bằng camera) — áp dụng cho MỖI LẦN gửi
file, không cần gõ tay:

```
3TReader mở "Nhận tài liệu" → tự tạo phiên, hiện QR ngay
    → ScanDoc quét QR bằng camera
    → Server xác thực mã → mở kết nối P2P
    → ScanDoc gửi file → 3TReader nhận
```

## 2. Vì sao không đơn giản chỉ "đổi UI"

Đọc kỹ `packages/transfer/protocol.py` (dùng chung Win/Mac) phát hiện: hiện
tại 3 vai trò đang bị **gộp cứng** vào đúng 2 hàm:

| | `send_file_async()` (hiện = ScanDoc) | `receive_file_async()` (hiện = 3TReader) |
|---|---|---|
| Ai tạo `transfer_session` | ✅ luôn hàm này | ❌ (chỉ join) |
| Vai WebRTC | luôn **offerer** (tạo DataChannel + SDP offer, tự retry gửi offer tới khi có answer trong 180s) | luôn **answerer** (đợi offer, trả answer) |
| Chiều file bytes | luôn **đẩy** file đi | luôn **nhận** file về |

Muốn đảo (3TReader tạo phiên + hiện QR, nhưng **vẫn nhận** bytes; ScanDoc
quét QR + join, nhưng **vẫn gửi** bytes) nghĩa là phải **tách rời 3 cột trên**
— không thể chỉ đổi thứ tự gọi hàm có sẵn.

## 3. Tin tốt: Backend REST đã sẵn sàng, không cần đổi

Đã đọc `app/main.py` + `app/services/transfer_session_service.py`:

- `POST /api/v2/transfer-sessions` (tạo phiên) dùng `any_device_auth` — desktop
  hay companion gọi đều được, không ép buộc ai là "sender".
- `POST /api/v2/transfer-sessions/{id}/join` chỉ kiểm tra hạn + cùng
  `license_id`, không giả định vai trò byte nào.
- `complete_transfer_session` chấp nhận bất kỳ bên nào trong phiên báo hoàn tất.

→ **Phase VPS/backend trong kế hoạch này gần như là bước xác nhận, không phải
code mới** (trừ khi phát sinh nhu cầu ở bước test tích hợp).

## 4. Thứ tự triển khai theo phase

### Phase 0 — Chuẩn bị (không rủi ro)
- [ ] Thêm dependency `qrcode` (Python) vào `requirements.txt` / môi trường
      build Win+Mac (3TReader dùng chung 1 codebase Python cho cả 2 hệ điều
      hành — làm 1 lần, áp dụng cả 2).
- [ ] Xác nhận `transfer_pairing_dialog.py` đang tạo QR bằng thư viện gì
      (đã thấy có `import qrcode` ở đó) — tái dùng đúng cách vẽ QR đã có,
      không tạo cách mới.

### Phase 1 — Desktop: tách vai trò trong `protocol.py` (Win + Mac, dùng chung)
File: `packages/transfer/protocol.py`.

- [ ] Viết hàm mới `host_receive_file_async(save_dir, *, on_progress, on_status)`:
      - Gọi `create_transfer_session` (giữ nguyên field `sender_device_id` ở
        DB dù giờ bên này sẽ NHẬN bytes — chỉ là tên field lịch sử, không ảnh
        hưởng logic).
      - Trả về `qr_payload` ngay (giống `send_file_async` đang làm ở dòng tạo
        session) để UI hiện QR.
      - Đóng vai **answerer**: đợi `sdp_offer` (đợi lâu hơn `receive_file_async`
        hiện tại vì giờ phải đợi người dùng cầm điện thoại lên MỞ app + quét —
        đề xuất timeout ~180s thay vì 60s hiện tại của `receive_file_async`).
      - Nhận bytes qua `_receive_file_over_channel` (tái dùng y nguyên).
- [ ] Viết hàm mới `guest_send_file_async(transfer_session_id, file_path, *, on_progress, on_status, credentials)`:
      - Gọi `join_transfer_session(transfer_session_id, credentials=...)`
        (tái dùng nguyên `join_transfer_session` đã có).
      - Đóng vai **offerer**: tạo DataChannel, SDP offer, **giữ nguyên logic
        retry-gửi-offer-mỗi-3s-tới-180s** đã tinh chỉnh kỹ trong
        `send_file_async` (đừng viết lại từ đầu — copy nguyên đoạn 279-296).
      - Gửi bytes qua `_send_file_over_channel` (tái dùng y nguyên).
      - **Lưu ý quan trọng**: hàm này hiện chỉ cần dùng ở phía Python cho mục
        đích test giả lập (script E2E) — vai "guest gửi" thật trên điện thoại
        nằm ở Swift (Phase 3), KHÔNG phải Python. Vẫn nên viết hàm Python này
        để có script test tự động 2-tiến-trình xác minh giao thức đảo vai
        đúng TRƯỚC khi đụng vào UI thật.
- [ ] Viết 1 script test thủ công (2 process Python trên cùng máy, 1 giả lập
      "host" 1 giả lập "guest") xác nhận file truyền đúng trước khi làm UI.

### Phase 2 — Desktop UI: `transfer_receive_dialog.py` (Win + Mac)
- [ ] Bỏ toàn bộ UI "dán mã" (`_code_input`, `_on_start_clicked` đọc từ
      textbox) — thay bằng: mở dialog là **tự động** gọi
      `host_receive_file_async` ngay, hiện QR to giữa dialog (canh giữa,
      tái dùng cách vẽ QR của `transfer_pairing_dialog.py`).
- [ ] Hiện trạng thái rõ ràng: "Đang chờ ScanDoc quét mã..." → "Đã kết nối -
      đang nhận..." → popup hoàn tất (đã có sẵn từ bản vá trước, giữ nguyên).
- [ ] Nút "Tạo mã mới" (phòng khi QR hết hạn/lỗi) — gọi lại
      `host_receive_file_async` từ đầu.
- [ ] **Quyết định UX cần chốt với người dùng trước khi code**: có giữ lại
      đường "dán mã thủ công" làm phương án dự phòng không (vd máy tính
      không có gì để hiện QR to, hoặc muốn gõ tay vì lý do khác)? Đề xuất:
      giữ 1 nút nhỏ "Nhập mã thủ công" ẩn phía dưới, không xoá hẳn code cũ.

### Phase 3 — iOS: ScanDoc App Business
Files: `Shared/Transfer/{SendToDesktopView,WebRTCSendService,TransferGatewayClient}.swift`.

- [ ] `TransferGatewayClient.swift`: thêm hàm
      `joinTransferSession(transferSessionID:deviceToken:) async throws` gọi
      `POST /api/v2/transfer-sessions/{id}/join` (endpoint đã có sẵn ở
      backend, chỉ thiếu client Swift).
- [ ] `WebRTCSendService.swift`: thêm hàm mới (không sửa `send()` hiện tại,
      giữ nguyên cho tương thích ngược nếu Phase 2 giữ đường dán mã thủ công)
      — vd `sendAfterScanningQR(transferSessionID:fileData:fileName:deviceToken:onStatus:onProgress:)`:
      - Gọi `joinTransferSession` thay vì `createTransferSession`.
      - Phần còn lại (tạo peer connection, DataChannel, SDP offer + retry,
        gửi bytes) **giữ nguyên y hệt** logic hiện có trong `send()` — vì vai
        offerer/pusher không đổi, chỉ đổi bước lấy `transfer_session_id` từ
        đâu ra (quét QR thay vì tự tạo).
- [ ] `SendToDesktopView.swift`: đổi luồng UI —
      - Bước 1: bấm "Gửi tài liệu" → mở scanner (tái dùng
        `PairingQRScannerView` đã có, parse `transfer_session_id` từ QR
        payload `{"v":1,"transfer_session_id":"..."}` — đã có sẵn hàm parse
        tương tự cho pairing, viết hàm parse riêng cho transfer QR theo
        đúng format Python `qr_payload` sinh ra ở Phase 1).
      - Bước 2: quét xong → gọi `sendAfterScanningQR(...)` → hiện progress
        như UI hiện tại.
      - Bỏ Picker chọn TTL trước khi gửi (không còn ý nghĩa vì giờ desktop
        là bên tạo phiên/quyết định TTL, không phải ScanDoc) — **cần xác
        nhận lại với người dùng**: TTL cho luồng mới nên cấu hình ở đâu (màn
        hình 3TReader "Nhận tài liệu", không phải ScanDoc)?

### Phase 4 — Backend (VPS) — bước xác nhận, không phải code mới
- [ ] Chạy lại toàn bộ luồng thật trên VPS staging/test key, xác nhận không
      endpoint nào cần sửa (theo phân tích ở mục 3).
- [ ] Nếu Phase 1-3 phát sinh nhu cầu thật (vd cần timeout join dài hơn cho
      vai host-chờ-quét, hiện `pairing_code_ttl_seconds`/`transfer_ticket_ttl_seconds`
      có thể cần tách riêng 1 giá trị TTL mới cho "phiên chờ quét" khác với
      TTL phiên gửi hiện tại) — bổ sung tại bước này, không đoán trước.

### Phase 5 — Test tích hợp + rollout
- [ ] Test thật 2 thiết bị (1 điện thoại thật + 1 Mac/Win thật), không phải
      simulator (WebRTC/camera cần thiết bị thật).
- [ ] Test các ca lỗi: QR hết hạn giữa chừng, mất mạng lúc đang gửi, quét
      nhầm QR ghép nối thiết bị (không phải QR gửi file) — 3TReader
      `_parse_transfer_session_id` đã có logic từ chối JSON sai loại, cần
      viết tương tự cho luồng mới.
- [ ] Cập nhật `docs/UPDATE_2026-08-10_transfer_fixes.md` hoặc tạo bản ghi
      mới khi hoàn tất, để đồng bộ thông tin cho team Win/Mac/VPS như các
      đợt trước.

## 5. Rủi ro chính cần lưu ý khi code

1. **Timing đảo ngược lại có lợi**: hiện tại bên answerer (nhận) luôn kết nối
   WS trễ hơn bên offerer (gửi) vì cần thao tác người dùng — đây là lý do
   `send_file_async` phải retry gửi offer mỗi 3s. Ở luồng MỚI, bên answerer
   (desktop, giờ đổi vai) sẽ kết nối WS **sớm hơn** (mở dialog là tạo phiên
   ngay), còn bên offerer (điện thoại, sau khi quét) mới là bên chậm hơn —
   nghĩa là logic retry-offer vẫn cần giữ nguyên bên phía **điện thoại** (nay
   là offerer), không phải bỏ đi.
2. **Không xoá code cũ vội** — nên giữ `send_file_async`/`receive_file_async`
   nguyên vẹn (dùng cho đường dán-mã-thủ-công nếu Phase 2 quyết định giữ lại
   làm dự phòng), chỉ THÊM hàm mới, tránh phải sửa lại 2 luồng cùng lúc nếu
   có vấn đề.
3. **`sender_device_id`/`receiver_device_id` ở DB sẽ mang ý nghĩa ngược với
   tên gọi** trong luồng mới (desktop = "sender" theo DB dù nó nhận bytes).
   Không đổi tên cột (tốn công, rủi ro migration) — chỉ cần comment rõ trong
   code để người đọc sau không nhầm.

## 7. Chiều thứ 2: 3TReader → ScanDoc (ScanDoc là bên NHẬN, tự tạo phiên)

Áp dụng đúng nguyên tắc mục 0: ScanDoc (bên nhận) tạo phiên + hiện mã;
3TReader (bên gửi) dán mã tay để join. Đây là **tính năng mới** vì ScanDoc
hiện chưa có màn "Nhận từ 3TReader" nào, và desktop's `transfer_send_dialog.py`
hiện đang làm NGƯỢC nguyên tắc (tự tạo phiên thay vì join) nên cũng phải sửa.

### Phase 6 — iOS: màn "Nhận từ 3TReader" (mới hoàn toàn)
- [ ] View mới `ReceiveFromDesktopView.swift` (đối xứng `SendToDesktopView.swift`):
      mở màn là gọi `createTransferSession` ngay (ScanDoc = bên tạo phiên),
      hiện mã to (text, không nhất thiết QR vì desktop không quét - xem bảng
      mục 0), trạng thái "Đang chờ 3TReader kết nối...".
- [ ] `WebRTCSendService.swift` cần thêm hàm đối xứng đóng vai **answerer +
      nhận bytes** (hiện file này chỉ có vai gửi) — hoặc tạo file mới
      `WebRTCReceiveService.swift` cho rõ ràng, tránh nhồi 2 vai trái ngược
      vào 1 class. Cần: đợi `sdp_offer` qua WSS, trả `sdp_answer`, nhận
      DataChannel, ghi file nhận được vào thư mục tài liệu ScanDoc (tương tự
      `_receive_file_over_channel` bên Python, viết lại bằng Swift/CryptoKit
      cho SHA-256 verify).
- [ ] Sau khi nhận xong: tự động thêm file vào thư viện tài liệu (`DocumentStore`)
      giống luồng "Quét mới" hiện có - cần xác nhận với người dùng có muốn
      tự động OCR file nhận về không, hay chỉ lưu PDF thô.

### Phase 7 — Desktop: sửa `transfer_send_dialog.py` (Win + Mac)
- [ ] Đổi từ "tự tạo phiên + hiện QR" (`send_file_async`, sai nguyên tắc)
      sang "dán mã do ScanDoc hiện ra" (`guest_send_file_async` viết ở
      Phase 1, đóng vai offerer + đẩy bytes - giữ nguyên, chỉ đổi input mã
      từ tự sinh sang người dùng dán vào).
- [ ] UI: thêm lại ô dán mã (giống `transfer_receive_dialog.py` cũ trước khi
      sửa ở Phase 2) - lưu ý 2 dialog `transfer_send_dialog.py` (giờ dán mã)
      và `transfer_receive_dialog.py` (giờ hiện QR) sẽ có UI **ngược nhau**
      so với tên gọi hiện tại ("Chuyển tài liệu" = dán mã để chuyển ĐI,
      "Nhận tài liệu" = hiện QR để người khác gửi ĐẾN) - cần soát lại text
      hướng dẫn trong cả 2 dialog cho khỏi gây nhầm lẫn với người dùng cuối.

## 8. Việc cần người dùng xác nhận trước khi bắt tay code

- [x] ~~Có cần làm song song cho cả luồng NHẬN từ 3TReader gửi SANG ScanDoc
      không~~ → **Đã chốt 11/08/2026: có, áp dụng nguyên tắc "bên nhận tạo
      phiên" đối xứng cho cả 2 chiều** (xem mục 0, 7).
- [ ] Giữ hay bỏ đường "dán mã thủ công" làm phương án dự phòng cho chiều
      ScanDoc→3TReader? (mục Phase 2) - lưu ý chiều 3TReader→ScanDoc BẮT
      BUỘC phải có dán mã tay (desktop không quét), không phải tuỳ chọn.
- [ ] TTL cho phiên "chờ kết nối" (cả 2 chiều) nên cấu hình ở đâu, mặc định
      bao lâu? (mục Phase 3, Phase 4)
- [ ] File nhận về từ 3TReader (Phase 6) có cần tự OCR ngay không, hay chỉ
      lưu PDF thô vào thư viện?
- [ ] Thứ tự ưu tiên: làm xong trọn vẹn chiều ScanDoc→3TReader (Phase 0-5)
      rồi mới sang chiều 3TReader→ScanDoc (Phase 6-7), hay làm song song?
      → **Đã chốt 11/08/2026: làm SONG SONG cả 2 chiều**, không làm tuần tự
      như đề xuất ban đầu. Phase 1 (tách vai trò trong `protocol.py`) vẫn là
      nền tảng chung, làm trước - nhưng Phase 2+3 (chiều 1) và Phase 6+7
      (chiều 2) có thể triển khai đồng thời vì không phụ thuộc nhau (file
      Swift/Python khác nhau, không đụng chung code).

## 9. VPS có cần sửa gì thêm không? (đã xác nhận: KHÔNG)

Đã rà soát lại kỹ lần 2 (tính cả việc giờ làm song song 2 chiều, không chỉ
1 chiều như phân tích ban đầu ở mục 3):

- `create_transfer_session`/`join_transfer_session` không kiểm tra
  `device_type` của người gọi — desktop hay companion tạo phiên/join đều
  chạy đúng 1 code path như nhau. Cả 2 chiều dùng chung 2 endpoint này.
- Server không đọc/hiểu nội dung SDP (`signaling_relay.relay()` chỉ forward
  JSON thô) — không có khái niệm "offerer"/"answerer" ở tầng backend, nên
  đảo vai trò ở client không đụng gì tới server.
- Rate limit tạo phiên hiện tại `rate_dep("transfer_create", 20, 60)` (20
  lần/phút) - đủ rộng rãi cho cả 2 chiều dùng song song, kể cả lúc test.
- TTL mặc định 1h (`transfer_ticket_ttl_seconds`, đã tăng từ đợt trước) đủ
  dài cho việc "bên nhận mở màn hình chờ" ở cả 2 chiều, không cần giá trị
  riêng.

**Kết luận: VPS không cần deploy gì thêm cho toàn bộ tính năng này** (cả 2
chiều) - trừ khi trong lúc code Phase 1-3/6-7 phát sinh nhu cầu thật không
lường trước được từ đầu.
