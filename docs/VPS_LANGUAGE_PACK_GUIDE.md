# VPS Language Pack Guide

Tai lieu nay mo ta cach host goi ngon ngu cho 3T Reader tren VPS `reader.3tcomputer.com`.

Muc tieu:

- app Win/Mac bam vao menu `Ngon ngu`
- nguoi dung chon `vi` hoac `en`
- app tai file JSON tu VPS
- app luu pack ve may va ap dung nhan UI co ban ngay lap tuc

## 1. App dang mong doi gi

App desktop hien tai dang tai goi ngon ngu theo URL sau:

```text
https://reader.3tcomputer.com/downloads/language/{code}.json
```

Trong do:

- `code = vi` cho tieng Viet
- `code = en` cho English

App se doc file JSON, lay truong `strings`, roi doi cac nhan co ban nhu menu, tab, status.
Neu file khong tai duoc, app se fallback ve ban built-in trong code.

## 2. Cau truc file nen dung

Moi goi ngon ngu nen co dang:

```json
{
  "code": "en",
  "version": "2026-05-28.1",
  "updated_at": "2026-05-28T00:00:00+07:00",
  "strings": {
    "menu.file": "File",
    "menu.navigate": "Navigate",
    "menu.view": "View",
    "menu.tools": "Tools",
    "menu.page": "Page",
    "menu.security": "Security",
    "menu.sign": "Sign",
    "menu.ocr": "OCR",
    "menu.ai": "AI",
    "menu.license": "License",
    "menu.language": "Language",
    "menu.help": "Help",
    "lang.vietnamese": "Vietnamese",
    "lang.english": "English",
    "lang.download": "Download language pack...",
    "tab.file_view": "File & View",
    "tab.annotate": "Annotate",
    "tab.page": "Page",
    "tab.security_export": "Security & Export",
    "tab.ocr_ai": "OCR & AI",
    "tab.sign": "Sign",
    "status.no_file": "No file opened",
    "status.page": "Page: -"
  }
}
```

Quy uoc:

- `code` phai khop voi ten file.
- `version` co the tang theo ngay build hoac release.
- `strings` la mapping `key -> text`.
- Key khong co thi app se dung fallback built-in.

## 3. Vi tri luu tren VPS

Khuyen nghi:

```text
/data/downloads/language/en.json
/data/downloads/language/vi.json
```

Neu sau nay co them ngon ngu, chi can them file moi:

```text
/data/downloads/language/ja.json
/data/downloads/language/zh.json
/data/downloads/language/fr.json
```

## 4. Tao thu muc tren VPS

Chay tren VPS:

```bash
sudo mkdir -p /data/downloads/language
sudo chown -R threet:threet /data/downloads/language
sudo chmod 755 /data/downloads
sudo chmod 755 /data/downloads/language
```

## 5. Tao file pack

### 5.1 Tao pack tieng Anh

```bash
cat > /data/downloads/language/en.json <<'EOF'
{
  "code": "en",
  "version": "2026-05-28.1",
  "updated_at": "2026-05-28T00:00:00+07:00",
  "strings": {
    "menu.file": "File",
    "menu.navigate": "Navigate",
    "menu.view": "View",
    "menu.tools": "Tools",
    "menu.page": "Page",
    "menu.security": "Security",
    "menu.sign": "Sign",
    "menu.ocr": "OCR",
    "menu.ai": "AI",
    "menu.license": "License",
    "menu.language": "Language",
    "menu.help": "Help",
    "lang.vietnamese": "Vietnamese",
    "lang.english": "English",
    "lang.download": "Download language pack...",
    "tab.file_view": "File & View",
    "tab.annotate": "Annotate",
    "tab.page": "Page",
    "tab.security_export": "Security & Export",
    "tab.ocr_ai": "OCR & AI",
    "tab.sign": "Sign",
    "status.no_file": "No file opened",
    "status.page": "Page: -"
  }
}
EOF
```

### 5.2 Tao pack tieng Viet

Neu ban muon host pack tieng Viet luon tren VPS:

```bash
cat > /data/downloads/language/vi.json <<'EOF'
{
  "code": "vi",
  "version": "2026-05-28.1",
  "updated_at": "2026-05-28T00:00:00+07:00",
  "strings": {
    "menu.file": "Tep",
    "menu.navigate": "Dieu huong",
    "menu.view": "Xem",
    "menu.tools": "Cong cu",
    "menu.page": "Trang",
    "menu.security": "Bao mat",
    "menu.sign": "Chu ky so",
    "menu.ocr": "OCR",
    "menu.ai": "AI",
    "menu.license": "License",
    "menu.language": "Ngon ngu",
    "menu.help": "Tro giup",
    "lang.vietnamese": "Tieng Viet",
    "lang.english": "English",
    "lang.download": "Tai goi ngon ngu...",
    "tab.file_view": "Tep & Xem",
    "tab.annotate": "Chu thich",
    "tab.page": "Trang",
    "tab.security_export": "Bao mat & Xuat",
    "tab.ocr_ai": "OCR & AI",
    "tab.sign": "Ky so",
    "status.no_file": "Chua mo tep",
    "status.page": "Trang: -"
  }
}
EOF
```

Luu y:

- App dang co fallback built-in tieng Viet, nen file `vi.json` khong bat buoc.
- Neu muon dong bo 100%, nen luu ca hai file `vi.json` va `en.json`.

## 6. Nginx

Config Nginx hien tai dang co:

```nginx
location /downloads/ {
    root /data;
    autoindex off;
    add_header Content-Disposition "attachment";
}
```

Block nay da phu hop voi language pack vi URL se thanh:

```text
/downloads/language/en.json
/downloads/language/vi.json
```

Neu ban muon tach cache header rieng cho language pack, co the them block dac biet:

```nginx
location /downloads/language/ {
    root /data;
    autoindex off;
    add_header Cache-Control "public, max-age=3600";
}
```

Luu y:

- block `location /downloads/language/` phai nam tren `location /downloads/` neu ban them rieng.
- sau khi sua Nginx, chay `nginx -t` va `systemctl reload nginx`.

## 7. Test tren VPS

Sau khi upload file, test:

```bash
curl -I https://reader.3tcomputer.com/downloads/language/en.json
curl https://reader.3tcomputer.com/downloads/language/en.json
```

Can thay:

- HTTP 200
- response la JSON hop le
- khong bi HTML 404

Neu muon xem nhanh noi dung:

```bash
curl https://reader.3tcomputer.com/downloads/language/en.json | jq .
```

## 8. Cach app su dung

Tren desktop:

- mo menu `Ngon ngu`
- chon `English` hoac `Tieng Viet`
- app se tai pack tu VPS
- neu tai thanh cong, app cap nhat cac nhan co ban
- neu tai that bai, app van doi qua fallback built-in

## 9. Quy trinh release de khong loi

Khi co cap nhat nguyen nhan ngon ngu:

1. Sua file JSON tren VPS.
2. Tang truong `version`.
3. Upload vao `/data/downloads/language/`.
4. Test `curl`.
5. Mien sao the, chay `systemctl reload nginx` neu sua config.
6. Mo app desktop va bam `Ngon ngu` de tai lai pack.

## 10. Nguoi phu trach can nho gi

- Khong commit secret vao repo.
- File ngon ngu la static file, khong can build lai backend API.
- App desktop chi can URL voi format da noi o tren.
- Neu sau nay muon them ngon ngu moi, chi can them file `xx.json` va cap nhat menu UI ben app.

## 11. Lien ket voi tai lieu khac

- [VPS_DEPLOY_GUIDE.md](VPS_DEPLOY_GUIDE.md)
- [LICENSE_CLIENT_GUIDE.md](LICENSE_CLIENT_GUIDE.md)
