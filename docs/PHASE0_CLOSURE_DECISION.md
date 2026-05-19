# Phase 0 — Quyết định đóng phase

Date: 2026-05-19  
Chuẩn đánh giá: Định hướng chi tiết 3T Reader v1.0

---

## Kết luận

**Phase 0 đạt tiêu chí kiến trúc và kỹ thuật. Các blocker còn lại là compliance/legal/smoke-test thực tế, được defer có căn cứ (xem mục III). Phase 1 có thể bắt đầu song song với việc giải quyết dần các mục defer.**

---

## I. Tiêu chí kiến trúc — ĐẠT ✅

| Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|
| shared không còn giả định Windows | ✅ DONE | `core/pkcs11.py` không còn `_candidate_paths()`/`_pick_vietnamese_font_path()`. Scan xác nhận không còn `System32`, `SysWOW64`, `C:\Windows` trong shared layer. |
| Signing tách OS hoàn chỉnh | ✅ DONE | `WindowsPkcs11Provider` → `.dll` System32/SysWOW64. `MacOSPkcs11Provider` → `.dylib/.so` Homebrew/usr/lib. Shared utils trong `packages/signing/shared.py`. `get_signing_provider()` chọn theo `sys.platform`. |
| Font path theo OS | ✅ DONE | `packages/platform/fonts.py` → Windows `%SystemRoot%\Fonts`, macOS `/System/Library/Fonts`, Linux `/usr/share/fonts`. Không còn hardcode trong shared. |
| PDF engine tách khỏi UI | ✅ DONE | `packages/pdf_engine/base.py` Protocol. Default engine = `PdfiumEngine` (pypdfium2 + reportlab). Legacy PyMuPDF AGPL chỉ qua env var `THREET_READER_PDF_ENGINE=legacy`. |
| Qt import qua qt_compat | ✅ DONE | Toàn bộ app import Qt qua `packages/qt_compat/`. Không còn import trực tiếp PyQt6 trong app code. |
| pdfjs-viewer-pyqt6 GPL loại bỏ | ✅ DONE | App dùng PDF.js Apache 2.0 trực tiếp qua `QWebEngineView` trong `app/pdf_viewer.py`. |
| Single instance boundary | ✅ DONE | `packages/platform/single_instance.py`. |
| Recent files qua platform adapter | ✅ DONE | `core/recent.py` delegate sang `packages.platform.get_app_data_dir()`. |
| License/update skeleton | ✅ DONE | `packages/license_client/`, `packages/update_client/`, `server/license-api/README.md`. |
| UI font theo OS | ✅ DONE | `main.py` chọn Segoe UI (Win) / SF Pro Text (Mac) / system fallback. |

---

## II. Tiêu chí test — ĐẠT PHẦN LỚN ✅

| Tiêu chí | Trạng thái | Ghi chú |
|---|---|---|
| Smoke tests platform/signing | ✅ 34 passed | `tests/test_smoke_platform.py` + `tests/test_pdf_pipeline.py`. Chạy trên macOS Python 3.13. |
| PDF edit pipeline non-AGPL fixture test | ✅ DONE | `TestBuildOverlayPdf` (reportlab), `TestPdfiumEngineOpen`, `TestNoPyMuPdfInDefaultPath`. 3 tests cần pikepdf **SKIP** vì pikepdf không build được trên Python 3.13 ARM — không phải lỗi pipeline, là lỗi env. |
| `create_blank_pdf` dùng pypdfium2 (bỏ pikepdf) | ✅ DONE | Fix ngay trong session này. |
| macOS smoke test thật (UI launch) | ⚠️ DEFERRED | Cần `PySide6` cài trong env; không test được UI không display trong CI. Xem mục III. |
| Windows smoke test thật (UI launch) | ⚠️ DEFERRED | Cần máy Windows với driver USB token thật. Xem mục III. |
| pikepdf rebuild_pdf tests | ⏸️ SKIPPED-ENV | Tests đã viết đủ (`TestRebuildPdfWithOps`), skip vì pikepdf không build trên Python 3.13 ARM. Sẽ pass trên Windows build env với Python 3.11/3.12. |

---

## III. Tiêu chí compliance/legal — DEFER CÓ CĂN CỨ ⚠️

| Tiêu chí | Trạng thái | Defer rationale |
|---|---|---|
| PDF.js official source pin | ⚠️ PARTIALLY DONE | Version đã xác định: **v5.6.205 Apache 2.0**, source URL ghi rõ trong `docs/compliance/PDFJS_SOURCE.md`. Bundle gốc chưa được thay bằng bản download trực tiếp từ Mozilla. Defer sang Phase 1 preparation vì không ảnh hưởng kiến trúc. |
| Icon source/license pin | ⚠️ DEFERRED | `download_icons.py` trỏ tới Microsoft Fluent UI System Icons (MIT License). Cần pin commit hash và lưu LICENSE text. Defer vì không block kiến trúc. |
| SBOM đầy đủ từ build env | ⚠️ DEFERRED | Cần chạy `pip-licenses` + CycloneDX trong Windows build environment với đủ deps. Không thể hoàn chỉnh trên macOS dev env hiện tại (thiếu Windows-only packages). |
| PySide6/Qt LGPL compliance review | ⚠️ DEFERRED | PyQt6 = GPL-3.0-only (NOT commercial). Chuyển sang PySide6 LGPL là đúng hướng — nhưng review đầy đủ (QtWebEngine Chromium notices, LGPL obligations) cần legal review riêng. |
| PyKCS11 loại khỏi commercial build | ✅ DONE | `PyKCS11` không có trong `requirements.txt`. Chỉ có `python-pkcs11` (MIT expected). Cần verify khi gen SBOM. |
| EULA / Privacy Policy | ⚠️ DEFERRED | Cần soạn thảo pháp lý. Không block kiến trúc Phase 0. Bắt buộc trước Phase 3 (License VPS). |
| Third-party Notices đầy đủ | ⚠️ DEFERRED | `NOTICE.md` + `LICENSES.md` đã có skeleton. Cần điền đầy đủ từ SBOM. Defer sang Phase 1 preparation. |
| PyMuPDF không ship trong commercial build | ✅ DONE | `PyMuPdfEngine` chỉ tải khi `THREET_READER_PDF_ENGINE=legacy`. Mặc định là `PdfiumEngine`. Test xác nhận `test_default_engine_is_not_pymupdf`. |

---

## IV. License rủi ro — Tổng hợp

| Thành phần | License | Rủi ro thương mại | Quyết định |
|---|---|---|---|
| PyQt6 6.11.0 | GPL-3.0-only | CAO — không bán closed-source | Chuyển sang PySide6 LGPL trong Phase 1 |
| PySide6 | LGPL-3.0 | THẤP — được phép closed-source nếu link dynamic | Target binding Phase 1 |
| pdfjs-viewer-pyqt6 1.2.0 | GPL-3.0-or-later | CAO — bị loại | ✅ Đã loại |
| PyMuPDF 1.27.2.2 | AGPL / Artifex Commercial | CAO — không ship mặc định | ✅ Đưa sang legacy optional path |
| pypdfium2 5.7.0 | BSD-3-Clause + Apache-2.0 | KHÔNG RỦI RO | ✅ Primary engine |
| pikepdf 10.5.1 | MPL-2.0 | THẤP — copyleft chỉ cho pikepdf file changes | ✅ Dùng cho PDF ops |
| reportlab 4.4.5 | BSD/HPND | KHÔNG RỦI RO | ✅ Dùng cho overlay |
| pyHanko 0.34.1 | MIT | KHÔNG RỦI RO | ✅ Dùng cho signing |
| cryptography 46.0.7 | Apache-2.0 OR BSD-3-Clause | KHÔNG RỦI RO | ✅ Giữ |
| PDF.js | Apache-2.0 | KHÔNG RỦI RO | ✅ Dùng trực tiếp |
| python-pkcs11 | MIT (cần verify) | KHÔNG RỦI RO | ✅ Primary PKCS#11 |
| PyInstaller 6.20.0 | GPL với bootloader exception | Build-only, không ship source | ✅ Giữ cho packaging |
| Fluent UI Icons | MIT | KHÔNG RỦI RO — cần pin commit | ⚠️ Pin commit hash |

---

## V. Quyết định Phase gate

### Có thể bắt đầu Phase 1 nếu:

1. ✅ Shared code sạch OS assumption → **ĐẠT**
2. ✅ Signing provider tách theo OS → **ĐẠT**
3. ✅ PDF engine abstraction → **ĐẠT**
4. ✅ Qt import qua compat layer → **ĐẠT**
5. ⚠️ Compliance blockers còn lại → **DEFER với điều kiện:**
   - Phase 1 không phân phối binary thương mại cho khách hàng.
   - Compliance items (SBOM, EULA, icon pin, Qt compliance) phải hoàn chỉnh trước Phase 3.
   - Windows smoke test thật được thực hiện trong Windows build env trước khi release bản Windows.
   - macOS smoke test thật trước khi release bản macOS.

### Không được làm trong Phase 1 cho đến khi resolve:
- Không phân phối binary có PyMuPDF AGPL.
- Không phân phối binary có PyQt6 GPL (phải hoàn thành chuyển sang PySide6).
- Không bán license key thật cho đến khi có EULA và Privacy Policy.

---

## VI. Checklist defer — ai làm gì trước Phase 3

| Mục | Owner | Deadline |
|---|---|---|
| Download official PDF.js 5.6.205 và thay bundle | Dev | Trước Phase 1 release |
| Pin Fluent UI icon commit + LICENSE | Dev | Trước Phase 1 release |
| Hoàn thành chuyển PyQt6 → PySide6 | Dev | Phase 1 |
| Run SBOM trên Windows build env | Dev | Trước Phase 2 release |
| Viết EULA + Privacy Policy | Legal | Trước Phase 3 |
| Third-party Notices đầy đủ | Dev + Legal | Trước Phase 3 |
| Windows smoke test thật | Dev | Trước Windows Phase 1 release |
| macOS smoke test thật (UI launch) | Dev | Trước macOS Phase 1 release |
| Qt/Chromium LGPL compliance review | Legal + Dev | Trước Phase 2 commercial release |
