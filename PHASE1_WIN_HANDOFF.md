# Phase 1 Windows Handoff

Tài liệu này là điểm vào nhanh cho người tiếp tục làm việc trên `phase1-win`.
Mục tiêu là đọc xong có thể biết ngay:

- hiện trạng Windows stream đang ở đâu
- phần nào đã xong
- phần nào còn thiếu
- phải làm tiếp theo thứ tự nào
- khi nào được phép chốt `phase1-win-ready`

## 1. Mục tiêu stream

`phase1-win` không còn là “PDF viewer thử nghiệm” nữa. Mục tiêu thực tế của stream này là:

- chạy ổn trên Windows
- mở / xem / search / in / search thumbnail / tab / recent files
- PDF rendering qua PDF.js đã hoạt động
- installer Windows build được
- USB token / PKCS#11 detect được
- ký số Windows đi được với token thật
- giao diện đủ trực quan để người dùng thao tác cơ bản

## 2. Trạng thái hiện tại

### Đã xong

- PDF.js render trên Windows đã chạy.
- JavaScript MIME fix cho `.mjs` đã có trong local PDF server.
- Windows PKCS#11 provider có `THREET_READER_WINDOWS_PKCS11_PATHS`.
- Windows mutex single-instance dùng `Local\...`.
- PyInstaller spec và Inno Setup script đã build được trên máy này.
- Smoke test Windows pass: `26 passed, 1 skipped`.
- Packaged app launch được từ `dist\3T_Reader\3T_Reader.exe`.

### Chưa xong

- USB token thật chưa test với middleware của nhà cung cấp.
- Chưa có một vòng install/uninstall end-to-end chính thức sau build.
- `phase1-win-ready` chưa được phép đánh dấu.

## 3. Quy tắc làm tiếp

### Phạm vi đúng của Windows stream

- Chỉ sửa những gì thuộc Windows desktop stream.
- Không trộn macOS behavior vào nhánh Windows.
- Không kéo backend/VPS vào nhánh Windows nếu chưa có lý do rõ.
- Shared change thì phải giữ API dùng chung, không viết lối riêng cho Windows nếu sau đó macOS phải lặp lại.

### Cách đọc trạng thái

- `docs/PHASE1_WIN_STATUS.md` là bảng trạng thái ngắn.
- `docs/WORKFLOW_CONVENTION.md` là luật branch/workspace/tag.
- `docs/PHASE1_3_STREAM_PLAN.md` là khung đường đi tổng thể.
- Tài liệu này là handoff thực dụng để tiếp tục công việc ngay.

## 4. Việc cần làm tiếp theo

Ưu tiên theo thứ tự:

1. Test USB token thật trên máy Windows có middleware nhà cung cấp.
2. Chạy một vòng cài đặt / gỡ cài đặt từ `build\installer\Setup_3T_Reader_v1.0.2.exe`.
3. Nếu cần release hơn nữa, chốt lại checklist compliance / notices / branding.
4. Nếu còn tiếp tục polish UI, chỉ làm những điểm ảnh hưởng trực tiếp đến dùng thật.

## 5. Các điểm còn dư kỹ thuật

Những điểm này đã biết rõ, không cần mò lại từ đầu:

- `docs/PHASE1_WIN_STATUS.md` vẫn nói blocker còn lại là token thật.
- `docs/WORKFLOW_CONVENTION.md` yêu cầu phase tag là snapshot, không phải branch.
- `docs/PHASE1_DUAL_MACHINE_WORKFLOW.md` và `docs/PHASE1_3_STREAM_PLAN.md` là nguồn cho split Win/Mac/Shared/Backend.

## 6. Nếu bạn đang tiếp tục phần UI edit

Nếu mục tiêu là hoàn thiện cụm `chèn/sửa/xóa` trong app:

- giữ object đã chèn ở trạng thái chọn được
- sửa vị trí / kích thước / xoay / nội dung từ một panel thống nhất
- không giữ nhiều popup chồng chéo
- text cần sửa được font tiếng Việt, đậm, gạch chân
- ảnh cần có stage tạm để không phụ thuộc path gốc
- thao tác phải nhìn ra ngay trên toolbar hoặc inspector, không đoán trạng thái

## 7. Kiểm tra trước khi chốt

Trước khi coi Windows stream xong, cần tối thiểu:

- `python -m pytest -q tests/test_smoke_platform.py`
- build PyInstaller pass
- Inno Setup pass
- mở app packaged pass
- test token thật pass

## 8. Khi nào được tag `phase1-win-ready`

Chỉ tag khi:

- token thật đã kiểm chứng
- signing flow đã đi qua máy Windows thật
- build/installer đã qua vòng release smoke cuối
- docs không còn nói blocker chính

## 9. File liên quan

- [PHASE1_WIN_STATUS.md](PHASE1_WIN_STATUS.md)
- [WORKFLOW_CONVENTION.md](WORKFLOW_CONVENTION.md)
- [PHASE1_DUAL_MACHINE_WORKFLOW.md](PHASE1_DUAL_MACHINE_WORKFLOW.md)
- [PHASE1_3_STREAM_PLAN.md](PHASE1_3_STREAM_PLAN.md)

