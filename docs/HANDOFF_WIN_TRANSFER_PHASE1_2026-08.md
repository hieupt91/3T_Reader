# Bàn giao team Win — Companion Device Pairing (Phase 1 P2P) — 08/2026

**Trạng thái:** Backend + code client đã có sẵn trên nhánh `piper-vps-sync` (commit `4658a41`), **đã test API thật OK**, nhưng **chưa gắn vào UI chính** — người dùng chưa bấm vào được trong app thật.
**Tài liệu gốc:** `docs/SPEC_TRANSFER_GATEWAY_V2.md` (đặc tả đầy đủ API/data model), `docs/HANDOFF_VPS_SECURITY_2026-08.md` (đợt vá bảo mật VPS trước đó).

---

## Đã có sẵn, chỉ cần `git pull`

- **Backend `transfer-gateway` V2** chạy thật trên VPS (`https://transfer.3tcomputer.com`), tách biệt hoàn toàn `license-api` V1, đã test: tạo mã ghép nối, claim đúng/sai, chặn dùng lại mã, chặn vượt giới hạn companion, thu hồi thiết bị — tất cả đều đúng qua test thật (curl + qua chính class Python).
- **`packages/transfer/`** (`authorization.py`) — client gọi 3 API: tạo phiên ghép nối, list thiết bị, thu hồi thiết bị. Tái dùng token V1 đã activate qua `VpsLicenseClient.get_cached_credentials()` (method mới thêm, không đổi hành vi V1 cũ).
- **`app/transfer_pairing_dialog.py`** — `TransferPairingDialog`, dialog hoàn chỉnh: nút "Thêm thiết bị" → hiện mã 8 ký tự + đếm ngược 120s, danh sách thiết bị companion kèm nút "Thu hồi".
- **`app/config.py`** — thêm `TRANSFER_GATEWAY_BASE_URL = "https://transfer.3tcomputer.com"`.
- Đã test import + construct dialog thật qua PySide6 (không lỗi), test gọi cả 3 API qua SSH tunnel tới VPS — hoạt động đúng.

## Việc CẦN LÀM ở team Win

1. **Gắn `TransferPairingDialog` vào UI chính** (`window.py` hoặc License dialog) — chỉ hiện nút này khi license đang active là key `3TR-E` (kiểm tra `plan_code` bắt đầu bằng `3TR-E`, xem cách `license_dialog.py` đang check `"3TR-E"` để tái dùng logic tương tự). Đây là việc duy nhất còn thiếu để tính năng dùng được thật — bên Mac cũng đang thiếu y hệt, chưa ai làm.
2. **Test thật trên máy Windows** — tôi mới test trên macOS (`build_venv` + PySide6). Cần xác nhận: dialog hiện đúng, `credential_manager` (thay Keychain) trả đúng `get_cached_credentials()`, mạng/firewall Windows không chặn gọi `https://transfer.3tcomputer.com`.
3. **Quyết định có làm QR ảnh không** — hiện tại chỉ hiện mã chữ (`YTSG-WCTG`), chưa render QR hình ảnh (cần thêm dependency `qrcode`, chưa quyết định). Mã chữ vẫn dùng được đầy đủ, QR chỉ là tiện ích thêm.

## KHÔNG làm ở giai đoạn này

- Chưa đụng `packages/transfer/protocol.py`, `webrtc_transport.py`, `inbox.py` — đó là Phase 2 (truyền PDF qua WebRTC), backend cũng chưa có endpoint `transfer-sessions`.
- Không tự sửa `token_verifier.py` V1 hay đổi Ed25519 key — không liên quan tính năng này.
- Không cần sửa gì ở `license-api` V1 — `transfer-gateway` hoàn toàn tách biệt.

## Checklist xác nhận

- [ ] `git pull origin piper-vps-sync` lấy commit `4658a41`
- [ ] Gắn dialog vào UI, chỉ hiện với key `3TR-E`
- [ ] Test trên Windows thật: mở dialog, tạo mã, list thiết bị (không cần iPhone thật để test list rỗng)
- [ ] Báo lại nếu `get_cached_credentials()` không hoạt động đúng trên Windows (Credential Manager)
