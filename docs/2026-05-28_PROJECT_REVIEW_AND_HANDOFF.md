# 3T Reader / 3T Document AI - Project review and handoff

Date: 2026-05-28

Ghi chu: day la tai lieu lam viec noi bo. Phan ban quyen/thuong hieu o day la
danh gia san pham va tien do ky thuat, khong phai tu van phap ly.

## Ket luan nhanh

- Repo hien tai da di dung huong dinh huong: mot codebase chung cho Windows,
  macOS va backend/VPS; UI shell, document engine, signing, license/update va
  platform adapter da duoc tach ra theo lop.
- He thong license/VPS da co nen, phu hop voi huong thuong mai B2B.
- Ban than project chua nen xem la "copyright-ready + commercial-ready" ngay,
  vi con gap nhom viec chot ownership, provenance asset, third-party notices,
  va kiem tra thuc te tren hardware/san pham mau.
- Ban tong hop day du nhat ve tinh nang hien co va huong parity Mac nam o:
  `docs/2026-05-28_FEATURE_MATRIX_AND_MAC_PARITY.md`

## Doi chieu voi dinh huong

### Da phu hop

- Mot codebase chung cho Windows + macOS.
- Cac lop lon da ro hon: UI Shell, Document Engine, Signing, License/Update,
  Platform Adapter.
- PDF core da co viewer, search, thumbnail, annotate, edit, export, watermark,
  password, signing, recent files va installer Windows.
- VPS/license/update da di theo huong doi token/signing thay vi update public
  kieu prototype.

### Chua dong hoan toan

- Windows stream: can real USB token + vendor middleware test end-to-end.
- macOS stream: chua co chung cuong thuc te tren may macOS.
- Commercial hardening: SBOM, third-party notices, asset provenance, EULA,
  Privacy Policy, update manifest signing, release packaging review.

## Anh huong doi voi dang ky ban quyen

### 1) Cai gi can dong lai truoc khi nop ho so

| Hang muc | Trang thai hien tai | Anh huong | Viec can lam |
| --- | --- | --- | --- |
| Quyen so huu source code | Da co repo, nhung chua dong bo ho so chu so huu/assignment cho moi dong gop | Neu khong co chain of ownership ro, ho so ban quyen se yeu | Tap hop danh sach tac gia, hop dong giao quyen, va ghi ro chu so huu phap nhan |
| Third-party libraries | Da co `LICENSES.md`, `THIRD_PARTY_NOTICES.md`, `docs/compliance/THIRD_PARTY_MANIFEST.md` | Phai tach ro cai nao la cua minh, cai nao la cua nguoi khac | Cap nhat SBOM va notices, giu license dong bo voi build thuc te |
| Asset provenance | Icon/logo/source asset con can pin cuoi | Neu asset khong ro nguon, khong nen coi la tai san doc quyen cua minh | Dong co nguon icon, logo, font, screenshot, PDF.js bundle |
| Brand / trademark | Ten `3T Reader` va `3T Document AI` da co huong, nhung can freeze brand | Ban quyen phan mem khac nhan hieu | Trau truoc ten/logo, tranh nham lan voi Foxit/Adobe/Acrobat |
| Build artifacts | Repo con co file sinh ra nhu xlsx/pdf/log/temp | Lam ban ho so source bi nhieu va de nham lan tai san | Loc file sinh ra khoi goi source, cap nhat `.gitignore` |

### 2) Cai gi duoc bao ve, cai gi khong

- Duoc bao ve: source code, UI expression, icon/logo do minh tao, tai lieu,
  day build va tung phan bieu hien cu the cua app.
- Khong duoc coi la duoc bao ve theo kieu "doc quyen y tuong": cac y tuong/tinh
  nang chung nhu `signature field`, `watermark`, `search`, `annotation`,
  `export`, `password`, `OCR`, `license server`.
- Nghia la: co the lam tinh nang giong nhom app khac, nhung khong sao chep code,
  screenshot, wording, icon, menu order, hay giao dien den muc gay nham lan.

### 3) Uu tien phap ly thuc dung

- Chot quyen so huu source va tai san.
- Dong source bundle third-party theo manifest.
- Khac biet brand va icon.
- Chot EULA/Privacy/Third-party notices truoc release thuong mai.

## Cong viec da lam trong ngay 2026-05-28

### Kiem tra va doc lai

- Rasoat lai repo va cac tai lieu dinh huong:
  - `docs/PHASE0_CLOSURE.md`
  - `docs/PHASE1_WIN_STATUS.md`
  - `docs/PHASE1_3_STREAM_PLAN.md`
  - `docs/LICENSE_RISK_REGISTER.md`
  - `docs/DEPENDENCY_STRATEGY.md`
  - `docs/ASSET_SOURCES.md`
  - `THIRD_PARTY_NOTICES.md`
  - `LICENSES.md`
- Doc file dinh huong thuong mai `Dinh_huong_chi_tiet_3T_Reader_Win_Mac_IP_Thuong_mai.docx`
  va doi chieu voi tinh trang repo hien tai.

### Code va UX da sua

- Bo sung ky PFX/P12, signature field va signature template flow.
- Cai tien inline text/image editor:
  - xoay co preview truc quan hon
  - them live update cho overlay
  - chinh lai nhap text/image de dung hon
- Sua luong xoa mat khau de nham vao file goc bi ma hoa, khong nham vao file tam da giai ma.
- Chuyen export Excel sang runner rieng de giam nguy co app bi vang khi xuat xong.
- Cai tien converter Excel de dung hon voi PDF sinh tu Excel/PDF phang.
- Sua watermark, page number, va mot so luong edit de on dinh hon.

### Test da chay

- `pytest tests/test_smoke_platform.py -k signing`
- `pytest tests/test_pdf_pipeline.py -k 'text_overlay_produces_valid_pdf'`
- Export probe voi `tai_lieu_moi.pdf` da tao duoc `.xlsx`
- `py_compile` cho cac file chinh da sua

### Backend update tu VPS

- Branch backend hien tai: `phase1-backend`
- Commit hardening gan nhat: `ccbe90c` (`hardening license backend deployment`)
- Secret da duoc tach khoi `docker-compose.yml`, secret that nam trong VPS runtime `.env`
- Da them `infra/backend/.env.example` de team biet can cau hinh gi
- Upload release `.dmg` / `.exe` hien tai tu tinh `sha256`
- Token loi / sai format khong con gay API 500; server tra `{"ok": false, "message": "Invalid token."}`
- Password admin/staff da hash bang PBKDF2; admin password cu da migrate sang hash
- Team Win/Mac khong can doi API contract:
  - `POST /api/v1/license/activate`
  - `POST /api/v1/license/validate`
  - `POST /api/v1/license/heartbeat`
  - `POST /api/v1/license/deactivate`
  - `GET /api/v1/update/check?platform=mac|win&current_version=...`
- Token la opaque string, app chi luu/cache, khong parse noi dung ben trong
- `device_id` phai on dinh theo may
- File release nen dat theo convention:
  - `3TReader-<version>-mac.dmg`
  - `3TReader-<version>-win.exe`

## Cong viec can lam tiep theo

### P1 - nen lam truoc

1. Test lai `Xuất Excel` tren mot file PDF thuc te sinh tu Excel, de so sanh:
   - co con vang app khong
   - co con mat dinh dang dung cau truc hay khong
2. Test lai `Xoa mat khau` voi file PDF co password:
   - mo file
   - xoa password
   - dong/mo lai de xac nhan con giai ma dung
3. Test lai xoay khi chen text/image:
   - xoay live phai thay duoc ngay tren overlay
   - confirm phai luu dung rotation vao object edit
4. Test USB token thuc te:
   - detection
   - PIN
   - ky so
   - ky field
5. Khoa ban notices:
   - third-party notices
   - asset provenance
   - SBOM

### P2 - sau do

1. Chot EULA / Privacy Policy / license terms.
2. Lam cung package release manifest va update signing.
3. Chot brand final: ten app, logo, icon, splash, installer label.
4. Lam sach repo:
   - file sinh ra nhu `*.xlsx`, `*.pdf`, log, temp
   - script tao asset tam thoi
5. Dong bo status doc:
   - `docs/PHASE1_WIN_STATUS.md`
   - `docs/PHASE1_3_STREAM_PLAN.md`
   - `docs/compliance/THIRD_PARTY_MANIFEST.md` hoac file notices tuong ung

## File da tac dong hom nay

- `app/actions/sign.py`
- `app/signature_pad.py`
- `app/pdf_inline_editor.py`
- `app/actions/document_ops.py`
- `app/actions/edit.py`
- `app/actions/export.py`
- `packages/document_core/converter.py`
- `packages/document_core/export_runner.py`
- `packages/pdf_engine/pdfium_engine.py`
- `app/window.py`
- `app/local_server.py`
- `app/ribbon_bar.py`
- `app/pdf_viewer.py`
- `app/about_dialog.py`
- `packages/signing/*`
- `packages/qt_compat/*`

## Tai lieu lien quan

- `docs/PHASE0_CLOSURE.md`
- `docs/PHASE1_WIN_STATUS.md`
- `docs/PHASE1_3_STREAM_PLAN.md`
- `docs/LICENSE_RISK_REGISTER.md`
- `docs/DEPENDENCY_STRATEGY.md`
- `docs/ASSET_SOURCES.md`
- `THIRD_PARTY_NOTICES.md`
- `LICENSES.md`
- `NOTICE.md`

## Nguon tham khao phap ly

- WIPO Copyright: https://www.wipo.int/copyright/en/
- WIPO software copyright: https://www.wipo.int/en/web/copyright/activities/software
- WIPO Lex - Viet Nam IP Law: https://www.wipo.int/wipolex/en/text/449011
