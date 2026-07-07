# Bàn giao team Mac — Đợt vá bảo mật 07/2026 (dùng chung VPS)

**Người thực hiện (Win):** phiên fix bảo mật 07/07/2026
**Branch Win:** `piper-vps-sync` · **Branch Backend:** `fix-vps-security` (off `phase1-backend`, CHƯA push)
**Branch Mac cần cập nhật:** `phase1-mac`

> Mục đích: các fix dưới đây làm trên nhánh Win + backend dùng chung. Vì Mac và Win nói chuyện với **cùng một VPS**, có phần Mac **tự động chịu tác động** (backend), có phần Mac **phải tự port** (client). Tài liệu này liệt kê chi tiết để Mac fix cho khớp hệ thống.

---

## PHẦN A — Backend VPS (ẢNH HƯỞNG CLIENT MAC NGAY KHI DEPLOY)

Backend là dùng chung (1 VPS, branch `phase1-backend`). Khi deploy `fix-vps-security`, **client Mac tự động chịu tác động, KHÔNG cần đổi code Mac**. Mac cần **biết** để không hiểu nhầm là app lỗi:

| Thay đổi backend | Tác động lên client Mac |
|---|---|
| `validate()` nay chặn `revoked_devices` | Thiết bị Mac **đã bị admin revoke** trước đây vẫn chạy (do lỗ hổng cũ) → sau deploy sẽ **bị chặn thật** ở lần validate online kế tiếp. Rà danh sách device đã revoke trước khi deploy. |
| Rate-limit theo IP: activate 10/phút, validate 60/phút, login 5/5phút | Client Mac không được gọi validate/activate dồn dập. Nhiều máy Mac sau cùng 1 IP NAT khởi động đồng loạt về lý thuyết có thể chạm ngưỡng (hiếm). |
| `token_service.verify()` từ chối token HMAC khi đã có khóa Ed25519 | Nếu VPS bật Ed25519 mà còn token HMAC cũ (2 phần) → token đó vô hiệu, máy Mac giữ nó phải **kích hoạt lại**. Token Ed25519 (4 phần) không ảnh hưởng. |
| Token phiên admin/staff có TTL 8 giờ | Người dùng Admin Panel (nếu team Mac có dùng) phải đăng nhập lại sau 8 giờ. |
| `/api/admin/licenses` và `/api/admin/devices` nay yêu cầu auth | Nếu có tool/script Mac nào gọi 2 endpoint này **không kèm Bearer token** → sẽ nhận 401. Phải thêm token admin. |

### Việc BẮT BUỘC trên VPS (ai giữ VPS làm, báo cả 2 team)
- `THREET_LICENSE_ED25519_PRIVATE`: **phải set** (khóa riêng Ed25519). Nếu chưa set, server ký HMAC → client (cả Mac lẫn Win chỉ nhận Ed25519) hỏng offline.
- `THREET_LICENSE_SIGNING_SECRET`: **đổi** khỏi mặc định `dev-secret-change-me`.
- `THREET_ADMIN_PASSWORD`: đảm bảo đã đổi khỏi mặc định `3tAdmin2026`.

---

## PHẦN B — Fix CLIENT phải PORT sang `phase1-mac`

⚠️ File client Win và Mac đã diverge. Sau khi rà `phase1-mac` (07/07/2026), trạng thái thực tế:

| Mục | Trạng thái trên Mac | Hành động |
|---|---|---|
| **B1 bypass license** | 🔴 CÒN LỖI | ✅ **ĐÃ PORT + push branch `fix-mac-license-bypass`** — chỉ cần review + merge |
| B2 export os.system | ✅ Mac đã an toàn sẵn (`subprocess.Popen(["open"])`) | Không cần làm |
| B4 race QEventLoop (sign.py) | Không có pattern `_run_signing_task` — luồng ký Mac viết khác | Mac tự review luồng ký của mình |
| B5 cảnh báo RSA yếu (shared.py) | Không có `rsa_key_size_threshold=0` — code validate Mac khác | Mac tự review |
| B6 threading update-check (window.py) | Không có pattern lambda đó | Mac tự review |
| B7 race ghi PDF (annotate.py) | Không có `_PDF_SAVE_LOCK`; `pages.py` không tồn tại trên Mac | Mac tự review luồng lưu/rotate |
| B8 dọn code chết (webchannel.py) | `webchannel.py` không tồn tại trên Mac | Không áp dụng |

**Tóm lại: chỉ B1 là bug logic dùng chung thật (đã port). B2–B8 là đặc thù Win — Mac review code tương ứng của mình, tham khảo mô tả dưới.**

Mô tả từng fix (để Mac đối chiếu code của mình):

### B1. 🔴 CRITICAL — Bypass license offline (BẮT BUỘC port)
**File:** `packages/license_client/vps_client.py`
**Lỗi:** Khi token không phải Ed25519 (hoặc chữ ký hỏng), code rơi vào `_offline_status(cache)` **đọc thẳng `plan_code`/`expires_at` từ file cache JSON không ký** → sửa tay file cache là active vĩnh viễn, hoàn toàn offline.

**Sửa như bản Win:**
- `_offline_status()` **không được cấp `active=True` từ cache**. Đổi thành luôn trả `active=False` với thông báo "cần kết nối internet để xác thực".
- `validate_cached()`: nhánh token không-Ed25519 phải **gọi `_validate_server()` đồng bộ** rồi `except → _offline_status`, thay vì trả cache ngay.

```python
# validate_cached(), thay khối "token cũ trả cache ngay":
try:
    return self._validate_server(token, cache)
except Exception:
    return self._offline_status(cache)

# _offline_status(): bỏ toàn bộ logic đọc cache, thay bằng:
def _offline_status(self, cache: dict) -> LicenseStatus:
    del cache
    return LicenseStatus(
        active=False,
        message="Khong the xac thuc license. Vui long ket noi internet de xac thuc lai.",
    )
```
**Hệ quả cần biết:** sau fix này, client (Mac) với token **không-Ed25519** sẽ thành **online-only** (không dùng offline được). Token Ed25519 bình thường **KHÔNG bị ảnh hưởng** (vẫn verify offline qua `_verify_offline`). Vì hệ thống cấp Ed25519, người dùng thật không mất offline.

### B2. Command injection cục bộ khi mở file sau export (đúng đường code Mac)
**File:** `app/actions/export.py` → `_open_after_export()`
**Sửa:** nhánh `darwin` bỏ `os.system(f'open "{path}"')` (chèn lệnh nếu tên file chứa `` ` ``/`$()`), dùng:
```python
import subprocess
if sys.platform == "darwin":
    subprocess.run(["open", output_path], check=False)
```

### B3. Ký số — PIN không ghi ra đĩa (nếu bản Mac có luồng USB token)
**File:** `packages/signing/usb_worker.py` + `app/actions/sign.py`
> Lưu ý: `usb_worker.py` **hiện không có trên `phase1-mac`**. Nếu Mac không dùng USB PKCS#11 thì bỏ qua B3. Nếu có (hoặc sắp có), áp:
- `usb_worker.main()`: khi `args[0] == "-"` → đọc payload từ `sys.stdin.buffer.read().decode("utf-8")` thay vì mở file.
- 2 caller trong `sign.py` (`_run_usb_signing_subprocess`, `_run_usb_signing_batch_subprocess`): bỏ `tempfile`, truyền `cmd=[..., "-"]` + `subprocess.run(..., input=payload_json, encoding="utf-8")`. PIN không còn nằm trên đĩa.

### B4. Ký số — race QEventLoop treo UI (nếu bản Mac dùng `_run_signing_task`)
**File:** `app/actions/sign.py`
**Lỗi:** closure `_finish_success/_finish_error` nối vào signal worker chạy trên background thread; nếu worker xong trước `loop.exec()` → quit bị bỏ qua → **treo UI**.
**Sửa:** thay bằng QObject relay có affinity main-thread (`_SigningLoopRelay` với `@pyqtSlot`), nối `worker.succeeded.connect(relay.on_success)` để Qt tự queue về main thread. (Xem commit Win `c4d30a8` để lấy nguyên class.)

### B5. Cảnh báo chữ ký khóa yếu
**File:** `packages/signing/shared.py`
**Sửa:** khi `policy_warning` (RSA < 2048) và `overall_ok`, đưa cảnh báo lên `overall_status` (thay vì để hiện "hợp lệ" trơn). Không lật `valid`/`ok`.

### B6. Threading update-check (tránh gọi GUI sai luồng)
**File:** `app/window.py`
**Sửa:** signal `error`/`finished` của update-check **không nối bằng lambda** (chạy nhầm background thread → `QMessageBox` sai luồng, crash). Nối vào bound-method (`_on_update_check_error_signal`, `_cleanup_update_check_worker`) + lưu `self._update_check_show_errors`.

### B7. Race ghi đè PDF nhiều luồng
**File:** `app/actions/annotate.py`, `app/actions/pages.py`
**Sửa:** bọc phần mở/save/replace PDF trong `_AnnotationOpQueue.flush()` và trong rotate nhiều trang (`pages.py`) bằng `_PDF_SAVE_LOCK` chung — tránh luồng lưu chú thích và luồng rotate cùng ghi đè 1 file → hỏng file.

### B8. Dọn code chết (không bắt buộc, nên đồng bộ)
- `app/webchannel.py`: xóa bridge mồ côi `editExistingTextBridge`/`_ExistingTextBridgeProxy` (không caller/JS).
- `app/actions/sign.py`: xóa `_LegacySignatureStatusDialog`, `_format_signature_report`/`_show_signature_report` (bản cũ, không caller).

---

## PHẦN C — Hợp đồng phải KHỚP giữa Mac và Win (dùng chung VPS)

1. **Public key Ed25519 hardcode** ở `packages/license_client/token_verifier.py` (`_ED25519_PUBLIC_B64`). ✅ **Đã kiểm 07/07/2026: Mac và Win KHỚP** (`y0jZ/wQHoQ+VvAQjYuhlmf0R63cMLgkTHp1wzXrcM08=`). Giữ nguyên; nếu sau này đổi keypair phải đổi đồng bộ cả 2 bên + khóa riêng trên VPS.
2. **Định dạng token:** client chỉ chấp nhận Ed25519 4 phần (`body.sig.ed.pubkey`). Sau khi backend siết HMAC, thống nhất mọi client dùng Ed25519.
3. **Hệ quả online-only** (mục B1): nếu port fix bypass, cả Mac và Win đều thành online-only với token không-Ed25519 — đảm bảo VPS đang cấp Ed25519 trước khi ship để không ai mất offline.

---

## PHẦN D — Phối hợp

- **Purge lịch sử `cccd_temp.pdf`:** file PII này ở commit `6dec164` (tổ tiên chung, đã lên remote). Nếu purge history + force-push nhánh dùng chung → **clone team Mac sẽ vỡ**. Phải hẹn lịch, cùng re-clone. Chưa thực hiện.
- **Deploy backend:** branch `fix-vps-security` (ahead 1 của `phase1-backend`) **chưa push**. Push = VPS pull + docker rebuild = deploy prod cho cả Mac lẫn Win. Thống nhất thời điểm + set env (Phần A) trước.

---

## PHẦN E — Checklist Mac sau khi port

- [ ] Port B1 (bypass license) + tự test: sửa tay file cache + để offline → app phải báo chưa hợp lệ (không còn active).
- [ ] Port B2 (export open) + test xuất file trên macOS.
- [ ] Port B4/B6/B7 nếu bản Mac có các luồng tương ứng; test ký PFX, kiểm tra cập nhật, xoay+chú thích liên tục.
- [x] `_ED25519_PUBLIC_B64` Mac == Win — đã xác nhận khớp 07/07/2026 (Phần C.1).
- [ ] Sau khi backend deploy: test 1 máy Mac đã-revoke → phải bị chặn; test kích hoạt/validate bình thường vẫn chạy.
