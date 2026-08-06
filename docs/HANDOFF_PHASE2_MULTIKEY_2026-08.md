# Bàn giao — Phase 2 P2P engine + multi-key Ed25519 — 06/08/2026

**Trạng thái:** Cả `phase1-mac` và `piper-vps-sync` đã có đầy đủ, đã merge/hòa giải với công việc thật team Win đang làm song song (gắn menu, QR ảnh). Đã test import + build thật, không lỗi.

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

- [ ] Nối nút "Gửi file"/"Nhận file" trong `TransferPairingDialog` (hoặc dialog mới) gọi `webrtc_transport.send_file`/`receive_file` — đây là việc lớn nhất còn lại.
- [ ] Test P2P thật qua 2 máy khác nhau, khác mạng (Wi-Fi/4G) — hiện chỉ test loopback cùng máy, chưa biết hành vi NAT thật.
- [ ] STUN riêng (đang dùng public tạm `stun.cloudflare.com`).
- [ ] Quyết định thời điểm xoay Ed25519 key (mục 1.2) khi đã sẵn sàng.
