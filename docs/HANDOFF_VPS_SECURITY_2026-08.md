# Bàn giao — Đợt vá bảo mật VPS 08/2026 (dùng chung, Win + Mac)

**Người thực hiện:** phiên làm việc 04/08/2026 (Claude Sonnet 5, cùng chủ repo)
**Phạm vi:** Chỉ VPS backend + tooling deploy. **Không sửa dòng code nào trong app 3TReader (Win/Mac)** — cả hai team **không cần port gì cả**, chỉ cần biết để không hiểu nhầm là app lỗi.

---

## Tóm tắt 1 dòng

Vá xong 4 lỗ hổng hạ tầng + đồng bộ đúng code license-api đang chạy thật về Git. Contract API (`/api/v1/license/*`) **không đổi gì** — Win/Mac tiếp tục hoạt động y hệt trước.

---

## PHẦN A — Đã làm trên `phase1-backend` (VPS, dùng chung)

| Việc | Commit | Ảnh hưởng client |
|---|---|---|
| Gỡ secret hardcode (Ed25519 key, admin password, SMTP password) khỏi `infra/backend/docker-compose.yml` — private key này từng lộ trên GitHub public | `c0a070c` | Không |
| Bind port 8000 license-api về `127.0.0.1`, chỉ vào được qua Cloudflare Tunnel — trước đó publish `0.0.0.0` khiến kẻ tấn công gọi thẳng IP:8000 giả mạo header `CF-Connecting-IP` để né rate-limit | `cd1b59a` | Không — Win/Mac luôn gọi qua domain `reader.3tcomputer.com`/`license.3tcomputer.com`, không gọi IP trực tiếp |
| Hòa giải nhánh với `origin/phase1-backend` (`ccbe90c`) | `9594f0f` | Không |
| **Đồng bộ toàn bộ `server/license-api/app/` đúng bản đang chạy thật trên VPS về Git** (nợ từ đợt vá 07/07/2026, đã phình tới 1631 dòng chưa version-control) | `c9d75ef` | Không — chỉ là đưa code đã chạy sẵn vào Git, không đổi hành vi |
| Thêm rate-limit cho `/api/license/heartbeat` (60/60s) và `/api/license/deactivate` (20/60s) — 2 endpoint trước đây không giới hạn | *(patch trực tiếp trên VPS, đã gộp vào `c9d75ef`)* | Không — client bình thường gọi vài lần/phút, không chạm ngưỡng |
| Đổi `THREET_ADMIN_PASSWORD` (biến môi trường fallback) khỏi giá trị mặc định `3tAdmin2026` | *(chỉ trên `.env` VPS, không commit)* | Không — mật khẩu đăng nhập admin panel thật (`admin-config.json`) không đổi |

**Đã test đầy đủ trước/sau mỗi bước:** domain qua Cloudflare vẫn `200`, IP:8000 trực tiếp bị chặn, 16 service khác trên VPS (không liên quan 3T Reader) không đổi trạng thái, `heartbeat`/`deactivate` xác nhận trả `429` đúng ngưỡng bằng test thật.

## PHẦN B — Đã làm trên `piper-vps-sync` (Win)

| Việc | Commit | Ảnh hưởng client |
|---|---|---|
| Bỏ `paramiko.AutoAddPolicy()` (tự tin host key, không cảnh báo MITM) trong 13 script deploy (`sftp_deploy.py`, `check_vps.py`, `deploy_final.py`, `direct_deploy.py`, `direct_deploy2.py`, `patch_vps.py`, `patch_data.py`, `patch_data_sudo.py`, `update_vps_config.py`, `upload_test.py`, `deploy_test.py`, `check_vps_local.py`, `scripts/fix_vps_reader_cache.py`), đổi sang `load_system_host_keys()` + `RejectPolicy()` | `87090a2` | Không — đây là tool dev dùng để deploy, không nằm trong app đã build/phát hành |

`phase1-mac` **không có commit nào** từ đợt này — các file trên (script deploy) chỉ tồn tại ở `piper-vps-sync`, không có ở `phase1-mac`.

---

## PHẦN C — Còn treo, CẦN chú ý khi làm tiếp

### C.1. Xoay Ed25519 key — chưa làm, sẽ cần port cả Win + Mac khi làm

Private key Ed25519 ký license **vẫn đang lộ trên GitHub public**, chưa xoay được ngay vì `packages/license_client/token_verifier.py` (cả Win lẫn Mac, đã xác nhận khớp nhau) chỉ tin **1 public key hardcode duy nhất** — xoay ẩu sẽ phá offline license của user đang cài bản cũ.

**Thứ tự bắt buộc khi làm:** thêm hỗ trợ multi-key/`key_id` vào `token_verifier.py` (cả 2 nền tảng) → phát hành bản Win + Mac mới → đợi đa số user cập nhật → mới rotate key trên VPS. **Sẽ có bàn giao riêng khi bắt đầu phần này** — lúc đó Win/Mac mới thực sự cần port code.

### C.2. SMTP App Password — chưa xoay, chờ chủ tài khoản

App Password Gmail (`3t.hotro@gmail.com`) dùng gửi email đơn hàng/key cũng đang lộ trên GitHub. Không ảnh hưởng app 3TReader (SMTP chỉ backend dùng), nhưng vì Gmail này còn là **email khôi phục cho tài khoản khác** (GitHub, VPS...) nên rủi ro dây chuyền nếu bị khai thác. Đang chờ chủ tài khoản đăng nhập Google để tạo App Password mới + thu hồi cái cũ.

### C.3. PII trong lịch sử Git — chưa purge, cần hẹn lịch

`cccd_temp.pdf` (ảnh CCCD) từng bị commit, đã gỡ tracking (`2761362`) nhưng vẫn còn nguyên trong blob lịch sử ở commit `6dec164` trên repo **public**. Purge triệt để cần `git filter-repo` + force-push — **sẽ làm vỡ mọi clone hiện có của team Win/Mac**, bắt buộc hẹn lịch để cùng re-clone sau khi làm. **Chưa thực hiện**, sẽ báo trước khi làm.

### C.4. Ngoài phạm vi 3T Reader — không đụng vào

VPS còn chạy nhiều service khác không thuộc 3T Reader (Postgres, camera-service, admin webapp của dự án khác) đang lộ port công khai do lỗi Docker-bypass-UFW. **Không sửa** trong đợt này vì thuộc hệ thống khác, cần xác nhận riêng trước khi đụng vào.

---

## PHẦN D — Checklist xác nhận cho Win/Mac

- [ ] Đọc qua để biết — **không cần port code gì**.
- [ ] Nếu thấy `heartbeat`/`deactivate` trả `429` bất thường khi test dồn dập (>60 lần/phút hoặc >20 lần/phút) — đây là rate-limit mới, không phải bug.
- [ ] Khi bắt đầu làm task multi-key Ed25519 (mục C.1) — chờ bàn giao riêng, đừng tự ý đổi `_ED25519_PUBLIC_B64` một phía.
- [ ] Trước khi bất kỳ ai chạy `git filter-repo`/force-push cho mục C.3 — dừng lại, hẹn lịch trước, đừng tự làm.
