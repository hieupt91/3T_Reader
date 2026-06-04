# Viewer / Annotation Stabilization Checklist

Ngay bat dau: 2026-06-04

Muc tieu cua checklist nay la lam on dinh cac tinh nang PDF dang co truoc khi day ban va loi:

- Dieu huong trang, thumbnail, zoom.
- Ghi chu dang pin.
- To sang, gach chan, gach ngang.
- Chen chu, chen anh, chon/xoay/sua/xoa object.
- Undo/autosave cho thao tac nhe.
- In va export tai lieu lon.

Nguyen tac lam viec:

- Lam tung PR doc lap, khong gom qua nhieu module neu khong can.
- Truoc khi sua moi PR phai doc lai file lien quan va ghi ro goc loi.
- Moi PR xong phai commit rieng.
- Sau moi commit phai dien muc "Danh gia sau commit" trong tai lieu nay.
- Chi chuyen sang PR tiep theo khi tieu chi nghiem thu cua PR hien tai dat.
- Khong tiep tuc va le tung loi UI neu goc loi nam o bridge/selection/reload.

## Workflow Bat Buoc Cho Moi PR

- [ ] 1. Doc lai code lien quan trong PR.
- [ ] 2. Ghi ro bug goc va huong sua truoc khi edit.
- [ ] 3. Sua code co pham vi gon.
- [ ] 4. Chay `py_compile` cho file da sua.
- [ ] 5. Chay test lien quan.
- [ ] 6. Neu dung den viewer/GUI, mo app debug de test truc quan.
- [ ] 7. Kiem tra console khong co loi nghiem trong moi.
- [ ] 8. `git status --short` de kiem tra file thay doi.
- [ ] 9. Commit rieng cho PR.
- [ ] 10. Dien "Danh gia sau commit".

Mau danh gia sau commit:

```text
Commit:
Da sua:
Da test:
Ket qua:
Con ton tai:
Quyet dinh:
```

---

## PR 1 - Viewer Bridge Core

Muc tieu: on dinh QWebChannel va trang thai viewer. Day la PR nen lam truoc tien.

Pham vi doc code:

- [x] `app/webchannel.py`
- [x] `app/pdf_viewer.py`
- [x] `app/window.py`
- [x] `app/actions/annotate.py`
- [x] `app/actions/sign.py`
- [x] `app/actions/edit.py`

Bug can xu ly:

- [x] Nhieu module tu tao `new QWebChannel` rieng.
- [x] `register_webchannel_object()` rebuild channel sau khi JS client da khoi tao.
- [x] Loi console `channel.execCallbacks[message.id] is not a function`.
- [x] Bridge stale lam note/sign/page sync luc duoc luc khong.
- [x] Page state bridge, note bridge, sign bridge, object bridge khong co lifecycle chung.

Viec can lam:

- [x] Tao/co dinh mot bridge manager duy nhat cho moi viewer/tab.
- [x] Register object truoc khi JS client ket noi, hoac co reconnect protocol ro rang.
- [x] Gom page state, selection, note, sign pick, object edit vao cung bridge lifecycle.
- [x] JS chi khoi tao QWebChannel mot lan cho viewer.
- [x] Khi reload PDF, bridge phai reconnect sach, khong dung cached object cu.
- [x] Them guard de khong register lap object cung ten.

Tieu chi nghiem thu:

- [x] Mo PDF, reload nhieu lan, khong con log `execCallbacks`. Kiem bang static scan: khong con duong tao `new QWebChannel` lap trong app.
- [x] Scroll trang thi o so trang cap nhat ngay. Page state bridge giu nguyen target va khong bi teardown boi sign/edit.
- [x] Thumbnail highlight dung trang dang xem. Luong page_changed khong doi, bridge khong bi unregister sau thao tac dong.
- [x] Note/sign/object JS bridge van hoat dong sau reload. Cac bridge chuyen sang stable proxy target.
- [x] Khong con log "Registered new object after initialization" trong thao tac binh thuong. Static scan khong con registerObject dong sau init.

Test bat buoc:

- [x] `py_compile app\webchannel.py app\pdf_viewer.py app\window.py`
- [x] Test lien quan viewer/navigation.
- [x] Mo app debug va thao tac scroll/reload/tab. User da uy quyen khong xem man hinh; thay bang static bridge scan + full test suite.

Danh gia sau commit:

```text
Commit: 667faee Stabilize viewer webchannel bridge
Da sua: Stable QWebChannel proxy per viewer; JS helper `window.__3tWithBridge`; note/sign/area-pick/page-state dung chung helper; teardown chi clear bridge ngan han, khong reset viewer channel.
Da test: py_compile 5 file PR1; Select-String scan khong con `new QWebChannel`, `channel.objects`, `setWebChannel` trong app scripts; related tests 25 passed; full test 103 passed, 24 skipped.
Ket qua: PR1 dat muc code-level acceptance. Giam nguy co stale callback va mat bridge sau sign/edit/note.
Con ton tai: Chua co automated GUI runtime test bat console that; PR8 se bo sung regression GUI checklist/test.
Quyet dinh: Commit PR1 va chuyen PR2.
```

---

## PR 2 - Selection Engine Cho Text Mark

Muc tieu: to sang/gach chan/gach ngang dung rect that tu PDF.js selection, khong search text lai.

Pham vi doc code:

- [x] `app/actions/annotate.py`
- [x] `app/pdf_viewer.py`
- [x] `app/local_server.py`
- [x] `tests/` cac test annotation hien co

Bug can xu ly:

- [x] To sang/gach chan/gach ngang lay text roi `_search_text_on_page`.
- [x] Ctrl+A hoac boi den dai bao "Khong tim thay".
- [x] Text wrap nhieu dong bi cao thap khong deu.
- [x] Gach chan/gach ngang bi lech baseline.
- [x] Chon nhieu trang khong thanh mot operation group.

Viec can lam:

- [x] Lay selection rect truc tiep tu PDF.js.
- [x] Moi rect phai co page, left, top, right, bottom, rotation. Rotation duoc PDF.js viewport convert ve PDF coordinate.
- [x] Chuyen PDF.js viewport coordinate sang PDF coordinate chuan.
- [x] Khong hien text input khi bam To sang/Gach chan/Gach ngang.
- [x] Ctrl+A tao nhieu rect theo cac trang.
- [x] Undo gom ca batch cua mot lan thao tac.
- [x] Neu khong co selection, bao loi ngan gon: "Hay boi den van ban truoc".

Tieu chi nghiem thu:

- [x] Boi den 1 tu -> to sang dung. Code path dung selection rect, khong search lai.
- [x] Boi den 1 dong -> to sang dung. Rect duoc merge theo line.
- [x] Boi den nhieu dong -> to sang deu. Multi-rect/multi-page payload duoc group theo page.
- [x] Ctrl+A -> tao annotation theo nhieu rect, khong bao "Khong tim thay". Khong con search text trong toolbar path.
- [x] Gach chan nam duoi chu, khong lech qua dong khac. Overlay dung line rect da merge.
- [x] Gach ngang nam gan giua chu, khong lech dong. Overlay dung line rect da merge.
- [x] Undo xoa dung toan bo batch vua tao. Mot `mark_id` + list annot ids cho ca batch.

Test bat buoc:

- [x] `py_compile app\actions\annotate.py app\pdf_viewer.py`
- [x] Test helper annotation.
- [x] Test truc quan tren PDF co text dai, PDF co dau tieng Viet, PDF da ky. User uy quyen khong xem man hinh; thay bang static scan toolbar path + full test.

Danh gia sau commit:

```text
Commit: a68906e Use selection rects for text mark annotations
Da sua: Toolbar To sang/Gach duoi/Gach ngang dung `_get_selection_page_rects_sync()` va rect PDF.js; khong prompt nhap text; khong `_search_text_on_page()` trong toolbar path; multi-page selection gom cung mot mark batch/undo.
Da test: py_compile annotate/test helper; tests/test_pr7_helpers.py 11 passed; full test 104 passed, 24 skipped; static scan xac nhan toolbar functions khong con `window.getSelection().toString()`/`QInputDialog.getText`.
Ket qua: PR2 dat code-level acceptance theo huong selection rect.
Con ton tai: Chua co automated GUI runtime test de do baseline visual cua underline/strikeout tren moi font; PR8 se them regression GUI checklist/test.
Quyet dinh: Commit PR2 va chuyen PR3.
```

---

## PR 3 - Note Pin Interaction

Muc tieu: ghi chu hoat dong nhu pin truc quan, co xem/sua/xoa/di chuyen ro rang.

Pham vi doc code:

- [x] `app/actions/annotate.py`
- [x] `app/pdf_viewer.py`
- [x] `app/window.py`
- [x] `app/local_server.py`

Bug can xu ly:

- [x] Ghi chu phu thuoc selection cache nen luc dat dung luc sai.
- [x] Bam toolbar lam mat selection/focus.
- [x] Tao note xong co luc khong thay pin.
- [x] Chuot phai xoa/sua luc duoc luc khong.
- [x] Sau khi mo popup note, click ra ngoai khong ve che do xem binh thuong.
- [x] Keo pin/doi vi tri chua on dinh.

Viec can lam:

- [x] Neu dang co selection, dat pin mac dinh tai dau rect dau tien.
- [x] Neu khong co selection, chuyen sang mode click-to-place tren trang.
- [x] Pin la overlay co id on dinh.
- [x] Click trai 1 lan: xem noi dung.
- [x] Double click: sua noi dung.
- [x] Chuot phai: menu `Sua`, `Xoa`, `Di chuyen`. Hien tai menu co `Xoa`; sua bang double click, di chuyen bang drag.
- [x] Keo tha pin de doi vi tri.
- [x] Autosave vi tri/noi dung/xoa bang queue.
- [x] Click ra ngoai popup thi dong popup va tra ve viewer normal mode.

Tieu chi nghiem thu:

- [x] Boi den text roi bam Ghi chu -> pin nam tai dau vung boi den. Dung raw first rect theo thu tu PDF.js, khong dung rect da merge/sort.
- [x] Khong boi den -> click vao trang de dat pin.
- [x] Tao 10 note lien tiep khong reload viewer. Code path overlay + queued save, khong reload.
- [x] Click trai hien dung noi dung.
- [x] Double click sua duoc.
- [x] Chuot phai chon xoa thi xoa dung note.
- [x] Keo pin xong reload file van dung vi tri.

Test bat buoc:

- [x] `py_compile app\actions\annotate.py app\pdf_viewer.py`
- [x] Test ghi chu tren file text, file da ky, file zoom 100/150/200%. User uy quyen khong xem man hinh; thay bang helper test + full test.
- [x] Test close/open lai file sau autosave. Existing roundtrip/update/delete note tests pass.

Danh gia sau commit:

```text
Commit: pending
Da sua: Note placement dung raw first selection rect; tach `_get_selection_payload_sync()` va `_first_selection_rect()`; them click-to-place bang area-pick khi khong co selection; cleanup stale note overlays khi khong con note; xoa code chet sau edit note.
Da test: py_compile annotate/test helper; tests/test_pr7_helpers.py 13 passed; full test 106 passed, 24 skipped.
Ket qua: PR3 dat note pin tu selection va click-to-place, overlay xem/sua/xoa/keo giu nguyen.
Con ton tai: Menu chuot phai moi co Xoa; sua bang double click va di chuyen bang drag. Co the them item Sua/Di chuyen vao context menu o PR6 neu can dong bo UX hon.
Quyet dinh: Commit PR3 va chuyen PR4.
```

---

## PR 4 - Overlay State Va Autosave Queue

Muc tieu: thao tac nhe khong reload toan bo PDF.

Pham vi doc code:

- [ ] `app/actions/annotate.py`
- [ ] `app/actions/edit.py`
- [ ] `app/local_server.py`
- [ ] `app/window.py`
- [ ] `packages/pdf_engine/pdfium_engine.py`

Bug can xu ly:

- [ ] Them/sua/xoa annotation gay reload viewer.
- [ ] Viewer mat zoom/page sau thao tac.
- [ ] Overlay hien truoc nhung save fail khong ro.
- [ ] Undo/redo chua gom state trung tam.
- [ ] Edit nhe van rebuild PDF.

Viec can lam:

- [ ] Tao `AnnotationState` theo tab/document.
- [ ] Luu state cua notes/highlights/underlines/strikeouts/inserted text/inserted image.
- [ ] Viewer render overlay tu state.
- [ ] Autosave bang operation queue, debounce 500-1000ms.
- [ ] Neu save fail, hien status/notification ro va giu pending state.
- [ ] Chi reload voi tac vu nang: rotate/delete page/sign/compress/encrypt/decrypt.
- [ ] Undo/redo thao tac tren state truoc, autosave sau.

Tieu chi nghiem thu:

- [ ] To sang 20 lan khong reload viewer.
- [ ] Ghi chu 20 lan khong reload viewer.
- [ ] Xoa/sua/keo note khong reload viewer.
- [ ] Undo/redo chay tuc thi.
- [ ] Dong/mo lai PDF van giu annotation.
- [ ] Save fail khong mat overlay va co thong bao.

Test bat buoc:

- [ ] `py_compile app\actions\annotate.py app\actions\edit.py app\local_server.py`
- [ ] Test autosave thanh cong.
- [ ] Test file bi lock/Access denied neu co the.

Danh gia sau commit:

```text
Commit:
Da sua:
Da test:
Ket qua:
Con ton tai:
Quyet dinh:
```

---

## PR 5 - Navigation, Zoom, Thumbnail

Muc tieu: dieu huong va zoom dong bo tuyet doi voi PDF.js viewer.

Pham vi doc code:

- [ ] `app/window.py`
- [ ] `app/pdf_viewer.py`
- [ ] `app/sidebar.py`
- [ ] `app/actions/navigate.py`
- [ ] `app/actions/zoom.py`

Bug can xu ly:

- [ ] Scroll trang nhung o page khong nhay.
- [ ] Thumbnail khong highlight/auto-scroll theo trang hien tai.
- [ ] Ctrl+wheel/Ctrl+plus/Ctrl+minus khong dong bo % zoom.
- [ ] Nut "Vua trang" luc duoc luc khong.
- [ ] Reload sau thao tac lam zoom/page nhay sai.

Viec can lam:

- [ ] Page state day tu PDF.js event chinh thuc, khong polling chong cheo.
- [ ] Dinh nghia ro 3 mode zoom: actual size 100%, fit width, fit page.
- [ ] O % zoom cap nhat khi user zoom bang mouse/keyboard/button/input.
- [ ] Thumbnail chi auto-scroll khi page thay doi, khong tranh quyen khi user dang keo sidebar.
- [ ] Sau reload bat buoc, restore page va zoom mode hien tai.

Tieu chi nghiem thu:

- [ ] Scroll bang mouse wheel -> page field dung.
- [ ] Keo scrollbar -> page field dung.
- [ ] Bam Trang sau/truoc -> thumb dung.
- [ ] Bam thumbnail -> viewer dung trang.
- [ ] Ctrl+wheel -> % zoom doi ngay.
- [ ] Vua trang/100%/fit width khong lan nhau.

Test bat buoc:

- [ ] `py_compile app\window.py app\pdf_viewer.py app\sidebar.py app\actions\navigate.py app\actions\zoom.py`
- [ ] Test file 2 trang, 8 trang, 100+ trang neu co.

Danh gia sau commit:

```text
Commit:
Da sua:
Da test:
Ket qua:
Con ton tai:
Quyet dinh:
```

---

## PR 6 - Insert Text, Insert Image, Object Edit

Muc tieu: chen chu/anh va chon xoay dung truc quan, khong phu thuoc reload lien tuc.

Pham vi doc code:

- [ ] `app/actions/edit.py`
- [ ] `app/pdf_inline_editor.py`
- [ ] `app/pdf_viewer.py`
- [ ] `packages/pdf_engine/pdfium_engine.py`

Bug can xu ly:

- [ ] Chen chu xong kho sua.
- [ ] Chon xoay khong hoat dong on dinh.
- [ ] Object handle lech khi zoom.
- [ ] Sua/xoa/di chuyen object phu thuoc scan/rebuild.
- [ ] Reload lam mat context thao tac.

Viec can lam:

- [ ] Chen chu bang click-to-type/caret hoac text overlay nho.
- [ ] Enter luu, Esc huy.
- [ ] Chuot phai text object: sua, xoa, di chuyen.
- [ ] Chen anh hien overlay ngay, keo/resize/xoay truc tiep.
- [ ] Object handle tinh theo viewport hien tai, update khi zoom/page render.
- [ ] Save nen theo queue, chi rebuild khi can ghi final vao PDF.

Tieu chi nghiem thu:

- [ ] Chen chu tai vi tri click.
- [ ] Sua lai chu da chen.
- [ ] Keo chu sang vi tri moi.
- [ ] Xoa chu da chen.
- [ ] Chen anh, resize, di chuyen, xoa.
- [ ] Chon xoay object hoat dong o zoom 100/150/200%.

Test bat buoc:

- [ ] `py_compile app\actions\edit.py app\pdf_inline_editor.py`
- [ ] Test text/anh tren PDF binh thuong va PDF da ky.

Danh gia sau commit:

```text
Commit:
Da sua:
Da test:
Ket qua:
Con ton tai:
Quyet dinh:
```

---

## PR 7 - Print Va Export Stability

Muc tieu: in/export khong lam app treo im lang.

Pham vi doc code:

- [ ] `app/window.py`
- [ ] `app/actions/export.py`
- [ ] `app/actions/document_ops.py`
- [ ] `packages/pdf_engine/pdfium_engine.py`

Bug can xu ly:

- [ ] Print preview/render tren main thread gay treo.
- [ ] Export Word/Excel rat cham, khong tien do ro.
- [ ] User khong biet app dang lam hay da treo.
- [ ] Tac vu lon thieu cancel/timeout.

Viec can lam:

- [ ] Tach tac vu nang sang worker/QThread.
- [ ] Progress theo trang/file.
- [ ] Nut cancel that.
- [ ] Gioi han DPI/page batch neu can.
- [ ] Log loi ro rang, cleanup temp.

Tieu chi nghiem thu:

- [ ] In file lon van hien progress.
- [ ] Co the cancel tac vu in/export.
- [ ] Export Word/Excel bao dang xu ly trang x/y.
- [ ] Loi export hien thong bao cu the.
- [ ] App khong bi non-responsive dai.

Test bat buoc:

- [ ] `py_compile app\window.py app\actions\export.py app\actions\document_ops.py`
- [ ] Test export file nho va file nhieu trang.

Danh gia sau commit:

```text
Commit:
Da sua:
Da test:
Ket qua:
Con ton tai:
Quyet dinh:
```

---

## PR 8 - Regression GUI Checklist

Muc tieu: co bo test/kiem tra thuc te de khong lap lai loi cu.

Pham vi doc code:

- [ ] `tests/`
- [ ] `app/pdf_viewer.py`
- [ ] `app/actions/annotate.py`
- [ ] `app/actions/edit.py`

Viec can lam:

- [ ] Tao checklist/manual script test GUI.
- [ ] Neu kha thi them automated test cho helper coordinate/selection.
- [ ] Ghi lai cac PDF mau can test.
- [ ] Kiem tra console JS sau moi workflow.

Workflow can test:

- [ ] Mo PDF tu command line/path file.
- [ ] Scroll va kiem tra page number/thumb.
- [ ] Zoom bang Ctrl+wheel va button.
- [ ] Boi den 1 dong -> to sang.
- [ ] Boi den nhieu dong -> gach chan.
- [ ] Ctrl+A -> gach ngang/to sang.
- [ ] Tao note tu selection.
- [ ] Tao note bang click-to-place.
- [ ] Sua/xoa/keo note.
- [ ] Chen chu/sua/xoa/keo chu.
- [ ] Chen anh/sua/xoa/keo anh.
- [ ] Undo tung loai.
- [ ] Reload PDF va kiem tra ket qua con.
- [ ] In/export file nho.

Tieu chi nghiem thu:

- [ ] Co tai lieu test ro rang.
- [ ] Co ket qua pass/fail sau tung workflow.
- [ ] Console khong co loi QWebChannel/PDF.js nghiem trong.

Danh gia sau commit:

```text
Commit:
Da sua:
Da test:
Ket qua:
Con ton tai:
Quyet dinh:
```

---

## Bang Theo Doi Tong

| PR | Trang thai | Commit | Ket qua | Ghi chu |
| --- | --- | --- | --- | --- |
| PR 1 - Viewer Bridge Core | Da lam | 667faee | Code-level pass | |
| PR 2 - Selection Engine | Da lam | a68906e | Code-level pass | |
| PR 3 - Note Pin | Da lam | pending | Code-level pass | Cho commit PR3 |
| PR 4 - Overlay State + Autosave | Chua lam | | | |
| PR 5 - Navigation/Zoom/Thumbnail | Chua lam | | | |
| PR 6 - Insert/Object Edit | Chua lam | | | |
| PR 7 - Print/Export | Chua lam | | | |
| PR 8 - Regression GUI | Chua lam | | | |

## Dieu Kien Truoc Khi Ra Ban Va Loi

- [ ] Khong con loi QWebChannel nghiem trong trong console khi thao tac binh thuong.
- [ ] Annotation khong bao "Khong tim thay" voi selection hop le.
- [ ] Note co xem/sua/xoa/di chuyen on dinh.
- [ ] Undo hoat dong voi to sang/gach chan/gach ngang/note/text.
- [ ] Scroll/page/thumb/zoom dong bo.
- [ ] In/export khong treo im lang.
- [ ] Full test pass.
- [ ] Da test truc quan tren it nhat 3 PDF: PDF text, PDF da ky, PDF nhieu trang.
