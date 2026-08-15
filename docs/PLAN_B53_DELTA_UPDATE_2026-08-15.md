# B53 — Kế hoạch triển khai Delta Update (VPS + Windows + macOS)

**Ngày viết:** 15/08/2026
**Trạng thái:** Chưa triển khai — tài liệu định hướng để làm, đã đọc source thật
(nhánh `origin/phase1-backend`, `origin/phase1-win` = `piper-vps-sync`,
`origin/phase1-mac`) chứ không suy đoán.

**Nguyên tắc cốt lõi (theo đúng đề xuất của anh):** API mới chạy **song
song**, hoàn toàn tách biệt với API cũ. Không sửa 1 dòng nào trong luồng
`/api/v1/update/check` hiện tại — mọi bản app đang chạy ngoài kia (kể cả bản
1.0.28-1.0.30 lỗi chữ ký cũ) tuyệt đối không bị ảnh hưởng. Chỉ bản app MỚI
(chưa build/release) mới biết gọi API mới; API mới không tồn tại trong nhận
thức của bản cũ.

---

## 0. Vì sao cần tách "Base Package" và "Code Package"

PyInstaller (`3T_Reader.spec`) gom toàn bộ Python thuần (`app/`, `packages/`,
`core/`, `styles/`, và mọi thư viện bên thứ 3 như PySide6/aiortc/AI SDK) vào
1 file `PYZ` archive duy nhất bên trong `_internal/`. Không thể "chỉ ghi đè
vài file .py" như app Python chạy từ source — phải tách kiến trúc build
trước.

```
3T Reader (cài đặt)
├── runtime/   ← Base Package: Qt/PySide6, Python interpreter, Tesseract-OCR,
│                aiortc, piper... — đổi RẤT hiếm (chỉ khi nâng version lớn)
└── app/       ← Code Package: app/, packages/, core/, styles/, assets/ —
                 đổi mỗi lần vá lỗi (như hôm nay: B13/B42/overload fix)
```

**Bản vá lỗi thường (99% trường hợp):** chỉ tải lại Code Package — dự kiến
vài MB thay vì 486MB. **Nâng cấp lớn** (đổi version Qt): vẫn tải Base Package
đầy đủ, hiếm khi xảy ra.

---

## 1. VPS / Backend (`server/license-api/`, nhánh git `phase1-backend`)

Backend THẬT là 1 FastAPI app, đã có sẵn convention versioning
(`settings.api_version = "v1"`, route vừa có bản không-version vừa có bản
`/api/{v}/...`) — tận dụng đúng convention này để thêm `v2` là 1 route+handler
**hoàn toàn mới**, không alias sang v1.

### 1.1. File cần sửa/thêm

| File | Việc làm |
|---|---|
| `app/config.py` | Thêm `api_version_delta: str = "v2"` (không đổi `api_version` hiện có) |
| `app/schemas.py` | Thêm class mới `UpdateCheckV2Response` (KHÔNG sửa `UpdateCheckResponse` cũ) |
| `app/services/update_service.py` | Thêm method mới `build_manifest_v2()` trên `UpdateService` (giữ nguyên `build_manifest()` cũ y hệt) |
| `app/services/admin_config.py` | Mở rộng whitelist `allowed` trong `set_update_config()` + default dict trong `get_update_config()` với các field mới (xem 1.2) — **đây là chỗ dễ quên nhất**: nếu không thêm vào `allowed`, field mới sẽ bị `set_update_config()` âm thầm loại bỏ khi admin panel ghi config |
| `app/main.py` | Thêm route mới `@app.get(f"/api/{settings.api_version_delta}/update/check", ...)` — route cũ (`/api/update/check`, `/api/v1/update/check`) giữ nguyên 100% |

### 1.2. Field config mới (trong `admin-config.json`, key `"update"`)

```python
# admin_config.py::get_update_config() default dict — thêm:
"win_base_version": "base-1.0",
"win_code_url": "",
"win_code_sha256": "",
"mac_base_version": "base-1.0",
"mac_code_url": "",
"mac_code_sha256": "",
"delta_enabled": False,   # công tắc tổng — tắt là v2 luôn trả full-install y hệt v1
```

`delta_enabled=False` mặc định — nghĩa là ngay cả sau khi deploy code này lên
VPS, hành vi v2 vẫn = full-install (an toàn), cho tới khi chủ động bật.

### 1.3. `UpdateCheckV2Response` (schemas.py)

```python
class UpdateCheckV2Response(BaseModel):
    platform: str
    current_version: str
    current_base_version: str = ""   # app gửi lên, để server so khớp
    latest_version: str
    update_type: str                  # "full" | "delta" | "none"
    download_url: str                 # full installer — LUÔN có, dùng làm fallback
    sha256: str = ""
    base_version: str = ""            # base version mà bản vá lỗi này yêu cầu
    code_package_url: str = ""        # rỗng nếu update_type != "delta"
    code_package_sha256: str = ""
    mandatory: bool = False
    release_notes: str = ""
    signature: str = ""               # ký trên (version, download_url, sha256) — full install, GIỐNG HỆT v1
    code_signature: str = ""          # ký RIÊNG trên (base_version, code_package_url, code_package_sha256)
```

Ký 2 chữ ký tách biệt (`signature` cho full install, `code_signature` cho
code package) — không tái dùng 1 chữ ký cho 2 loại payload khác nhau (tránh
đúng lớp lỗi ambiguous-signature).

### 1.4. `update_service.py::build_manifest_v2()`

```python
def build_manifest_v2(self, platform: str, current_version: str, current_base_version: str) -> dict:
    cfg = self.admin_config.get_update_config() if self.admin_config else {}
    is_win = platform.lower() in ("win", "windows")
    prefix = "win" if is_win else "mac"

    latest_version = cfg.get(f"{prefix}_version") or settings.default_update_version
    full_url = cfg.get(f"{prefix}_url") or settings.default_update_url
    full_sha256 = cfg.get(f"{prefix}_sha256", "")
    server_base_version = cfg.get(f"{prefix}_base_version", "base-1.0")
    code_url = cfg.get(f"{prefix}_code_url", "")
    code_sha256 = cfg.get(f"{prefix}_code_sha256", "")
    delta_enabled = bool(cfg.get("delta_enabled", False))

    can_delta = (
        delta_enabled
        and code_url
        and code_sha256
        and current_base_version == server_base_version
        and current_version != latest_version
    )
    update_type = "delta" if can_delta else ("full" if latest_version != current_version else "none")

    manifest = {
        "platform": platform, "current_version": current_version,
        "current_base_version": current_base_version,
        "latest_version": latest_version, "update_type": update_type,
        "download_url": full_url, "sha256": full_sha256,
        "base_version": server_base_version,
        "code_package_url": code_url if update_type == "delta" else "",
        "code_package_sha256": code_sha256 if update_type == "delta" else "",
        "mandatory": bool(cfg.get("mandatory", False)),
        "release_notes": cfg.get("release_notes", ""),
    }
    manifest["signature"] = self._sign_update_manifest(
        version=latest_version, download_url=full_url, sha256=full_sha256,
    )  # tái dùng nguyên hàm ký cũ cho phần full-install — payload giống hệt v1
    manifest["code_signature"] = self._sign_code_package(
        base_version=server_base_version, code_url=manifest["code_package_url"],
        code_sha256=manifest["code_package_sha256"],
    ) if update_type == "delta" else ""
    return manifest
```

`_sign_code_package()` — hàm ký mới, cùng khoá Ed25519 hiện có
(`self.token_service._ed25519_key`), payload JSON canonical riêng
`{"base_version", "code_package_url", "code_package_sha256"}`.

### 1.5. Route mới trong `main.py`

```python
@app.get(f"/api/{settings.api_version_delta}/update/check", response_model=UpdateCheckV2Response)
def update_check_v2(platform: str, current_version: str, current_base_version: str = "base-1.0") -> UpdateCheckV2Response:
    manifest = update_service.build_manifest_v2(platform, current_version, current_base_version)
    return UpdateCheckV2Response(**manifest)
```

Route `/api/update/check` và `/api/v1/update/check` (2 route hiện có) **không
đụng 1 dòng nào**.

### 1.6. Deploy backend an toàn

- Branch `phase1-backend` đã tách riêng khỏi `piper-vps-sync` (Windows) và
  `phase1-mac` — code backend đổi không kéo theo build lại app.
- Deploy: commit trên `phase1-backend`, SSH LAN vào VPS
  (`192.168.1.254:2222`, dùng lại `deploy_lan.py`-style paramiko connect, KHÔNG
  qua cloudflared tunnel — đã xác nhận hay hang), `git pull` trong
  `phase1-backend` checkout trên VPS, `docker compose restart` (đúng lệnh
  `deploy_final.py` đã dùng).
- **Rollback**: vì route mới hoàn toàn tách biệt, rollback = `git revert` +
  restart, hoặc đơn giản hơn là chỉ set `delta_enabled=False` qua admin panel
  (`/api/admin/update-config`) — tắt ngay lập tức không cần deploy lại gì.
- **Trước khi bật `delta_enabled=True` cho thật**: gọi thử
  `curl "https://reader.3tcomputer.com/api/v2/update/check?platform=win&current_version=1.0.31&current_base_version=base-1.0"`
  xác nhận response đúng schema, `update_type` đúng kỳ vọng, chữ ký verify
  được bằng đúng script test đã có (`tests/test_update_client.py` làm mẫu).

---

## 2. Windows client (`packages/updater/update_client.py`, `app/window.py`)

### 2.1. File mới: `packages/updater/base_version.py`

```python
def get_installed_base_version() -> str:
    """Đọc base_version đã cài từ %APPDATA%/3T Reader/base_version.txt.
    Chưa có file (mọi bản cài hiện tại, kể cả 1.0.31 vừa deploy) -> mặc định
    "base-1.0" - khớp đúng server_base_version mặc định ở mục 1.2, để bản
    delta ĐẦU TIÊN vẫn áp dụng được cho user đang chạy 1.0.31 hiện tại."""
    ...

def set_installed_base_version(value: str) -> None:
    """Ghi lại sau khi cài xong (cả full install lẫn code-package patch)."""
    ...
```

### 2.2. Thêm vào `update_client.py` (KHÔNG sửa `check_for_update`/`download_update` hiện có)

- `check_for_update_v2(base_url, current_version, current_base_version, platform="windows") -> UpdateInfoV2`
  — gọi `/api/v2/update/check`, cùng pattern `_get()` đã có.
- `_verify_code_signature(code_signature, payload_bytes) -> bool` — sao y
  `_verify_signature()` hiện có (dùng chung `_EMBEDDED_PUBLIC_KEYS_B64`), chỉ
  đổi payload thành `{base_version, code_package_url, code_package_sha256}`.
- `download_code_package(update_info) -> UpdateResult` — tải
  `code_package_url`, verify SHA-256 + `code_signature`, giải nén vào thư mục
  tạm (KHÔNG ghi đè trực tiếp) trước, chỉ atomic-move đè lên `_internal/app`,
  `_internal/packages`, `_internal/styles` sau khi giải nén + verify checksum
  từng file trong gói THÀNH CÔNG hết. Nếu bất kỳ bước nào lỗi → xoá thư mục
  tạm, trả `UpdateResult(success=False, ...)`, **caller phải tự động fallback
  gọi `download_update()` (full installer) hiện có** — không bao giờ để app
  ở trạng thái nửa vá.

### 2.3. Nơi gọi (trong `app/window.py`, chỗ hiện đang gọi `check_for_update`)

```python
info_v2 = check_for_update_v2(VPS_LICENSE_BASE_URL, APP_VERSION, get_installed_base_version())
if info_v2.available and info_v2.update_type == "delta":
    result = download_code_package(info_v2)
    if result.success:
        set_installed_base_version(info_v2.base_version)
        # apply + restart app
        return
    # rơi xuống full-install như cũ, không báo lỗi riêng cho user - chỉ log
info = check_for_update(VPS_LICENSE_BASE_URL, APP_VERSION, platform="windows")  # luồng CŨ, giữ nguyên
```

Luồng full-install cũ (`check_for_update`/`download_update`) **giữ nguyên
100% dòng code**, chỉ là fallback path — không có rủi ro mới cho phần đã hoạt
động ổn định.

### 2.4. Test bắt buộc trước khi release

- Vá liên tiếp giả lập: cài 1.0.31 → patch code package giả lên 1.0.32 →
  1.0.33 (chỉ bằng code package) → so sánh cây thư mục `_internal/app`,
  `_internal/packages` với 1 bản cài MỚI HOÀN TOÀN 1.0.33 từ installer full —
  phải giống hệt (dùng hash cây thư mục, không so từng file bằng mắt).
  Trường hợp lệch cần chặn ngay: patch bên trong file compiled `.pyd`
  (Nuitka) — khi B52/B13/B2 sensitive modules đổi version, phải đảm bảo code
  package build LUÔN gồm cả `.pyd` mới tương ứng, không patch riêng `.py` mà
  quên `.pyd`.
- Test ngắt mạng/tắt app giữa chừng lúc patch — xác nhận không để lại
  `_internal/app` half-written (dùng thư mục tạm + atomic move như 2.2 đã
  thiết kế).
- Test fallback: giả lập `code_package_sha256` sai trên server → app phải tự
  rơi về full install, không crash, không kẹt.

---

## 3. macOS client (`packages/update_client/`, nhánh `phase1-mac`)

**Việc bắt buộc làm TRƯỚC B53 trên Mac, không phải optional:** updater hiện
tại trên Mac (`packages/update_client/checker.py`) **hoàn toàn không verify
chữ ký** — không có bước nào tương đương `_verify_signature()` của Windows.
Nếu thêm delta-patch (tự động ghi đè code vào app đang chạy) mà không có
bước ký/verify, đây là lỗ hổng RCE thật (ai chiếm được domain/CDN có thể đẩy
code độc hại qua "update"). Áp dụng nguyên `_verify_signature()` +
`_EMBEDDED_PUBLIC_KEYS_B64` từ `packages/updater/update_client.py` (Windows)
sang Mac trước, verify bằng chữ ký + SHA-256 giống Windows y hệt — CHỈ SAU
ĐÓ mới thêm phần v2/delta.

Sau khi có verify chữ ký, các bước còn lại **giống hệt mục 2** (base_version
file tại `~/Library/Application Support/3T Reader/base_version.txt` thay vì
`%APPDATA%`, còn lại đồng nhất logic). `_current_platform()` trong
`checker.py` đã trả `"mac"` sẵn — khớp đúng `prefix = "mac"` ở backend mục
1.4.

---

## 4. Thứ tự triển khai + điểm dừng an toàn

1. **VPS**: thêm route v2 + field config mới, `delta_enabled=False` mặc định
   → deploy → test bằng `curl` tay, KHÔNG ảnh hưởng bản đang chạy. *(rủi ro:
   thấp — chỉ cộng thêm, có thể rollback tức thì bằng 1 flag)*
2. **Mac**: vá lỗ hổng thiếu verify chữ ký trước (độc lập với B53, nên làm dù
   có B53 hay không). *(rủi ro: thấp — chỉ thêm bước từ chối, không đổi hành
   vi khi chữ ký hợp lệ)*
3. **Windows + Mac client**: code check_for_update_v2 + download_code_package
   + fallback, build 1 bản TEST riêng (không phải bản public 1.0.31/1.0.32
   thật) → tự test đầy đủ mục 2.4 trên máy dev.
4. **Chỉ khi bước 3 pass hết**: build code package thật đầu tiên cho 1 bản vá
   lỗi nhỏ thật, bật `delta_enabled=True`, theo dõi qua log/heartbeat 1 thời
   gian ngắn với chính máy dev/test trước.
5. **Cuối cùng**: release bản app mới có sẵn logic v2 cho user thật — lúc
   này mới đúng nghĩa "push thông báo người dùng chuyển qua" như anh đề xuất.
   User đang chạy bản CŨ (chưa có code gọi v2) không bao giờ đụng route mới,
   tự động an toàn.

**Không làm tắt bước nào ở trên** — đặc biệt bước 4 (test riêng biệt trước
khi bật `delta_enabled` thật) là điểm mấu chốt biến "thay đổi kiến trúc rủi
ro cao" thành "rủi ro thấp, có thể tắt bật bằng 1 config flag".
