# Phase 0 Progress Report

Date: 2026-05-19

Scope: nền chung cho Windows và macOS, chưa chia luồng Windows/macOS/VPS.

## Mục tiêu Phase 0

- Giữ một lõi chung cho cả Windows và macOS.
- Loại bỏ hardcode và giả định Windows khỏi phần `shared`.
- Cô lập các điểm phụ thuộc OS vào adapter riêng.
- Chuẩn bị nền thương mại hóa: license, compliance, PDF engine, signing boundary, update/license backend skeleton.
- Không chia repo thành 3 luồng riêng trong Phase 0.

## Đã hoàn thiện trong Phase 0

### 1) Làm sạch và chuẩn hóa source

- Dọn workspace khỏi artifact nặng và file rác.
- Loại `venv`, `dist`, `build`, cache, temp, `.agents`.
- Chuẩn hóa brand sang `3T Reader`.
- Cấu trúc lại repo theo hướng commercial foundation.

### 2) Tách lớp nền platform

- Tạo boundary cho single-instance.
- Tách path app data/cache/log/recent sang module platform.
- Chuẩn bị để Windows và macOS dùng cùng API nền, không phụ thuộc logic UI.

### 3) Tách PDF engine khỏi UI

- Đưa thao tác PDF qua `pdf_engine` abstraction.
- Cô lập PyMuPDF vào legacy path.
- Chuyển default engine sang `PdfiumEngine`.
- Dùng `pypdfium2`, `pikepdf`, `reportlab` cho luồng không AGPL.

### 4) Bỏ wrapper GPL cho PDF viewer

- Loại `pdfjs-viewer-pyqt6` khỏi app code.
- Dựng viewer nội bộ dùng PDF.js trực tiếp qua `QWebEngineView`.
- Tách khỏi phụ thuộc wrapper GPL để phù hợp hướng thương mại.

### 5) Chuyển UI compat sang PySide6

- Bỏ import trực tiếp `PyQt6` trong app.
- Tạo `qt_compat` để app đi qua một lớp chung.
- Định hướng UI chung cho Windows và macOS, không tách giao diện theo nền tảng.

### 6) Tách signing boundary

- Bỏ `PyKCS11` khỏi primary signing path.
- Dùng `python-pkcs11` làm đường chính.
- Tạo `SigningProvider` protocol và provider adapter.
- Giữ flow UI ký số đi qua abstraction, không gọi thẳng implementation.

### 7) Compliance và license scaffolding

- Thêm manifest third-party, risk register, asset source docs.
- Thêm docs cho migration PDF engine, signing, dependency strategy.
- Có khung `NOTICE`, `LICENSES`, và tài liệu blocker/compliance.

### 8) Skeleton cho backend license/update

- Tạo khung `license_client`.
- Tạo khung `update_client`.
- Đặt nền cho Linux VPS backend, nhưng chưa triển khai thật.

## Đã làm đúng hướng yêu cầu chi tiết

- Nền chung cho Windows và macOS, không phải Windows-first rồi vá mac sau.
- Shared code không nên chứa hardcode Windows.
- OS-specific behavior phải đi qua adapter.
- UI/UX và workflow phải giữ nhất quán giữa hai nền.
- Linux VPS chỉ là backend chung cho license/update/audit về sau.

## Còn thiếu để chốt Phase 0

### 1) Bóc hết hardcode Windows khỏi phần shared

- `core/pkcs11.py` còn dò `System32` và `SysWOW64`.
- Phần stamp font vẫn còn giả định `C:\Windows\Fonts`.
- Các chỗ này phải được đưa sang adapter theo OS.

### 2) Hoàn thiện signing provider theo OS

- Windows provider: dò `.dll` và middleware vendor trên Windows.
- macOS provider: dò `.dylib`/`.so` và middleware vendor trên macOS.
- Shared layer chỉ giữ API `SigningProvider`.

### 3) Chuẩn hóa font và stamp path cho macOS

- Không được hardcode font path theo Windows trong logic chung.
- Cần font resolution theo OS hoặc font bundle trung tính.

### 4) Chốt compliance artifacts

- Pin nguồn PDF.js official release/tag.
- Chốt SBOM/license table cuối cho từng dependency và asset.
- Làm rõ source/version/license của icon, fonts, and third-party bundles.

### 5) Smoke test trên macOS

- Mở app được.
- Load PDF được.
- Render page được.
- Search/print cơ bản hoạt động.
- Signing flow không đụng Windows-only assumption.

### 6) Smoke test trên Windows sau khi tách shared

- Đảm bảo Windows vẫn giữ được flow hiện tại.
- Kiểm tra rằng adapter Windows vẫn đọc token middleware và font đúng.

### 7) Ghi nhận phase gate

- Chỉ sang chia luồng Windows/macOS/VPS khi shared đã sạch OS và compliance đủ rõ.

## Kết luận

Phase 0 hiện đã xong phần lớn nền kiến trúc và license-risk lớn.
Tuy nhiên, Phase 0 chưa thể coi là chốt nếu `shared` vẫn còn giả định Windows trong signing/font lookup.

Điểm còn lại là làm sạch hết giả định Windows khỏi lõi chung, rồi mới cho phép bước sang phase split Windows/macOS/VPS.
