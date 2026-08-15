# Bàn giao — Phase 2 P2P engine + multi-key Ed25519 — 06/08/2026

**Trạng thái:** Cả `phase1-mac` và `piper-vps-sync` đã có đầy đủ, đã merge/hòa giải với công việc thật team Win đang làm song song (gắn menu, QR ảnh). Đã test import + build thật, không lỗi.

---

## 0. CẬP NHẬT 06/08 (cuối ngày) — team Win đã xong "Nhận tài liệu", rà soát chéo với `phase1-mac`

**Việc lớn nhất còn lại ở mục 1.1 bên dưới (nút "Gửi file"/"Nhận file") — phần NHẬN đã xong bên Win.** Đã build + deploy thật bản `1.0.28` lên `reader.3tcomputer.com`, verify qua `curl /api/v1/update/check?platform=win` trả đúng `1.0.28`. **Không đụng gì tới `mac_version`/`mac_url`** trên VPS (vẫn giữ nguyên `1.0.21` như trước).

**Đã có sẵn bên Win, team Mac có thể bỏ qua phần thiết kế UX (đã quyết định, khỏi hỏi lại):**
- File mới: `app/transfer_receive_dialog.py` (`ReceiveDocumentDialog`) — đối xứng với `SendDocumentDialog`, gắn vào menu License cạnh "Chuyển tài liệu..." với tên "Nhận tài liệu...", cùng điều kiện chặn theo key `3TR-E`.
- **Quyết định UX quan trọng:** desktop KHÔNG quét QR bằng camera (không khả thi/không đáng làm cho desktop). Người dùng dán/gõ tay mã phiên (hoặc dán nguyên JSON QR payload `{"v":1,"transfer_session_id":"..."}` - dialog tự parse cả 2 dạng) vào 1 ô `QLineEdit`. Bên gửi (điện thoại ScanDoc) mới là bên hiển thị QR/mã.
- Luồng bên Win (dùng `webrtc_transport.py` tách rời): nhập mã → `client.join_transfer_session(id)` → `SignalingClient(...)` → `webrtc_transport.receive_file(signaling, on_progress=...)` (trả về `(file_name, bytes)`) → `packages.transfer.inbox.StagedReceive` ghi `.part` rồi đổi tên atomic → `client.complete_transfer_session(id, "completed", sha256)` → nút "Mở tài liệu" gọi thẳng `window.open_document(path)`.

**Bên Mac làm sẽ ĐƠN GIẢN HƠN Win** vì `packages/transfer/protocol.py` của Mac đã có sẵn `receive_file_async(transfer_session_id, save_dir, on_progress=, on_status=)` — hàm này tự làm HẾT (join session, signaling, nhận DataChannel, ghi `.part` + atomic rename, verify SHA-256, gọi `complete_transfer_session`) và trả thẳng `{"file_path": ..., "sha256": ...}`. Team Mac chỉ cần:
1. Viết 1 dialog Qt mới (copy phong cách `transfer_send_dialog.py` hiện có, đảo ngược: ô nhập mã thay vì hiện QR) với 1 `QLineEdit` nhận mã/QR-JSON dán tay (parse như mô tả ở trên).
2. Gọi `run_async_in_thread(lambda: receive_file_async(transfer_session_id, save_dir, on_progress=..., on_status=...), on_done, on_error)` — đúng pattern `run_async_in_thread` đã có sẵn cuối `protocol.py`, y hệt cách chắc chắn `send_file_async` đang được gọi trong `transfer_send_dialog.py` hiện tại.
3. Chọn `save_dir` — gợi ý theo đúng convention Win đang dùng (`packages/transfer/inbox.py::inbox_dir()`, đã có sẵn nhánh `darwin`): `~/Library/Application Support/3T Reader/Inbox ScanDoc`. Mac chưa có file `inbox.py` riêng (logic ghi `.part`/rename đã nằm sẵn trong `_receive_file_over_channel` của `protocol.py`) — không cần tạo thêm file, chỉ cần truyền đúng `save_dir`.
4. Gắn menu "Nhận tài liệu..." cạnh "Chuyển tài liệu..." trong `menu_license`, cùng điều kiện `_has_active_enterprise_license()` như bản Win.

**2 điểm lệch phát hiện khi rà soát chéo 2 nhánh (không khẩn, chỉ để 2 team biết):**
- `packages/license_client/token_verifier.py`: nhánh `phase1-mac` (commit `967f41c`) **đã thêm sẵn key Ed25519 mới** vào `_TRUSTED_ED25519_PUBLIC_KEYS_B64` (bước 1 xoay key, VPS chưa ký bằng key này). Nhánh `piper-vps-sync` (Win) **chưa có** — vẫn chỉ 1 key gốc. Không gây lỗi gì hiện tại (VPS chưa dùng key mới), nhưng 2 bên đang lệch danh sách key tin cậy — nên đồng bộ trước khi ai đó thật sự bắt đầu xoay key trên VPS.
- STUN server: Mac dùng 2 server (`stun.l.google.com:19302` + `stun.cloudflare.com:3478`), Win (`webrtc_transport.py`) chỉ dùng 1 (`stun.cloudflare.com:3478`). Không phải bug, nhưng Win có thể cân nhắc thêm Google STUN dự phòng cho tỉ lệ kết nối NAT cao hơn.

---

## 1. Đã có sẵn — chỉ cần `git pull`

### 1.1. Engine truyền file P2P (`packages/transfer/`)

- `protocol.py` — manifest/chunk (64KiB + 4-byte index)/sha256, sanitize tên file
- `inbox.py` — staged write `.part` + atomic rename vào "Inbox ScanDoc"
- `signaling_client.py` — wrap WSS `/signal`
- `webrtc_transport.py` — `aiortc`, non-trickle ICE, flow-control qua `bufferedAmount`

**Test THẬT (không mock):** 2 tiến trình gửi/nhận chạy song song, kết nối qua signaling server thật (`wss://transfer.3tcomputer.com`), mở DataChannel, truyền P2P thật. File 300KB và 5MB đều hash khớp 100%. Test trên macOS — team Win nên tự chạy lại 1 lần trên máy Windows thật để chắc `aiortc` build đúng (thư viện có native deps: `av`, `pylibsrtp`).

**⚠️ Việc còn thiếu:** `TransferPairingDialog` (dialog "Thiết bị ScanDoc") mới có phần **pairing** (thêm/thu hồi thiết bị). **Chưa có nút "Gửi file"/"Nhận file" gọi vào `webrtc_transport.py`** — engine đã chạy được thật nhưng chưa nối vào UI. Đây là việc lớn nhất còn lại của Phase 2.

### 1.2. Multi-key Ed25519 (`packages/license_client/token_verifier.py`)

Đổi `_ED25519_PUBLIC_B64` (1 key hardcode) → `_TRUSTED_ED25519_PUBLIC_KEYS_B64` (list). Verify offline giờ chấp nhận token ký bằng **bất kỳ key nào trong danh sách**, không chỉ 1. **Không đổi hành vi hiện tại** — danh sách hiện chỉ có đúng key gốc đang dùng, token thật verify y hệt trước.

**Lý do:** đây là điều kiện bắt buộc trước khi dám xoay private key trên VPS (key hiện tại từng lộ trên GitHub public, xem đợt vá bảo mật 08/2026). Nếu xoay key khi client chỉ tin 1 key duy nhất, mọi user chưa cập nhật app sẽ bị rơi về "online-only" (mất khả năng dùng offline) và có thể bị khoá hẳn nếu VPS trục trặc đúng lúc đó.

**Quy trình xoay key sau này (CHƯA làm):**
1. Sinh keypair Ed25519 mới trên VPS, **giữ nguyên** key cũ.
2. Thêm public key mới vào `_TRUSTED_ED25519_PUBLIC_KEYS_B64` (cả Win lẫn Mac) — giữ key cũ trong danh sách.
3. Phát hành bản Win + Mac mới có danh sách 2 key.
4. Đợi đa số user cập nhật (theo dõi qua analytics/support nếu có).
5. Chuyển VPS sang ký bằng key mới hoàn toàn.
6. Sau một thời gian đủ dài (gợi ý: vài tháng), xoá key cũ khỏi danh sách + khỏi VPS.

**Không tự ý làm bước nào ở trên khi chưa có quyết định rõ ràng về thời điểm** — đây là thay đổi ảnh hưởng toàn bộ user đang hoạt động.

---

## 2. Backend liên quan (đã xong, không cần làm gì thêm)

- `transfer-gateway` V2 (companion pairing + transfer-sessions + WSS signaling) chạy thật trên VPS, port `8001`, DB/Redis riêng — tất cả bind `127.0.0.1`, chỉ vào qua `https://transfer.3tcomputer.com`.
- **Sự cố đã xử lý (06/08):** VPS reboot ngoài ý muốn khiến `license-api` và `transfer-gateway` down (thiếu `restart policy`) — đã khắc phục + thêm `restart: unless-stopped`, không cần ai làm gì thêm phía client.

---

## 3. Việc tiếp theo (chưa làm, ai rảnh thì nhận)

- [x] ~~Nối nút "Gửi file"~~ — xong cả 2 nền tảng từ trước (`send_file`/`send_file_async` + dialog).
- [x] Nối nút "Nhận file" bên Win (06/08) — xem mục 0. Còn thiếu bên Mac, xem hướng dẫn chi tiết ở mục 0.
- [ ] Nối nút "Nhận file" bên Mac — `receive_file_async()` đã có sẵn trong `protocol.py`, chỉ cần viết dialog UI (xem mục 0, bước 1-4).
- [ ] Đồng bộ danh sách key Ed25519 giữa 2 nhánh (xem mục 0).
- [ ] Test P2P thật qua 2 máy khác nhau, khác mạng (Wi-Fi/4G) — hiện chỉ test loopback cùng máy, chưa biết hành vi NAT thật.
- [ ] STUN riêng (đang dùng public tạm `stun.cloudflare.com`/`stun.l.google.com`).
- [ ] Quyết định thời điểm xoay Ed25519 key (mục 1.2) khi đã sẵn sàng.
