# Viewer GUI Regression Checklist

Muc dich: checklist nay dung de test nhanh truoc khi dong goi ban va loi. Moi muc can ghi Pass/Fail va console log neu co loi.

## Mau PDF Can Co

- PDF text binh thuong, 2-5 trang.
- PDF nhieu trang, toi thieu 50 trang.
- PDF da ky so.
- PDF co van ban tieng Viet dau day du.
- PDF scan/anh de test in va export cham.

## Mo File Va Dieu Huong

- [ ] Mo app bang double click file PDF hoac command line path, tai lieu mo thang vao viewer.
- [ ] Cuon mouse wheel qua tung trang, o so trang cap nhat theo trang dang xem.
- [ ] Keo scrollbar doc nhanh, o so trang va thumbnail highlight cap nhat theo.
- [ ] Bam Trang truoc/Trang sau, viewer va thumbnail cung doi trang.
- [ ] Bam thumbnail, viewer nhay dung trang va o so trang dung.
- [ ] Dong/mo tab khong co loi QWebChannel trong console.

## Zoom

- [ ] Mo file mac dinh 100%.
- [ ] Bam phong to/thu nho, o % zoom doi dung.
- [ ] Ctrl+wheel, o % zoom doi dung.
- [ ] Ctrl+plus/Ctrl+minus neu duoc ho tro, o % zoom doi dung.
- [ ] Bam Vua trang, zoom ve dung mode mac dinh hien tai cua app.
- [ ] Sau reload bat buoc, trang va zoom khong nhay ve ngoai y muon.

## Text Mark

- [ ] Boi den mot tu, bam To sang, khong hien hop nhap text.
- [ ] Boi den mot dong, bam To sang, highlight thang va deu.
- [ ] Boi den nhieu dong, bam To sang, khong bao "Khong tim thay".
- [ ] Ctrl+A, bam To sang/Gach duoi/Gach ngang, khong bao "Khong tim thay".
- [ ] Gach duoi nam duoi chu, khong lech dong.
- [ ] Gach ngang nam giua chu, khong lech dong.
- [ ] Bam Hoan tac xoa dung batch vua tao.

## Ghi Chu Pin

- [ ] Boi den text, bam Ghi chu, pin dat tai dau rect dau tien cua selection.
- [ ] Khong boi den, bam Ghi chu, app cho click tren trang de dat pin.
- [ ] Click trai pin mot lan, hien noi dung.
- [ ] Click ra ngoai popup, ve che do xem binh thuong.
- [ ] Double click pin, sua duoc noi dung.
- [ ] Chuot phai pin, hien menu xoa; bam Xoa thi note bien mat.
- [ ] Keo pin sang vi tri moi, dong/mo file van dung vi tri.
- [ ] Tao/sua/xoa/keo lien tiep 10 note khong reload viewer.

## Chen Chu, Chen Anh, Object Edit

- [ ] Chen chu tai vi tri click.
- [ ] Chon object text, hien handle dung vi tri o zoom 100/150/200.
- [ ] Sua noi dung text da chen.
- [ ] Di chuyen text da chen.
- [ ] Xoa text da chen.
- [ ] Chen anh, resize/di chuyen/xoa duoc.
- [ ] Chon xoay object hoat dong o zoom 100/150/200.
- [ ] Console khong co `channel.execCallbacks` khi lap lai thao tac.

## In Va Export

- [ ] In file nho hien dialog in va progress khi render.
- [ ] In file lon co the bam Huy, app khong treo im lang.
- [ ] Export Word hien progress va co the huy.
- [ ] Export Excel hien progress theo trang va co the huy.
- [ ] Loi export hien thong bao co noi dung cu the.
- [ ] Sau khi export fail/cancel khong de lai file output rong.

## Console Log Khong Duoc Co

- [ ] `channel.execCallbacks[message.id] is not a function`
- [ ] `Registered new object after initialization`
- [ ] `Unknown object encountered`
- [ ] `promises.getOrInsertComputed is not a function`
- [ ] Traceback Python trong thao tac binh thuong.

## Ket Qua Lan Test

```text
Ngay test:
Build/commit:
Nguoi test:
PDF da dung:
Tong ket Pass/Fail:
Loi con lai:
Quyet dinh release:
```
