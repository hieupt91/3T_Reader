# 3T Reader — macOS → Windows feature handoff

Ngày cập nhật: 2026-08-15  
Nhánh nguồn: `phase1-mac`  
Nhánh đích: `phase1-win`

## Mục tiêu

Tài liệu này là checklist để team Windows đối chiếu toàn bộ khả năng hiện có trên macOS trước khi triển khai parity. Không copy nguyên workspace macOS sang Windows; chỉ merge các phần dùng chung và port adapter theo từng nhóm.

## Tính năng đang có trên `phase1-mac`

- PDF core: mở, nhiều tab, recent files, tìm kiếm, thumbnail, bookmark/TOC, zoom, fit page/width, chuyển trang, xoay, fullscreen và in.
- Chỉnh sửa PDF: chèn text, chèn ảnh/PNG, kéo-thả/đổi kích thước/xoay object, vẽ, highlight, underline, strikeout, redact, comment, watermark, đánh số trang, undo, xóa/tách/trích xuất/gộp trang, nén và đặt/gỡ mật khẩu.
- Xuất tài liệu: PDF → ảnh, text, Word và Excel.
- OCR: OCR một trang hoặc toàn tài liệu, hỗ trợ tiếng Việt và dialog tiến trình.
- AI: dịch, tóm tắt, chat với PDF, semantic search, chọn provider và Ollama local.
- Ký số: USB token PKCS#11, PFX/P12, tạo signature field, chữ ký viết tay/stamp, preview vị trí ký và kiểm tra chữ ký.
- License: trial, activate/deactivate, heartbeat, offline grace, device fingerprint, xác minh Ed25519, Keychain trên macOS.
- Update: kiểm tra bản mới, tải có tiến trình, kiểm SHA-256/manifest chữ ký.
- Ngôn ngữ: language manager, language pack từ VPS và fallback chuỗi tích hợp.
- Audit: ghi/xem/lọc/xuất nhật ký thao tác.
- UI: ribbon kiểu Word/Excel, theme sáng/tối, icon theo theme, sidebar, welcome/about và shortcut theo nền tảng.
- Companion transfer: ghép nối thiết bị, tạo/hiển thị QR, gửi/nhận tài liệu qua WebRTC/DataChannel, thông báo thành công/lỗi rõ ràng.

## Phần Windows cần đối chiếu

1. Port UI/action dùng chung từ `app/actions/*`, `app/window.py`, `app/ribbon_bar.py` và `app/pdf_inline_editor.py`.
2. Giữ nguyên contract của `packages/pdf_engine`, `packages/license_client`, `packages/ai`, `packages/transfer`.
3. Chỉ thay adapter Windows cho font, đường dẫn, mutex, Credential Manager, PKCS#11 `.dll`, installer và update installer.
4. Test riêng trên Windows thật: PDF.js/WebEngine, inline editor, OCR tiếng Việt, Word/Excel export, USB token/middleware, license activation, update và transfer.
5. Không đưa hành vi macOS (Keychain, `.dylib`, `.app`, notarization, native menu) vào Windows branch.

## Cách review và lấy thay đổi

```bash
git fetch origin
git checkout phase1-win
git diff --stat origin/phase1-win..origin/phase1-mac
git log --oneline origin/phase1-win..origin/phase1-mac
```

Merge theo nhóm, ưu tiên shared trước:

```bash
git checkout phase1-win
git merge --no-ff origin/phase1-shared
# sau khi review từng nhóm mac-specific/shared:
git merge --no-ff origin/phase1-mac
```

Nếu muốn thử nghiệm trước khi merge chính thức, tạo branch:

```bash
git checkout -b win-mac-parity-review origin/phase1-win
git merge --no-commit origin/phase1-mac
```

## Trạng thái và blocker cần xác nhận

- Windows smoke test trong handoff hiện có: `26 passed, 1 skipped`.
- Cần test USB token thật với middleware nhà cung cấp trên Windows.
- Cần test cài/gỡ installer end-to-end trên máy Windows.
- Cần kiểm tra đủ dependency của OCR, Word/Excel export và AI provider trong bản đóng gói.
- Các thư mục `piper_*` và `debug/` trên máy Mac là artifact cục bộ, không thuộc commit bàn giao.

## Snapshot nguồn

Snapshot hiện tại của `phase1-mac` được push trên remote `origin`. Team Windows nên review commit range bằng lệnh ở trên và ghi kết quả port/test vào `PHASE1_WIN_STATUS.md`.
