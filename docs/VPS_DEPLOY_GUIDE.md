# Hướng dẫn triển khai VPS — 3T Reader License & Update API

> Domain mục tiêu: `reader.3tcomputer.com`  
> Stack: FastAPI + uvicorn + Nginx + Let's Encrypt  
> OS khuyến nghị: Ubuntu 22.04 LTS  

---

## 1. Yêu cầu VPS

| Thông số | Tối thiểu | Khuyến nghị |
|---|---|---|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 512 MB | 1 GB |
| Disk | 10 GB | 20 GB |
| OS | Ubuntu 22.04 | Ubuntu 22.04 |
| Cổng mở | 80, 443, 22 | 80, 443, 22 |

---

## 2. Cài đặt môi trường

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài Python 3.11, pip, nginx, certbot
sudo apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx git

# Tạo user riêng chạy service (không dùng root)
sudo useradd -m -s /bin/bash threet
sudo mkdir -p /opt/threet /data
sudo chown threet:threet /opt/threet /data
```

---

## 3. Deploy code server

```bash
# Chuyển sang user threet
sudo -u threet -i

# Clone hoặc copy code server vào /opt/threet
cd /opt/threet
git clone <repo_url> .           # hoặc scp/rsync thư mục server/license-api

# Tạo virtualenv và cài dependencies
python3.11 -m venv venv
source venv/bin/activate
pip install -r server/license-api/requirements.txt
```

---

## 4. Biến môi trường (bắt buộc)

Tạo file `/opt/threet/.env`:

```dotenv
# ── Môi trường ──────────────────────────────────────────────────
THREET_ENV=production

# ── Bảo mật — THAY ĐỔI ngay, KHÔNG để mặc định ────────────────
THREET_LICENSE_SIGNING_SECRET=<chuỗi ngẫu nhiên 64 ký tự>
THREET_ADMIN_PASSWORD=<mật_khẩu_admin_mạnh>

# ── Thư mục dữ liệu (license state, orders, staff) ──────────────
THREET_DATA_DIR=/data
THREET_STATE_FILE=license-api-state.json

# ── Cấu hình license ────────────────────────────────────────────
THREET_GRACE_DAYS=7
THREET_LICENSE_DURATION_DAYS=365

# ── Thông tin bản cập nhật MỚI NHẤT (cập nhật khi phát hành) ───
THREET_DEFAULT_UPDATE_VERSION=1.0.0
THREET_DEFAULT_UPDATE_URL=https://reader.3tcomputer.com/downloads/3TReader-1.0.0-mac.dmg
```

> **Tạo signing secret ngẫu nhiên:**
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## 5. Systemd service

Tạo `/etc/systemd/system/threet-api.service`:

```ini
[Unit]
Description=3T Reader License & Update API
After=network.target

[Service]
Type=simple
User=threet
WorkingDirectory=/opt/threet/server/license-api
EnvironmentFile=/opt/threet/.env
ExecStart=/opt/threet/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable threet-api
sudo systemctl start threet-api
sudo systemctl status threet-api   # kiểm tra running
```

---

## 6. Nginx + SSL

### 6.1. Cấu hình Nginx

Tạo `/etc/nginx/sites-available/threet`:

```nginx
server {
    listen 80;
    server_name reader.3tcomputer.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name reader.3tcomputer.com;

    # SSL — certbot sẽ tự điền sau
    ssl_certificate     /etc/letsencrypt/live/reader.3tcomputer.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/reader.3tcomputer.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Thư mục chứa file DMG / EXE để tải về
    location /downloads/ {
        root /data;
        autoindex off;
        add_header Content-Disposition "attachment";
    }

    # API proxy
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/threet /etc/nginx/sites-enabled/
sudo nginx -t
```

### 6.2. Cấp SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d reader.3tcomputer.com
# Nhập email, đồng ý điều khoản → certbot tự cấu hình Nginx
sudo systemctl reload nginx
```

---

## 7. Phát hành bản cập nhật mới

Khi có build mới (ví dụ `1.2.0`), làm theo 3 bước:

### Bước 1 — Upload file DMG/EXE lên VPS

```bash
# Tạo thư mục downloads nếu chưa có
sudo mkdir -p /data/downloads
sudo chown threet:threet /data/downloads

# Upload từ máy dev
scp 3TReader-1.2.0-mac.dmg user@reader.3tcomputer.com:/data/downloads/
scp 3TReader-1.2.0-win.exe user@reader.3tcomputer.com:/data/downloads/
```

### Bước 2 — Cập nhật biến môi trường

Sửa `/opt/threet/.env`:

```dotenv
THREET_DEFAULT_UPDATE_VERSION=1.2.0
THREET_DEFAULT_UPDATE_URL=https://reader.3tcomputer.com/downloads/3TReader-1.2.0-mac.dmg
```

> **Lưu ý:** Hiện tại server trả cùng 1 URL cho cả mac và win.  
> Nếu cần tách: sửa `update_service.py` để đọc URL theo `platform`.

### Bước 3 — Restart service

```bash
sudo systemctl restart threet-api
```

Ngay lập tức, khi app 3T Reader < 1.2.0 khởi động sau 15 giây, nó sẽ hỏi người dùng muốn cập nhật không.

---

## 8. Kiểm tra endpoint cập nhật

```bash
# Kiểm tra từ máy local
curl "https://reader.3tcomputer.com/api/v1/update/check?platform=mac&current_version=1.0.0"

# Kết quả mong đợi (khi có bản mới 1.2.0):
{
  "platform": "mac",
  "current_version": "1.0.0",
  "latest_version": "1.2.0",
  "download_url": "https://reader.3tcomputer.com/downloads/3TReader-1.2.0-mac.dmg",
  "sha256": "",
  "mandatory": false,
  "release_notes": ""
}

# Kiểm tra khi đã dùng bản mới nhất:
curl "https://reader.3tcomputer.com/api/v1/update/check?platform=mac&current_version=1.2.0"
# → latest_version == current_version → app hiểu là "đã mới nhất"
```

---

## 8.1. Publish thư viện giọng Piper cho client Win/Mac

Client `Đọc sách` đang lấy danh sách giọng từ `app/actions/piper_tts_manager.py`.

### URL client sẽ thử

Theo thứ tự:

- `https://reader.3tcomputer.com/downloads/piper/index.json`
- `https://reader.3tcomputer.com/piper/index.json`
- `https://reader.3tcomputer.com/downloads/voices/index.json`
- `https://reader.3tcomputer.com/voices/index.json`
- `https://reader.3tcomputer.com/index.json`

Khuyến nghị chuẩn hóa và chỉ dùng:

- `https://reader.3tcomputer.com/downloads/piper/index.json`

### Cấu trúc public trên VPS

Đặt file tại:

```text
/home/hieupt/projects/3T_Reader/phase1-backend/downloads/piper/
  index.json
  vi_VN-vais1000-medium.onnx
  vi_VN-vais1000-medium.onnx.json
  en_US-ryan-medium.onnx
  en_US-ryan-medium.onnx.json
```

### Format `index.json`

Client đang expect một mảng JSON:

```json
[
  {
    "id": "vi_VN-vais1000-medium",
    "name": "Vietnamese - VAI-S1000 Medium",
    "language": "vi",
    "size": "60.3 MB",
    "onnx_url": "./vi_VN-vais1000-medium.onnx",
    "json_url": "./vi_VN-vais1000-medium.onnx.json"
  },
  {
    "id": "en_US-ryan-medium",
    "name": "English (US) - Ryan Medium",
    "language": "en",
    "size": "60.3 MB",
    "onnx_url": "./en_US-ryan-medium.onnx",
    "json_url": "./en_US-ryan-medium.onnx.json"
  }
]
```

Ghi chú:

- `onnx_url` và `json_url` có thể là relative path. Client sẽ tự resolve theo URL thật của `index.json`.
- `id` sẽ được dùng làm tên file local ở client.

### Client tải file về đâu

Windows:

```text
%APPDATA%\3T_Reader\voices\
```

macOS:

```text
~/Library/Application Support/3T_Reader/voices/
```

### Win/Mac dùng chung cái gì

Dùng chung:

- `index.json`
- model `.onnx`
- config `.onnx.json`

Khác nhau:

- runtime để chạy model
- Windows dùng `piper_bin/piper.exe`
- macOS dùng `venv_piper/bin/piper` hoặc runtime tương đương

Nói ngắn gọn: voice library trên VPS là shared cho cả Win và Mac, chỉ phần engine local là khác theo nền tảng.

### Ví dụ thao tác deploy nhanh

```bash
mkdir -p /home/hieupt/projects/3T_Reader/phase1-backend/downloads/piper
scp index.json \
    vi_VN-vais1000-medium.onnx \
    vi_VN-vais1000-medium.onnx.json \
    en_US-ryan-medium.onnx \
    en_US-ryan-medium.onnx.json \
    hieupt@<vps>:/home/hieupt/projects/3T_Reader/phase1-backend/downloads/piper/
```

### Verify sau khi deploy

```bash
curl https://reader.3tcomputer.com/downloads/piper/index.json
curl -I https://reader.3tcomputer.com/downloads/piper/vi_VN-vais1000-medium.onnx.json
curl -I https://reader.3tcomputer.com/downloads/piper/en_US-ryan-medium.onnx.json
```

Nếu `index.json` trả `200` thì dialog `Cửa hàng Giọng AI` của Win/Mac sẽ nhìn thấy danh sách giọng.

---

## 9. Tất cả endpoints API

| Endpoint | Method | Mô tả |
|---|---|---|
| `/api/v1/update/check` | GET | Kiểm tra bản cập nhật |
| `/api/v1/license/activate` | POST | Kích hoạt license key |
| `/api/v1/license/validate` | POST | Xác thực token license |
| `/api/v1/license/heartbeat` | POST | Giữ phiên license online |
| `/api/v1/license/deactivate` | POST | Hủy kích hoạt thiết bị |
| `/admin` | GET | Trang admin (cần password) |
| `/api/admin/config` | GET/POST | Cấu hình hệ thống |
| `/api/admin/orders` | GET/POST | Quản lý đơn hàng |
| `/api/admin/staff` | GET/POST | Quản lý tài khoản nhân viên |

**Tài liệu Swagger UI tự động:**  
`https://reader.3tcomputer.com/docs`

---

## 10. Quy trình thêm release notes

Hiện tại server dùng `release_notes: ""`. Để thêm nội dung:

**Cách nhanh** — thêm biến env:
```dotenv
THREET_DEFAULT_RELEASE_NOTES=- Sửa lỗi hiển thị PDF scan\n- Tăng tốc OCR tiếng Việt\n- Cải thiện ribbon bar
```

Sau đó sửa `update_service.py` đọc biến này:
```python
"release_notes": os.getenv("THREET_DEFAULT_RELEASE_NOTES", "").replace("\\n", "\n"),
```

---

## 11. Backup dữ liệu

```bash
# Backup thủ công state file + orders
sudo cp /data/license-api-state.json /data/backup-$(date +%Y%m%d).json
sudo cp /data/orders.json /data/orders-backup-$(date +%Y%m%d).json

# Cron tự động backup mỗi ngày 2h sáng
echo "0 2 * * * root tar -czf /data/backup-\$(date +\%Y\%m\%d).tar.gz /data/*.json" \
  | sudo tee /etc/cron.d/threet-backup
```

---

## 12. Checklist trước khi go-live

- [ ] Đổi `THREET_LICENSE_SIGNING_SECRET` khỏi giá trị mặc định
- [ ] Đổi `THREET_ADMIN_PASSWORD` khỏi giá trị mặc định
- [ ] SSL certbot đã cấp và nginx reload thành công
- [ ] `curl https://reader.3tcomputer.com/api/v1/update/check?platform=mac&current_version=0.0.0` trả JSON đúng
- [ ] Upload ít nhất 1 file DMG/EXE vào `/data/downloads/`
- [ ] `THREET_DEFAULT_UPDATE_VERSION` và `THREET_DEFAULT_UPDATE_URL` đã cập nhật
- [ ] Systemd service enabled và running
- [ ] Cron backup đã bật
