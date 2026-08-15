# Patch bảo mật backend license — 07/07/2026

`backend-security-fixes-20260707.patch` chứa ĐÚNG các thay đổi bảo mật đã áp
lên backend license đang chạy trên VPS (`3tserver`), so với bản code thật lúc
đó (không phải bản 516 dòng trên `origin/phase1-backend`).

## Đã DEPLOY LIVE (07/07/2026)
Đã áp thẳng 4 file trên VPS `phase1-backend/server/license-api/app/`, rebuild
container `backend-license-api-1`, verify live: /health 200, admin endpoint
401 khi không auth, token HMAC giả mạo bị chặn, container ổn định.

- `main.py`: rate-limit theo IP (login 5/5phút, activate 10/phút, validate
  60/phút, order 5/5phút) + token phiên admin/staff TTL 8 giờ.
- `services/token_service.py`: từ chối token HMAC khi đã cấu hình Ed25519
  (chống giả mạo — VPS đang bật Ed25519).
- `services/license_service.py`: `validate()` chặn thiết bị đã revoke.
- `services/order_service.py`: thêm `import timedelta` (sửa crash cleanup).

## ⚠️ Nợ kỹ thuật cần xử lý (git hygiene)
Code chạy trên VPS là **working tree chưa commit** (main.py 1285 dòng, khác hẳn
`origin/phase1-backend` 516 dòng). Fix đã "nướng" vào image nên đang chạy,
nhưng CHƯA version-control. Nếu rebuild từ checkout sạch sẽ **mất fix + mất cả
tính năng đang chạy**.

Việc cần làm (team backend): đồng bộ `origin/phase1-backend` về đúng bản đang
chạy trên VPS, RỒI áp patch này (hoặc commit trực tiếp trên VPS — nhưng lưu ý
`admin-config.json` chứa hash mật khẩu admin đang UNTRACKED, tuyệt đối không
commit; cần thêm vào .gitignore).

## Backup / rollback
Bản gốc 4 file ở VPS: `/home/hieupt/backups/license-fix-20260707-141801`.
Rollback: copy đè lại + `cd infra/backend && docker compose up -d --build`.

## Cách áp patch (khi repo chuẩn đã khớp bản 1285 dòng)
```
cd server/license-api/app && git apply /đường-dẫn/backend-security-fixes-20260707.patch
```
