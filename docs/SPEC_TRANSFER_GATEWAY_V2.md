# Đặc tả kỹ thuật — Transfer-Gateway V2 (Key doanh nghiệp + P2P companion pairing)

**Trạng thái:** Đặc tả để implement. Dựa trên `ENTERPRISE_P2P_TRANSFER_AND_LICENSING_PLAN.md` (định hướng sản phẩm đã chốt), chuyển thành contract chi tiết cho 3 bên: **VPS (transfer-gateway)**, **3TReader (Win/Mac)**, **ScanDoc/ScanDoc Business (iOS, spec-only — chưa có codebase trong phạm vi này)**.
**Thứ tự triển khai bắt buộc:** VPS xong hoàn chỉnh (service, API, test) → mới bắt đầu phần 3TReader UI gọi vào → ScanDoc Business làm sau cùng, riêng đợt bàn giao.
**Ràng buộc bất biến (kế thừa nguyên vẹn từ kế hoạch gốc, mục 15):** không phá `license-api` V1, không ép account, không gửi PDF qua VPS, không raw key làm credential, không TURN/relay ngầm.

---

## 1. Kiến trúc & ranh giới

`transfer-gateway` là **service Python/FastAPI mới, tách hoàn toàn** khỏi `license-api` V1 — không dùng chung process, không dùng chung port, không sửa code V1.

```text
server/
  license-api/        # V1 — KHÔNG ĐỤNG, giữ nguyên container/port 8000 hiện tại
  transfer-gateway/    # V2 — MỚI, container riêng, port riêng (đề xuất 8001, bind 127.0.0.1)
    app/
      main.py
      config.py
      models.py         # SQLAlchemy/Pydantic models cho bảng V2
      schemas.py         # request/response Pydantic
      services/
        pairing_service.py
        device_service.py
        token_service_v2.py   # Ed25519, KHÁC key với V1 hay dùng chung — xem mục 3
        audit_service.py
      db.py              # PostgreSQL connection
      cache.py           # Redis connection (TTL session/pairing code)
```

**Deploy:** `infra/transfer-gateway/docker-compose.yml` riêng, publish `127.0.0.1:8001:8001` (học đúng bài học port 8000 — **không bao giờ publish `0.0.0.0` ra ngoài**, chỉ vào qua Cloudflare Tunnel, thêm route mới trong `cloudflared` config: `transfer.3tcomputer.com → http://localhost:8001`).

**Database:** PostgreSQL riêng cho V2 (container mới, **học đúng bài học Docker-bypass-UFW đã phát hiện ở license-api cũ** — publish `127.0.0.1` only, không `0.0.0.0` như Postgres của dự án khác đang bị lộ trên VPS hiện tại). Redis cho pairing code/session TTL ngắn.

---

## 2. Data model V2 (PostgreSQL)

```sql
CREATE TABLE licenses_v2 (
    license_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_key_hash    TEXT NOT NULL UNIQUE,      -- hash, KHÔNG lưu raw key
    key_type             TEXT NOT NULL,              -- '3TR-E' (enterprise) hiện tại chỉ hỗ trợ loại này ở V2
    desktop_seat_limit   INT NOT NULL DEFAULT 1,
    mobile_companion_per_desktop INT NOT NULL DEFAULT 2,
    mobile_companion_limit       INT NOT NULL,       -- default = desktop_seat_limit * 2
    status               TEXT NOT NULL DEFAULT 'active',  -- active | suspended | expired
    expires_at           TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE devices (
    device_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_id           UUID NOT NULL REFERENCES licenses_v2(license_id),
    device_type           TEXT NOT NULL,             -- 'desktop' | 'iphone' | 'ipad'
    public_key            TEXT NOT NULL,              -- X25519/Ed25519 public key thiết bị, sinh lúc install
    display_name           TEXT,
    parent_desktop_device_id UUID REFERENCES devices(device_id),  -- NULL nếu là desktop
    token_version          INT NOT NULL DEFAULT 2,
    last_seen_at            TIMESTAMPTZ,
    revoked_at              TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pairing_sessions (
    pairing_session_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_hash               TEXT NOT NULL,             -- hash mã 8 ký tự Base32, KHÔNG lưu plaintext
    initiator_device_id      UUID NOT NULL REFERENCES devices(device_id),  -- luôn là desktop
    intended_direction        TEXT NOT NULL,            -- 'add_companion'
    status                    TEXT NOT NULL DEFAULT 'pending',  -- pending | claimed | expired | revoked
    nonce                     TEXT NOT NULL,
    expires_at                 TIMESTAMPTZ NOT NULL,     -- created_at + 120s
    consumed_at                 TIMESTAMPTZ,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transfer_sessions (
    transfer_session_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_device_id          UUID NOT NULL REFERENCES devices(device_id),
    receiver_device_id         UUID REFERENCES devices(device_id),  -- NULL cho tới khi join
    auth_mode                  TEXT NOT NULL,          -- 'business_key' | 'public_premium'
    file_manifest_meta          JSONB,                  -- tên đã sanitize, size, sha256, KHÔNG chứa bytes
    status                      TEXT NOT NULL DEFAULT 'created',  -- created | signaling | completed | failed | expired
    expires_at                   TIMESTAMPTZ NOT NULL,   -- created_at + 5 phút (ticket ngắn hạn)
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE apple_entitlements (
    entitlement_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_transaction_id_hash TEXT NOT NULL UNIQUE,  -- hash, KHÔNG lưu Apple Account
    product_id                   TEXT NOT NULL,
    expires_at                    TIMESTAMPTZ,
    revocation_state               TEXT,
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_events (
    event_id           BIGSERIAL PRIMARY KEY,
    event_type          TEXT NOT NULL,      -- activate|pair|start|complete|fail|revoke
    device_id            UUID,
    correlation_id         TEXT NOT NULL,
    result                  TEXT NOT NULL,   -- ok|error
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Redis keys:**
- `pairing:{pairing_session_id}` → TTL 120s, giá trị = trạng thái claim
- `pairing_attempts:{ip}:{pairing_session_id}` → đếm số lần thử mã, rate-limit
- `transfer_ticket:{transfer_session_id}` → TTL 2-5 phút

---

## 3. Token V2 — quyết định kỹ thuật quan trọng

`token_verifier.py` hiện tại (client Win/Mac, đã xác nhận khớp nhau 2 bên) chỉ đọc format `body.sig.ed.pubkey` (4 phần) và **1 public key hardcode duy nhất**. Không đổi format cũ cho token V1 (`3t-reader-desktop` audience).

**Token V2 dùng schema riêng, KHÔNG tái sử dụng token V1:**

```json
{
  "device_id": "uuid",
  "license_id": "uuid",
  "device_type": "iphone",
  "aud": "transfer-session",
  "scope": ["companion:pair", "transfer:send", "transfer:receive"],
  "issued_at": 1234567890,
  "expires_at": 1234567890,
  "key_id": "v2-2026-08"
}
```

Ký Ed25519 **bằng key riêng cho V2** (KHÔNG dùng chung private key với V1 — tách rủi ro: nếu key V2 có sự cố, V1 không bị ảnh hưởng và ngược lại). Client (3TReader/ScanDoc) verify token V2 bằng **danh sách public key có `key_id`**, không hardcode 1 key duy nhất như V1 — **thiết kế multi-key ngay từ đầu cho V2**, tránh lặp lại vấn đề đang mắc kẹt ở V1 (task #9 hiện tại).

---

## 4. API Contract đầy đủ

Base URL: `https://transfer.3tcomputer.com` (route mới qua Cloudflare Tunnel, cần thêm vào `cloudflared` config).

### 4.1. `POST /api/v2/business/companion-sessions`
3TReader (desktop đã activate key `3TR-E`) tạo pairing session.

**Request** (header `Authorization: Bearer <desktop_token_v2>`):
```json
{}
```
**Response 200:**
```json
{
  "pairing_session_id": "uuid",
  "code": "7M4Q-K9XC",
  "qr_payload": "{\"v\":1,\"pairing_session_id\":\"...\",\"nonce\":\"...\",\"checksum\":\"...\"}",
  "expires_at": "2026-08-05T10:02:00Z"
}
```
**Rate-limit:** 10 lần/5 phút theo `device_id` desktop (không theo IP — desktop cố định).
**Lỗi:** `403` nếu vượt `mobile_companion_limit`; `401` nếu token không hợp lệ.

### 4.2. `POST /api/v2/business/companion-sessions/{id}/claim`
ScanDoc Business quét/nhập mã.

**Request:**
```json
{ "code": "7M4Q-K9XC", "device_public_key": "base64...", "device_type": "iphone", "display_name": "iPhone của Nam" }
```
**Response 200:**
```json
{ "device_token": "...", "parent_desktop_device_id": "uuid", "expires_at": "..." }
```
**Rate-limit:** 5 lần thử mã/session — sau đó khóa session (không phải khóa IP, vì mã đã bị "đốt" là đúng thiết kế single-use).
**Lỗi:** `410 Gone` nếu hết hạn/đã dùng, `429` nếu vượt số lần thử.

### 4.3. `POST /api/v2/transfer-sessions`
Tạo phiên gửi/nhận PDF (bên gửi gọi trước).

**Request:**
```json
{ "auth_mode": "business_key", "direction": "send" }
```
hoặc với Public Premium:
```json
{ "auth_mode": "public_premium", "apple_transaction_jws": "..." }
```
**Response 200:** `{ "transfer_session_id": "uuid", "expires_at": "..." }` (TTL 5 phút)

### 4.4. `POST /api/v2/transfer-sessions/{id}/join`
Đầu nhận xác thực để tham gia session.

### 4.5. `WSS /api/v2/transfer-sessions/{id}/signal`
Chỉ nhận message loại `sdp_offer`, `sdp_answer`, `ice_candidate`, `control`. **Từ chối thẳng bất kỳ payload nào có field chứa file bytes** — validate schema nghiêm ngặt, giới hạn message size (đề xuất 16 KiB/message, đủ cho SDP/ICE, không đủ để nhét file).

### 4.6. `POST /api/v2/transfer-sessions/{id}/complete`
Ghi audit, không nhận hash nội dung ngoài manifest.

### 4.7. `POST /api/v2/apple/entitlements/verify`
Verify JWS qua App Store Server API, cấp `transfer_session` ticket ngắn hạn cho Public Premium.

### 4.8. `POST /api/v2/devices/{id}/revoke`
Thu hồi ngay — mọi `transfer_session`/`pairing_session` liên quan bị đóng trong vòng lặp kiểm tra tiếp theo (KPI kế hoạch: < 30 giây).

---

## 5. Việc cần làm — theo đúng thứ tự bạn chốt

### 5.1. VPS (`transfer-gateway`) — làm trước, làm xong hẳn

- [ ] Tạo `server/transfer-gateway/` theo cấu trúc mục 1
- [ ] PostgreSQL + Redis container mới, **chỉ bind `127.0.0.1`** (bài học từ license-api)
- [ ] Implement đủ 8 endpoint mục 4, có test cho từng cái (đặc biệt: hết hạn mã, sai mã, vượt rate-limit, revoke giữa chừng)
- [ ] Sinh Ed25519 keypair V2 riêng, lưu private key trong `.env` (KHÔNG hardcode — học đúng bài học V1)
- [ ] Thêm route `transfer.3tcomputer.com` vào `cloudflared`, deploy, test qua domain (không publish `0.0.0.0`)
- [ ] Gắn tag/version cho image ngay từ commit đầu tiên (khác V1, V2 sinh ra sau khi đã biết bài học)
- [ ] **Exit gate trước khi sang 5.2:** tạo/claim pairing session bằng `curl` thủ công chạy đúng, revoke chặn được, không có bytes PDF nào chạm gateway

### 5.2. 3TReader (Win/Mac) — chỉ bắt đầu sau khi 5.1 xong hẳn

- [ ] `packages/transfer/` mới (theo đúng kế hoạch gốc mục 7.1): `authorization.py` (token V2 adapter), `signaling_client.py`, `webrtc_transport.py` (`aiortc` worker riêng thread/event loop, không block Qt UI), `protocol.py`, `inbox.py`
- [ ] UI: nút `Thêm thiết bị` trong License dialog cho key `3TR-E`, hiển thị QR/mã, danh sách companion, nút thu hồi
- [ ] **Không đụng `license_client/` V1 hiện có** — package mới hoàn toàn tách biệt, dùng token V2 riêng
- [ ] Test: không phá activate/validate/heartbeat V1 hiện hành (regression bắt buộc)

### 5.3. ScanDoc Business (iOS) — spec-only ở đây, làm sau cùng

Team ScanDoc dùng contract mục 4 để implement `TransferAuthorizationProvider` phía Swift. Cần bàn giao riêng khi 5.1 xong, kèm sandbox test key.

---

## 6. Test matrix bắt buộc trước khi coi 5.1 là "xong hẳn"

| Nhóm | Ca test |
|---|---|
| Pairing | Tạo mã, claim đúng, claim sai 5 lần bị khóa, mã hết hạn 120s, mã dùng lại lần 2 bị từ chối |
| Seat limit | Vượt `mobile_companion_limit` bị chặn đúng thông báo |
| Revoke | Revoke device → pairing/transfer session liên quan đóng trong <30s |
| Bảo mật | Raw key không xuất hiện trong QR/log/response; token V2 audience mismatch bị chặn; WSS signaling từ chối payload vượt size limit |
| Hạ tầng | Port 8001 không lộ `0.0.0.0`; Postgres/Redis mới không lộ ra ngoài (test bằng `curl` từ máy khác như đã làm với license-api) |
| Regression | `license-api` V1 hoạt động y hệt trước, không downtime |

---

## 7. Việc KHÔNG làm ở giai đoạn này

- Không cài TURN/relay.
- Không sửa bất kỳ file nào trong `server/license-api/` hiện có.
- Không đổi `_ED25519_PUBLIC_B64` trong `token_verifier.py` V1 — token V2 dùng cơ chế multi-key riêng, độc lập hoàn toàn.
- Không tạo `packages/transfer/` cho tới khi 5.1 có exit gate pass.
