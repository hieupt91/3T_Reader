# Hướng dẫn kỹ thuật — License Client (VPS Backend)

> Dành cho: Đội phát triển Windows & macOS  
> Branch: `phase1-backend` (Windows) · `phase1-mac` (macOS)  
> Cập nhật: 2026-05-21

---

## 1. Tổng quan

Desktop app (Win/Mac) kết nối trực tiếp với VPS backend qua HTTPS để xác thực license.

```
[Desktop App]
     │
     │  HTTPS
     ▼
[Cloudflare Tunnel]
     │
     ▼
[VPS: license.3tcomputer.com → localhost:8000]
     │
     ▼
[Docker: backend-license-api-1  (FastAPI + uvicorn)]
```

**Endpoint gốc:** `https://license.3tcomputer.com`

---

## 2. Cấu hình

File: `app/config.py`

```python
VPS_LICENSE_BASE_URL = "https://license.3tcomputer.com"

# Để tắt license (chạy thử không cần VPS):
# VPS_LICENSE_BASE_URL = ""
```

---

## 3. Sử dụng trong code

```python
from packages.license_client import get_license_client

client = get_license_client()
```

`get_license_client()` tự động trả về `VpsLicenseClient` khi `VPS_LICENSE_BASE_URL` có giá trị, hoặc `NotConfiguredLicenseClient` (bypass, luôn active) khi để trống.

### 3.1 Kích hoạt license

```python
from packages.license_client.fingerprint import get_device_fingerprint

fp = get_device_fingerprint()   # ID ổn định của máy (32 hex)

try:
    result = client.activate(
        license_key="THREET-XXXX-XXXX",
        email="khachhang@email.com",   # lưu trữ nội bộ, không gửi lên server
        device_fingerprint=fp,
    )
    print(f"Kích hoạt OK — token: {result.signed_token[:20]}...")
    print(f"Hết hạn: {result.status.expires_at}")
except RuntimeError as e:
    print(f"Lỗi: {e}")   # "Seat limit reached", "Unknown license key", v.v.
```

### 3.2 Kiểm tra license khi khởi động app

```python
status = client.validate_cached()

if not status.active:
    # Hiện dialog yêu cầu nhập license key
    show_license_dialog()
else:
    print(f"License hợp lệ — plan: {status.plan_code}")
    print(f"Hết hạn: {status.expires_at}")
```

### 3.3 Heartbeat định kỳ (mỗi 24h)

```python
import threading, time

def _heartbeat_loop(client):
    while True:
        time.sleep(86400)   # 24 giờ
        status = client.heartbeat()
        if not status.active:
            # Thông báo license hết hạn / bị thu hồi
            notify_license_expired()

threading.Thread(target=_heartbeat_loop, args=(client,), daemon=True).start()
```

### 3.4 Hủy kích hoạt

```python
client.deactivate()   # Gọi API + xóa cache local
```

---

## 4. Offline Grace Period

Khi **VPS không reach được** (mất mạng, server bảo trì), app vẫn hoạt động trong **grace period 3 ngày** kể từ ngày hết hạn token.

| Tình huống | Kết quả |
|---|---|
| VPS online, token còn hạn | `active=True` |
| VPS offline, còn trong grace period | `active=True`, message "Offline — sẽ xác thực lại khi có kết nối" |
| VPS offline, đã qua grace period | `active=False`, message "License hết grace period" |
| Chưa từng kích hoạt | `active=False`, message "Chưa kích hoạt license" |

---

## 5. Cấu trúc file

```
packages/license_client/
├── __init__.py          # get_license_client() — lazy init
├── client.py            # LicenseClient protocol + NotConfiguredLicenseClient
├── models.py            # LicenseStatus, ActivationResult dataclass
├── fingerprint.py       # get_device_fingerprint() — MAC+hostname+OS hash
└── vps_client.py        # VpsLicenseClient — gọi VPS thật
```

---

## 6. API Backend — Endpoints

Base URL: `https://license.3tcomputer.com`

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/health` | Kiểm tra server còn sống |
| POST | `/api/v1/license/activate` | Kích hoạt license trên thiết bị |
| POST | `/api/v1/license/validate` | Validate token đã lưu |
| POST | `/api/v1/license/heartbeat` | Heartbeat định kỳ |
| POST | `/api/v1/license/deactivate` | Hủy kích hoạt thiết bị |
| GET | `/api/v1/update/check` | Kiểm tra phiên bản mới |

### 6.1 Backend contract snapshot 2026-05-28

Current backend deployment note for Win/Mac:

- Backend branch: `phase1-backend`
- Current hardening commit: `ccbe90c` (`hardening license backend deployment`)
- Desktop app contract does not need to change for this backend update.
- Treat the returned `token` as an opaque string. Store/cache it as-is and do not parse internal fields in the app.
- Keep `device_id` stable per machine across `activate`, `validate`, `heartbeat`, and `deactivate`.
- Offline grace still follows `expires_at + grace_days`.
- Update checks remain `GET /api/v1/update/check?platform=mac|win&current_version=...`.
- Release file naming should follow:
  - `3TReader-<version>-mac.dmg`
  - `3TReader-<version>-win.exe`
- Language packs are separate static files:
  - `GET /downloads/language/vi.json`
  - `GET /downloads/language/en.json`
  - app will fallback to built-in labels if the pack is missing
- Do not commit `.env`; keep secrets in the VPS runtime file and share only `.env.example` in the repo.

### Request / Response mẫu

**Activate:**
```bash
curl -X POST https://license.3tcomputer.com/api/v1/license/activate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "THREET-DEMO-ENTERPRISE",
    "device_id": "abc123def456",
    "platform": "windows",
    "app_version": "1.0.2",
    "machine_name": "DESKTOP-ABC"
  }'
```

```json
{
  "status": "ok",
  "message": "Activated.",
  "license_key": "THREET-DEMO-ENTERPRISE",
  "device_id": "abc123def456",
  "token": "eyJ...",
  "expires_at": "2026-05-24T00:00:00+00:00",
  "grace_days": 3,
  "seat_limit": 10
}
```

---

## 7. License Keys Demo (để test)

| Key | Loại | Số máy tối đa |
|---|---|---|
| `THREET-DEMO-0001` | Demo | 2 |
| `THREET-DEMO-ENTERPRISE` | Enterprise Demo | 10 |

> **Lưu ý:** Đây là key demo để test. Key thật sẽ được cấp riêng theo hợp đồng.

---

## 8. Cache local

Token sau khi activate được lưu tại:

| Hệ điều hành | Đường dẫn |
|---|---|
| Windows | `%APPDATA%\3T Reader\license_cache.json` |
| macOS | `~/Library/Application Support/3T Reader/license_cache.json` |
| Linux | `~/.local/share/3T Reader/license_cache.json` |

File này chứa token, device_id, expires_at, grace_days. **Không nên chỉnh tay.**

---

## 9. Test nhanh

```bash
# Kiểm tra server
curl https://license.3tcomputer.com/health

# Chạy test suite
python tests/test_inline_editor_win.py   # Windows
python tests/test_smoke_macos.py         # macOS
```

---

## 10. Lưu ý khi phát triển

- **Tắt license khi debug:** Set `VPS_LICENSE_BASE_URL = ""` trong `app/config.py`
- **Không commit license_cache.json** — đã có trong `.gitignore`
- **Timeout mặc định:** 8 giây. Nếu VPS chậm → tự động fallback offline
- **Seat limit:** Mỗi license key có giới hạn số máy. Nếu đầy → báo lỗi "Seat limit reached"

---

*Cập nhật: 2026-05-21 | Branch: phase1-backend / phase1-mac*
