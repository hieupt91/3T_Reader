# Internal Commercial Validation via VPS

Muc tieu:
- Chay app nhu ban thuong mai, nhung chi phat noi bo.
- Kiem tra do on dinh cua ket noi license / update qua VPS.
- Test day du activate / validate / heartbeat / update / revoke.

## 1. Nguyen tac

- Giu `VPS_LICENSE_BASE_URL` tro ve VPS that.
- Khong dung che do bypass local.
- License key la key that tren VPS, khong la key mock.
- Release noi bo van phai co sha256 va update manifest nhu ban chinh thuc.

## 2. Phia client

File can giu on dinh:
- `app/config.py`
- `packages/license_client/*`
- `app/license_dialog.py`

Kiem tra tren client:
- Mo app va nhap key.
- Neu key hop le thi app luu token cache.
- Dong mo lai app de verify cached token.
- Tat mang mot luc de xem offline grace co giu app hay khong.
- Bat mang lai de xem heartbeat co hoi phuc duoc khong.

## 3. Phia VPS

Can co:
- customer noi bo
- product
- plan test
- license key test
- release file test
- update manifest
- language pack neu can

Nen dat:
- so may gioi han theo kich ban test
- han dung ngan neu chi muon test nhanh
- release version ro rang de tiep tuc test update

## 4. Luong test ket noi on dinh

### Test 1 - Activate

- Mo app tren may noi bo.
- Nhap key.
- Kich hoat qua VPS.
- Xac nhan khong co loi timeout / retry / 500.

### Test 2 - Validate cached token

- Dong app.
- Mo lai app.
- Xac nhan app doc token cache va vao duoc ma khong can nhap lai key.

### Test 3 - Heartbeat

- De app chay mot khoang thoi gian.
- Xac nhan heartbeat gui len VPS thanh cong.
- Kiem tra truong hop mat mang tam thoi va khoi phuc lai ket noi.

### Test 4 - Update check

- Goi `GET /api/v1/update/check?platform=win|mac&current_version=...`
- Xac nhan app nhan dung version / url / sha256.
- Thu tai release va verify hash.

### Test 5 - Deactivate / revoke

- Huy kich hoat tren 1 may.
- Kiem tra may do mat quyen dung sau khi validate lai.
- Test doi may neu plan cho phep.

## 5. Luong can on dinh trong app

- `POST /api/v1/license/activate`
- `POST /api/v1/license/validate`
- `POST /api/v1/license/heartbeat`
- `POST /api/v1/license/deactivate`
- `GET /api/v1/update/check?platform=mac|win&current_version=...`
- `GET /downloads/language/{code}.json`

## 6. Ket luan

- Day la cach test gan nhat voi ban thuong mai.
- Khong can ra cong chung, chi phat noi bo.
- Neu cac test tren on dinh thi sau nay chi can thay key / plan / branding / release policy de chuyen sang ban chinh thuc.

