# Yêu cầu bàn giao Windows 1.0.32 → team macOS

Ngày yêu cầu: 2026-08-15  
Người nhận: team Windows / owner bản Windows 1.0.32  
Nhánh Mac đang chờ: `phase1-mac`

## Phát hiện hiện tại

Remote `origin/phase1-win` hiện đang trỏ tới commit `cd61e3c` và
`app/version.py` là `1.0.7`. Chưa có snapshot Windows `1.0.32` trong nhánh
này để team Mac có thể audit đầy đủ.

## Đề nghị team Windows chia sẻ một snapshot hoàn chỉnh

Vui lòng push một branch hoặc tag bất biến, ví dụ:

```text
phase1-win-1.0.32
```

Snapshot phải bao gồm toàn bộ source và lịch sử thay đổi đến đúng bản 1.0.32,
không chỉ các file đã chọn. Sau khi push, gửi commit SHA và cập nhật bảng dưới.

## Gói bàn giao bắt buộc

1. Source code, assets, installer/spec và dependency lock đúng bản 1.0.32.
2. Danh sách feature/capability đầy đủ từ Windows UI: ribbon, menu, context
   menu, dialog, shortcut, drag/drop, settings và các entry point ẩn.
3. Workflow end-to-end: mở/sửa/lưu/reopen, page operations, OCR, AI, export,
   in, ký số, license, update, transfer và mọi trạng thái lỗi/loading/cancel.
4. Test evidence: lệnh test, kết quả, fixture đầu vào, output sau khi mở lại,
   screenshot/video cho control khó quan sát và log lỗi/retry.
5. Ma trận version/dependency: Python, Qt, PDF engine, OCR, AI provider,
   PKCS#11 middleware, installer và runtime asset.
6. Các thay đổi bảo mật/compliance: license verification, update SHA-256 +
   Ed25519, third-party notices, signing và installer integrity.
7. Danh sách Windows-only behavior và lý do được phê duyệt; không tự loại bỏ
   feature khi port sang Mac.

## Format phản hồi đề nghị

| ID | Windows 1.0.32 capability | UI/entry point | Source files | Test evidence | Mac status | Port owner |
|---|---|---|---|---|---|---|
| W32-001 | | | | | `MISSING/PARTIAL/PASS` | |

Team Mac sẽ dùng snapshot này làm master reference để cập nhật:

- `docs/parity_audit/FEATURE_PARITY_REPORT.md`
- `docs/parity_audit/UI_UX_PARITY_REPORT.md`
- `docs/parity_audit/WORKFLOW_PARITY_REPORT.md`
- `docs/parity_audit/SETTINGS_PARITY_REPORT.md`
- `docs/parity_audit/SHORTCUT_PARITY_REPORT.md`
- `docs/parity_audit/MISSING_FEATURES.md`

## Điều kiện hoàn tất bàn giao

- Branch/tag Windows 1.0.32 tồn tại trên remote và clone được từ máy sạch.
- Commit SHA, version/build number và checksum installer được cung cấp.
- Bảng capability không còn ô trống cho các feature Windows đang phát hành.
- Mọi feature chưa port sang Mac được ghi rõ status, severity, owner, kế hoạch
  implement và tiêu chí retest.
- Không bật rollout delta Mac hoặc thay đổi API v1 chỉ vì thiếu snapshot.

Đề nghị team Windows phản hồi trực tiếp trên commit/PR chứa tài liệu này và
push snapshot 1.0.32 trước khi team Mac chốt parity audit.
