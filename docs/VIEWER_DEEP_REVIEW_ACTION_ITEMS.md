# Viewer Deep Review - Action Items

Ngay review: 2026-06-29

Pham vi review:

- Viewer chinh: `app/pdf_viewer.py`
- Local PDF.js server: `app/local_server.py`
- WebChannel bridge: `app/webchannel.py`
- PDF.js hook layer: `assets/js/pdfjs_ui_hooks.js`
- Cac luong lien quan Phase 7: edit existing text/object, soft reload, overlay, signature metadata

## 1. Ket luan nhanh

Viewer hien tai da dat nen tang kha tot de dong bo voi nhanh Win Phase 7. Cac diem cot loi da dung huong:

- PDF.js duoc serve qua local HTTP server rieng, phu hop voi `QWebEngineView`.
- Endpoint `/pdf` co allow-list path va cache invalidation theo path/mtime/size.
- WebChannel dung proxy on dinh, giam loi JS giu object cu sau khi Python thay bridge target.
- Page state co ca event bridge va polling fallback.
- Phase 7 edit text goc da su dung `viewport.convertToPdfPoint()` tu PDF.js va backend dung quy doi cropbox/rotation/font Unicode.
- Soft reload giu page/scroll va giam flash trang sau khi edit.

Danh gia tong the: viewer da san sang o muc kha cao, nhung con mot so diem can xu ly truoc khi coi la parity 100% va on dinh production.

## 2. Muc uu tien xu ly

| Muc | Hang muc | Rui ro | File lien quan |
| --- | --- | --- | --- |
| P0 | Audit luong Save vi `PDFViewerWidget.save_pdf()` dang la stub | Nguoi dung bam Save nhung khong ghi file neu caller goi truc tiep viewer | `app/pdf_viewer.py`, `app/window.py`, cac action save |
| P1 | Tach `reload_soft()` JS khoi Python string lon | Kho review/test, de vo quote/style/coordinate | `app/pdf_viewer.py`, `assets/js/pdfjs_ui_hooks.js` |
| P1 | Chuan hoa mot helper coordinate duy nhat cho overlay/edit | Lech overlay khi zoom/rotation/page margin/DPR | `app/pdf_viewer.py`, `assets/js/pdfjs_ui_hooks.js`, `app/actions/edit.py` |
| P1 | Dung chung path validation cho `/pdf` va `/sigmeta` | Security/behavior khong nhat quan, dac biet Windows path | `app/local_server.py` |
| P2 | Dat nguong soft reload theo kich thuoc file | PDF lon co the ton RAM gap nhieu lan | `app/pdf_viewer.py`, `app/local_server.py` |
| P2 | Gate JS console logging bang debug flag | Production output on, co the lo path/noi dung loi | `app/pdf_viewer.py` |
| P2 | Prune/unregister allowed PDF paths | App mo lau co the phinh allow-list/cache | `app/local_server.py` |
| P3 | Bo sung E2E/screenshot test cho viewer | Unit test chua bat duoc loi visual | tests moi |

## 3. Chi tiet tung van de

### P0 - Audit luong Save

Hien trang:

- `PDFViewerWidget.save_pdf()` chi emit loi khi khong co `current_pdf_path`.
- Neu co path, ham gan nhu khong thuc hien ghi PDF.
- Cac edit PDF dang duoc save qua pipeline rieng, nhung can xac nhan khong co action nao fallback vao `viewer.save_pdf()` voi ky vong save that.

Rui ro:

- Neu nut Save hoac shortcut Save goi `viewer.save_pdf()` trong mot nhanh nao do, nguoi dung co the tuong file da duoc luu nhung thuc te khong co thay doi nao duoc ghi.
- Rui ro nay nghiem trong vi la loi mat du lieu/khong luu du lieu, kho phat hien bang UI neu khong co thong bao ro.

Can lam:

- `rg "save_pdf\\(" app packages tests`
- Ve lai so do luong Save:
  - Save PDF edited text/object
  - Save annotation
  - Save signed PDF
  - Save PDF.js form/annotation neu co
- Neu viewer khong nen save, doi ten ham thanh private/no-op ro rang hoac emit warning.
- Neu viewer can save, trien khai save that hoac dieu huong sang pipeline save hien co.

Definition of Done:

- Moi action Save co test hoac smoke case.
- Khong con caller production nao goi `viewer.save_pdf()` voi ky vong save that neu ham van la stub.
- UI co thong bao ro khi khong co thay doi de luu hoac luu thanh cong.

### P1 - Tach soft reload JS khoi Python string

Hien trang:

- `reload_soft()` trong `app/pdf_viewer.py` chua mot khoi JS lon.
- JS nay lam nhieu viec cung luc:
  - Freeze canvas hien tai
  - Lay page/scroll hien tai
  - Fetch PDF bytes voi cache busting
  - Goi `PDFViewerApplication.open({ data })`
  - Restore page/scroll
  - Render lai overlay
  - Fallback hard reload khi loi

Rui ro:

- Kho test rieng bang JS.
- Kho review vi string Python phai escape nhieu lop.
- De drift voi logic overlay trong `update_ops()` va JS hook khac.
- Neu object op co gia tri style/font bat thuong, viec ghep style inline co the gay loi render.

Can lam:

- Tao module JS rieng, vi du:
  - `assets/js/viewer_soft_reload.js`
  - Expose `window.__3tSoftReload.reload(options)`
- Python chi goi mot API nho:
  - path/url
  - page number
  - scroll state
  - overlay ops
  - fallback flag
- Tach helper render overlay dung chung giua soft reload va `update_ops()`.

Definition of Done:

- `app/pdf_viewer.py` khong con khoi JS inline lon cho soft reload.
- JS co API ro rang va idempotent.
- Co test/toi thieu smoke:
  - reload giu dung page
  - reload giu scroll gan dung
  - overlay van nam dung vi tri sau reload
  - loi fetch fallback sang hard reload

### P1 - Chuan hoa coordinate helper

Hien trang:

- Cac vi tri overlay dang duoc tinh o nhieu noi:
  - `update_ops()` trong `app/pdf_viewer.py`
  - JS trong `reload_soft()`
  - edit object/text flow trong `app/actions/edit.py`
  - text click/selection trong `assets/js/pdfjs_ui_hooks.js`
- Co nhieu he toa do:
  - PDF point
  - viewport point
  - canvas client rect
  - page element local rect
  - cropbox-adjusted coordinate

Rui ro:

- Lech overlay khi zoom.
- Lech khi PDF page co cropbox khac mediabox.
- Lech voi rotation 90/180/270.
- Lech khi PDF.js thay doi DOM margin/canvas layer.
- Loi chi xuat hien voi mot so file PDF that, kho bat bang test don gian.

Can lam:

- Tao mot JS helper dung chung:
  - `pdfRectToViewportRect(pageView, pdfRect)`
  - `viewportRectToPageLocalRect(pageView, viewportRect)`
  - `pdfPointToPageLocalPoint(pageView, x, y)`
- Tat ca overlay/edit handles dung helper nay.
- Backend chi luu toa do PDF canonical; frontend chuyen sang viewport/page-local.

Definition of Done:

- Khong con cong thuc tinh `canvasRect`, `pageRect`, `clientRect` lap lai o nhieu noi.
- Test/smoke voi:
  - zoom 50%, 100%, 200%
  - page rotated 90 do
  - PDF co cropbox offset
  - multi-page PDF

### P1 - Dung chung validate path cho `/pdf` va `/sigmeta`

Hien trang:

- Endpoint `/pdf` da duoc gia co security:
  - reject traversal
  - allow registered absolute paths
  - xu ly Windows absolute path tot hon
  - no-store response
  - support Range
- Endpoint `/sigmeta` co logic rieng va chua dong bo day du voi `/pdf`.

Rui ro:

- Cung mot file co the xem PDF duoc nhung metadata chu ky loi.
- Windows-style path co the bi reject khac nhau giua hai endpoint.
- Security review kho hon vi co hai policy path khac nhau.

Can lam:

- Tao helper rieng trong `LocalPDFJSServer`, vi du:
  - `_resolve_registered_pdf_path(raw_path: str) -> str | None`
  - `_is_registered_pdf_path(path: str) -> bool`
  - `_is_forbidden_pdf_request(raw_path: str) -> bool`
- `/pdf` va `/sigmeta` dung chung helper.
- Them test cho `/sigmeta`:
  - path hop le da register
  - relative traversal
  - Windows absolute path
  - unregistered absolute path

Definition of Done:

- Logic security path chi nam o mot noi.
- `/pdf` va `/sigmeta` co behavior nhat quan.
- Test local server security bao phu ca metadata endpoint.

### P2 - Gioi han soft reload cho PDF lon

Hien trang:

- Soft reload fetch full PDF bytes vao JS.
- Server co nguong normalize signed PDF nho/lon, nhung viewer soft reload van co the doc ca file vao `ArrayBuffer`.

Rui ro:

- File PDF lon co the ton RAM nhieu lan:
  - server/cache bytes
  - JS `ArrayBuffer`
  - PDF.js internal buffer
  - canvas/page cache
- Rui ro giat/treo khi edit file lon.

Can lam:

- Lay file size truoc khi soft reload.
- Dat nguong, vi du 30-50 MB tuy memory target.
- Neu vuot nguong:
  - hard reload URL co cache-busting
  - restore page sau load
  - bo qua freeze canvas neu can

Definition of Done:

- Soft reload chi dung cho PDF duoi nguong.
- File lon khong bi duplicate bytes trong JS.
- Co smoke voi file > nguong.

### P2 - Gate JS console logging

Hien trang:

- `_DebugPage.javaScriptConsoleMessage()` print JS console ra stdout.

Rui ro:

- Production log on.
- Co the lo local path/file name/error noi bo.
- Kho doc log khi user thao tac nhieu.

Can lam:

- Them debug flag, vi du env:
  - `THREET_READER_DEBUG_JS=1`
- Chi print khi flag bat.
- Loi nghiem trong van co the route qua logger neu can.

Definition of Done:

- Production macOS build khong spam JS console mac dinh.
- Debug build van xem duoc console khi can.

### P2 - Prune allowed PDF paths/cache

Hien trang:

- `LocalPDFJSServer.register_pdf()` them path vao allow-list.
- Cache co LRU gioi han, nhung allow-list co the tang theo thoi gian chay app.

Rui ro:

- App mo lau voi nhieu temp file co allow-list phinh.
- Cac path temp da xoa van con trong allow-list.

Can lam:

- Them unregister khi viewer close/tab close neu app co multi-document.
- Hoac prune theo LRU/time:
  - giu N path gan nhat
  - loai path khong ton tai nua

Definition of Done:

- Allow-list khong tang vo han.
- Cache va allow-list co chien luoc vong doi ro.

## 4. Test can bo sung

### Viewer E2E / visual smoke

Can them test hoac script smoke co the chay tren macOS:

- Mo PDF multi-page.
- Zoom 50%, 100%, 200%.
- Edit existing text co dau tieng Viet.
- Soft reload sau edit.
- Kiem tra:
  - page hien tai khong bi nhay ve page 1
  - scroll gan dung
  - overlay/handle dung vi tri
  - text Unicode khong mat dau
  - signature hitbox van click duoc

### Local server security

Can them case:

- `/sigmeta?file=<registered path>` thanh cong.
- `/sigmeta?file=../x.pdf` bi reject.
- `/sigmeta?file=C:\\temp\\a.pdf` hanh vi nhat quan voi `/pdf`.
- Unregistered absolute path bi reject.

### Save flow

Can them case:

- Save sau edit existing text.
- Save sau edit object/image.
- Save khi khong co edit pending.
- Save khi PDF path khong ton tai nua.
- Save failure phai co message ro, khong silent.

### Large PDF

Can them smoke:

- File > nguong soft reload.
- Edit 1 text/object.
- App reload khong treo va quay lai dung page.

## 5. Trang thai test da chay khi review

Cac nhom test da pass:

- `tests/test_pdf_pipeline.py`
- `tests/test_pdf_save_helpers.py`
- `tests/test_viewer_annotation_regressions.py`
- `tests/test_stability_contracts.py`
- `tests/test_ai_chat_phase6_regressions.py`
- `tests/test_annotation_queue.py`
- `tests/test_pr7_helpers.py`
- `tests/test_signing_pr4.py`
- `tests/test_license_pr6.py`
- `tests/test_local_server.py`

Full `tests/` tai thoi diem review:

- `245 passed`
- `17 skipped`
- `3 failed`

Ghi chu ve 3 failed:

- 2 test lien quan PyMuPDF default path fail do thu tu import trong full suite; khi chay rieng thi pass.
- 1 test single-instance fail do sandbox chan bind TCP localhost, khong phai loi viewer logic truc tiep.

## 6. De xuat thu tu lam tiep

1. Xu ly P0 Save audit truoc.
2. Chuan hoa path validation cho `/pdf` va `/sigmeta`.
3. Tach soft reload JS sang asset rieng.
4. Tao helper coordinate dung chung.
5. Them nguong large-PDF cho soft reload.
6. Gate JS console logging.
7. Them E2E/screenshot smoke cho viewer.

## 7. Quy trinh AI tu lam - tu check - tu commit

Muc tieu cua phan nay la de bat ky AI/dev nao doc file nay co the tu xu ly cac hang muc theo dung thu tu, tu kiem tra chat luong, va tu commit khi da dat yeu cau.

### Nguyen tac bat buoc

- Lam tung hang muc uu tien mot, khong tron nhieu refactor lon vao cung mot commit.
- Khong revert thay doi co san trong worktree neu khong chac do minh tao ra.
- Truoc khi sua, phai ghi nhan trang thai dirty hien tai bang `git status --short`.
- Khi commit, chi stage dung file lien quan toi hang muc vua lam.
- Khong commit neu test lien quan fail.
- Khong commit neu con diff khong hieu ro.
- Khong commit file binary/temp/log neu khong phai output bat buoc cua task.
- Neu gap loi moi truong, phai ghi ro loi moi truong va khong commit code workaround vo can.

### Buoc 0 - Doc va chon task

AI/dev phai doc file nay tu dau den cuoi, sau do chon hang muc uu tien cao nhat chua hoan tat.

Thu tu mac dinh:

1. P0 Save audit.
2. P1 validate path `/pdf` va `/sigmeta`.
3. P1 tach soft reload JS.
4. P1 chuan hoa coordinate helper.
5. P2 large-PDF soft reload threshold.
6. P2 gate JS console logging.
7. P2 prune allowed PDF paths/cache.
8. P3 bo sung viewer E2E/smoke.

Neu mot task phu thuoc task khac, lam dependency truoc va ghi ro trong commit message.

### Buoc 1 - Khao sat truoc khi sua

Chay cac lenh sau:

```bash
git status --short
git branch --show-current
rg "save_pdf\\(|reload_soft\\(|sigmeta|register_pdf|__3tOps|convertToPdfPoint" app assets packages tests
```

Can doc code lien quan truoc khi sua:

- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/webchannel.py`
- `assets/js/pdfjs_ui_hooks.js`
- `app/actions/edit.py`
- Test hien co trong `tests/`

Ket qua khao sat phai tra loi duoc:

- Flow hien tai dang di qua function nao?
- Co caller nao bi anh huong?
- Co file dirty san tu truoc khong?
- Test nao phai chay sau khi sua?

### Buoc 2 - Lap ke hoach sua nho

Truoc khi edit, phai xac dinh:

- File se sua.
- Behavior mong muon sau khi sua.
- Test can them hoac cap nhat.
- Rui ro regression.

Quy tac:

- Neu sua logic server/security, phai them/cap nhat unit test.
- Neu sua coordinate/overlay, phai them it nhat smoke/unit test co the tu dong chay.
- Neu sua viewer JS, phai chay syntax check JS neu co `node`.
- Neu sua Python, phai chay compile hoac pytest lien quan.

### Buoc 3 - Sua code

Chi sua dung pham vi cua task dang lam.

Vi du pham vi hop le:

- Task `/sigmeta` validation:
  - Sua `app/local_server.py`
  - Them/cap nhat `tests/test_local_server_security.py`
- Task JS console logging:
  - Sua `app/pdf_viewer.py`
  - Them test neu code co helper de test
- Task soft reload:
  - Sua `app/pdf_viewer.py`
  - Them file JS moi trong `assets/js/`
  - Cap nhat injection neu can
  - Them test/smoke lien quan

Khong nen lam trong cung commit:

- Doi style UI khong lien quan.
- Format toan bo file lon.
- Sua dependency khong can thiet.
- Commit file sinh ra tam thoi.

### Buoc 4 - Tu check sau khi sua

Chay nhom check toi thieu theo loai thay doi.

Neu sua Python chung:

```bash
python3 -m compileall app packages
```

Neu sua JS viewer:

```bash
node --check assets/js/pdfjs_ui_hooks.js
```

Neu them file JS moi:

```bash
node --check assets/js/<ten_file_moi>.js
```

Neu sua local server:

```bash
python3 -m pytest tests/test_local_server.py tests/test_local_server_security.py -q
```

Neu sua PDF pipeline/edit:

```bash
python3 -m pytest tests/test_pdf_pipeline.py tests/test_pdf_save_helpers.py tests/test_viewer_annotation_regressions.py -q
```

Neu sua stability/window/webchannel:

```bash
python3 -m pytest tests/test_stability_contracts.py tests/test_viewer_annotation_regressions.py -q
```

Neu sua signing/signature metadata:

```bash
python3 -m pytest tests/test_signing_pr4.py tests/test_local_server.py -q
```

Neu task co rui ro rong:

```bash
python3 -m pytest tests -q
```

Chap nhan full suite co the gap loi moi truong da biet:

- Test single-instance co the fail neu sandbox chan bind TCP localhost.
- Mot so test PyMuPDF default path co the fail trong full suite do thu tu import, nhung phai chay rieng de xac nhan pass.

Neu full suite fail, phai phan loai:

- Fail do code vua sua: fix tiep, khong commit.
- Fail do moi truong da biet: ghi ro trong commit/body hoac final note.
- Fail khong lien quan nhung moi xuat hien: dieu tra truoc khi commit.

### Buoc 5 - Tu review diff

Truoc khi commit, chay:

```bash
git diff -- app assets packages tests docs
git status --short
```

Tu kiem tra:

- Diff co dung task khong?
- Co file la/temp/binary bi them nham khong?
- Co xoa code khong lien quan khong?
- Co thay doi format qua rong khong?
- Co comment/TODO tam thoi khong?
- Co log debug mac dinh trong production khong?
- Test moi co that su assert behavior moi khong?

Neu worktree co dirty file khong lien quan tu truoc:

- Khong stage bang `git add .`.
- Stage tung file cu the.
- Neu file co ca thay doi lien quan va khong lien quan, dung partial staging hoac tach task.

### Buoc 6 - Dieu kien duoc commit

Chi duoc commit khi tat ca dieu kien sau dat:

- Task co Definition of Done da hoan tat.
- Test lien quan pass.
- Diff da duoc review.
- Khong stage file khong lien quan.
- Khong con debug print/log moi khong can thiet.
- Khong co regression ro rang voi Phase 7 edit/export/signature/viewer.

Lenh commit mau:

```bash
git add <file-1> <file-2> <test-file>
git diff --cached
git commit -m "fix(viewer): <mo ta ngan gon>"
```

Quy uoc commit message:

- `fix(viewer): ...` cho bug viewer.
- `fix(server): ...` cho local server/security.
- `refactor(viewer): ...` cho tach JS/helper khong doi behavior.
- `test(viewer): ...` cho test/smoke.
- `docs(viewer): ...` cho tai lieu.

Vi du:

```bash
git commit -m "fix(server): share pdf path validation with signature metadata"
git commit -m "refactor(viewer): move soft reload logic into js asset"
git commit -m "fix(viewer): guard soft reload for large pdf files"
```

### Buoc 7 - Sau khi commit

Sau commit, chay:

```bash
git status --short
git log -1 --stat
```

Bao cao ngan gon:

- Da xu ly task nao.
- Commit hash la gi.
- Test nao da chay va ket qua.
- Con rui ro nao chua xu ly.
- Task tiep theo nen lam la gi.

### Mau bao cao sau khi commit

```text
Da xu ly: P1 - dung chung validate path cho /pdf va /sigmeta
Commit: <hash> fix(server): share pdf path validation with signature metadata
Files: app/local_server.py, tests/test_local_server_security.py
Tests: python3 -m pytest tests/test_local_server.py tests/test_local_server_security.py -q
Ket qua: passed
Con lai: P1 tach soft reload JS, P1 coordinate helper
```

### Truong hop khong duoc commit

Khong commit trong cac truong hop:

- Test lien quan fail.
- Chua hieu diff.
- Co conflict voi dirty changes cua nguoi khac.
- Can quyet dinh product/UX ma file nay khong du thong tin.
- Sua toi file binary/release artifact khong nam trong task.
- Moi truong khong cho chay test toi thieu.

Khi khong commit, phai de lai bao cao:

```text
Chua commit vi: <ly do>
Da sua/da thu: <tom tat>
Test da chay: <ket qua>
Can quyet dinh: <neu co>
```

## 8. Checklist cho team

- [ ] Audit tat ca caller cua `save_pdf()`.
- [ ] Quyet dinh `PDFViewerWidget.save_pdf()` se save that hay khong duoc goi truc tiep.
- [ ] Tao helper validate path dung chung cho `/pdf` va `/sigmeta`.
- [ ] Them test security cho `/sigmeta`.
- [ ] Tach JS soft reload khoi Python string.
- [ ] Gom overlay coordinate vao mot helper JS duy nhat.
- [ ] Test zoom/rotation/cropbox voi edit text/object.
- [ ] Them nguong file size cho soft reload.
- [ ] Tat JS console log mac dinh trong production.
- [ ] Them strategy prune/unregister allowed PDF paths.
- [ ] Them smoke test viewer sau edit Phase 7.
