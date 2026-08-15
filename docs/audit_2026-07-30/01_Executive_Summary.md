# 01 — Executive Summary

**Dự án**: 3T Reader Phase 1 Windows (`C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win`)
**Loại audit**: Enterprise software audit toàn diện (kiến trúc, code quality, UI/UX, hiệu năng, bảo mật, dependency, technical debt) — chỉ điều tra, không sửa code.
**Ngày**: 2026-07-30
**Phạm vi**: 847 file tracked trong git, ~55.000 dòng code Python (app/ + packages/ + tests/ + root scripts).

> **Lưu ý về checklist gốc**: bộ checklist người dùng cung cấp được viết cho ứng dụng mobile/Flutter (nhắc tới "widgets", "Tablet/Landscape issues", "Touch targets"). Đây là ứng dụng desktop Windows dùng PySide6/Qt, điều khiển bằng chuột+bàn phím. Các báo cáo dưới đây đã map lại các mục đó thành N/A kèm lý do, thay vì bịa phát hiện.

## Bức tranh tổng thể

3T Reader là 1 app đọc/sửa PDF thương mại cho thị trường Việt Nam, kiến trúc PySide6 + QWebEngineView (chạy PDF.js), engine PDF dùng pypdfium2/pikepdf, ký số qua PKCS11/PFX, OCR qua Tesseract, AI đa nhà cung cấp, license qua VPS backend riêng. Đây là sản phẩm 1 người/nhóm nhỏ phát triển, không phải codebase doanh nghiệp nhiều đội — điều này ảnh hưởng cách đánh giá mức độ ưu tiên: nợ kỹ thuật kiến trúc (god-object, coupling chặt) là có thật nhưng KHÔNG khẩn cấp bằng crash/bảo mật/pháp lý.

## Đã xử lý trong phiên làm việc này (trước khi audit này chạy)

Trước khi audit toàn diện này được yêu cầu, phiên làm việc đã tìm và **sửa xong, đã deploy lên production (bản 1.0.27)**:

| # | Vấn đề | Trạng thái |
|---|---|---|
| A1 | Crash native (access violation) khi ghi đè file PDF lúc thumbnail đang render nền | ✅ Đã sửa |
| A2 | `QThread.terminate()` gây rủi ro crash khi hủy tải LibreOffice | ✅ Đã sửa |
| B1/B2 | Quét PKCS11 đồng bộ trên UI thread gây lag ký số + mở file có ô ký số | ✅ Đã sửa |
| B4 | Đọc outline PDF đồng bộ gây lag khi mở file có mục lục lớn | ✅ Đã sửa |
| D1 | Icon PDF không đổi ở chế độ Details trong Explorer | ✅ Đã sửa |
| — | Module bị PyInstaller bỏ sót khi đóng gói (gây `ModuleNotFoundError` ngay khi mở app) | ✅ Đã sửa |
| — | OCR nền bỏ qua lỗi từng trang im lặng | ✅ Đã sửa |
| — | Watermark nhiều trang chặn UI thread | ✅ Đã sửa |
| — | `QThread.terminate()` trùng lỗi A2 ở luồng tải iTaxViewer | ✅ Đã sửa |
| — | API key AI mã hóa bằng key suy ra được (MachineGuid+USERNAME) | ✅ Đã sửa (chuyển sang Windows Credential Manager) |
| — | Bộ cài iTaxViewer không kiểm tra checksum | ✅ Đã sửa (client-side, cần VPS publish sidecar hash để kích hoạt thật) |

Các mục này **không được liệt kê lại** là "cần sửa" trong báo cáo bug/risk dưới đây, chỉ xuất hiện trong `09_Technical_Debt.md`/`10_Bug_List.md` dưới dạng "đã đóng" để có dấu vết.

## Phát hiện MỚI quan trọng nhất từ audit này (chưa xử lý)

| Mức độ | Phát hiện | Chi tiết |
|---|---|---|
| 🔴 **Critical — pháp lý** | **PyMuPDF (AGPL-3.0) đang bị đóng gói kèm bản 1.0.27 vừa deploy production** | `app/actions/edit.py:2356,2570` dùng `fitz.open()` thật trong tính năng "Sửa text gốc". Dự án tự ghi nhận đã "gỡ PyMuPDF vì AGPL" nhưng thực tế chưa gỡ hết. **Đây là quyết định pháp lý/kinh doanh, người dùng đã yêu cầu ghi nhận vào báo cáo, chưa xử lý.** Xem `07_Security_Report.md` §C1, `08_Dependency_Report.md` §C1. |
| 🟠 High | 2 nhà cung cấp AI (Gemini, HuggingFace) không hoạt động được trong bản đã đóng gói — thiếu thư viện dù `3T_Reader.spec` có khai hiddenimports | `08_Dependency_Report.md` §H1 |
| 🟠 High | Ghi file PDF không được khóa đồng bộ nhất quán — `sign.py`/`edit.py`/`document_ops.py` không dùng chung `_PDF_SAVE_LOCK` mà `annotate.py`/`pages.py` dùng → nguy cơ mất dữ liệu âm thầm (last-writer-wins) nếu 2 thao tác ghi đè lên nhau trong vài trăm ms | `10_Bug_List.md` §1 |
| 🟠 High | 3 dialog (License, OCR, Audit-log) hard-code màu dark-mode, không có nhánh light-mode → hiện bảng màu tối giữa giao diện sáng | `05_UI_UX_Report.md` §1 |
| 🟠 High | Vòng lặp chờ cài iTaxViewer không có timeout/nút hủy — cài đặt bên thứ 3 treo sẽ khóa app không lối thoát trong app | `10_Bug_List.md` §3 |
| 🟡 Medium | Cache token PKCS11 là singleton không khóa, đọc/ghi từ 2 thread — rủi ro chọn nhầm token khi cắm nhiều USB ký số | `10_Bug_List.md` §2 |
| 🟡 Medium | Dependency `pyqtdarktheme` khai báo nhưng không dùng ở đâu; `pyproject.toml` version lệch với `app/version.py` | `08_Dependency_Report.md` §M1, §M2 |

## Điểm sức khỏe tổng thể

Xem chi tiết từng hạng mục ở `14_Project_Health_Score.md`. Tóm tắt: **65/100** — sản phẩm hoạt động ổn định cho quy mô hiện tại, các lỗi crash nghiêm trọng nhất đã được xử lý trong phiên này, nhưng có 1 rủi ro pháp lý thật (AGPL) và nợ kiến trúc tích lũy (god-object `window.py`) cần kế hoạch riêng, không phải vá vội. Nếu loại trừ accessibility (chưa phải ưu tiên thị trường) và AGPL (quyết định business, không phải lỗ hổng kỹ thuật), điểm sức khỏe kỹ thuật thuần túy ước tính **~70-75/100**.

## Khuyến nghị ưu tiên ngay

1. **Quyết định hướng xử lý PyMuPDF/AGPL** (mua license Artifex, hoặc thay bằng pypdfium2/pikepdf đã có sẵn trong app) — đây là việc duy nhất có rủi ro pháp lý thật trong toàn bộ audit.
2. Xem `12_Fix_Roadmap.md` cho lộ trình 5 sprint theo mức độ ưu tiên.
