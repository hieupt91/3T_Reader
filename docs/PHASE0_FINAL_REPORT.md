# Phase 0 — Final Technical Report

Date: 2026-05-19

## Tất cả việc đã hoàn thiện trong Phase 0

### 1. Làm sạch source và brand
- Dọn workspace khỏi artifact nặng, file rác, `.agents/`, `venv/`, `dist/`, `build/`, cache.
- Chuẩn hóa brand sang `3T Reader`, `APP_NAME = "3T Reader"`, `APP_DATA_DIR_NAME = "3T Reader"`.
- `.gitignore` đúng chuẩn Python/PyInstaller, bỏ phần PowerShell sai.

### 2. Tách lớp nền platform
- `packages/platform/paths.py` — app data / cache / log dir theo OS (Windows/macOS/Linux).
- `packages/platform/single_instance.py` — single instance guard.
- `packages/platform/fonts.py` — font resolver theo OS (Windows: `%SystemRoot%\Fonts`,
  macOS: `/System/Library/Fonts`, Linux: `/usr/share/fonts`).
- `packages/platform/__init__.py` — export đầy đủ.
- `core/recent.py` — dùng platform adapter, không tự ghép `os.name`.

### 3. Tách PDF engine khỏi UI
- `packages/pdf_engine/base.py` — `PdfEngine` / `PdfDocument` Protocol.
- `packages/pdf_engine/pdfium_engine.py` — `PdfiumEngine` dùng `pypdfium2` + `pikepdf` + `reportlab`.
- `packages/pdf_engine/pymupdf_engine.py` — `PyMuPdfEngine` (legacy path, AGPL, disabled mặc định).
- Default engine = `PdfiumEngine`; chuyển sang AGPL path chỉ qua env var `THREET_READER_PDF_ENGINE=legacy`.

### 4. Bỏ GPL wrappers
- Loại `pdfjs-viewer-pyqt6` GPL-3.0-or-later — app dùng PDF.js Apache 2.0 trực tiếp qua `QWebEngineView`.
- Loại import trực tiếp `PyQt6` — toàn bộ Qt đi qua `packages/qt_compat/`.

### 5. Tách signing theo OS (hoàn tất Phase 0)
- `packages/signing/provider.py` — `SigningProvider` Protocol + `TokenInfo` dataclass.
- `packages/signing/shared.py` — shared utilities không phụ thuộc OS:
  cert parsing, ASCII-fold, tax code extraction, stamp style builder, core pyHanko signing session.
- `packages/signing/windows_provider.py` — `WindowsPkcs11Provider`:
  dò `.dll` trong `%SystemRoot%\System32` và `%SystemRoot%\SysWOW64`.
- `packages/signing/macos_provider.py` — `MacOSPkcs11Provider`:
  dò `.dylib/.so` trong `/usr/lib`, `/usr/local/lib`, Homebrew dirs, `~/Library/PKCS11`.
- `packages/signing/__init__.py` — chọn provider theo `sys.platform` (darwin → macOS, win32 → Windows).
- `core/pkcs11.py` — thin backward-compat shim; không còn `_candidate_paths()` hay font path Windows.

### 6. Font stamp — không còn hardcode Windows
- `packages/platform/fonts.py` — `get_vietnamese_font_path()` theo OS.
- `packages/signing/shared.py` — `build_vietnamese_stamp_style()` không nhận font_path (dùng
  pyHanko default; font system resolve không phụ thuộc path cứng).
- `main.py` — UI font chọn theo `platform.system()`: Segoe UI (Windows), SF Pro Text (macOS), fallback.

### 7. Compliance scaffolding
- `LICENSES.md`, `NOTICE.md` — tổng quan license.
- `docs/compliance/THIRD_PARTY_MANIFEST.md` — bảng dependency + license status.
- `docs/compliance/PDFJS_SOURCE.md` — PDF.js **v5.6.205** Apache 2.0, source URL ghi rõ.
- `docs/compliance/PHASE0_BLOCKERS.md` — checklist hoàn chỉnh: done vs. còn lại.

### 8. License/update backend skeleton
- `packages/license_client/` — `LicenseClient` skeleton.
- `packages/update_client/` — `UpdateManifest` skeleton.
- `server/license-api/README.md` — blueprint VPS backend.

### 9. Smoke tests
- `tests/test_smoke_platform.py` — 19 tests, tất cả pass trên macOS:
  platform paths, font resolver, signing provider selection, shared utils, recent files.

---

## Kiến trúc shared layer sau Phase 0

```
packages/
  platform/
    paths.py          ← app data / cache / log (OS-aware)
    fonts.py          ← font resolver (OS-aware)
    single_instance.py
  signing/
    provider.py       ← SigningProvider Protocol, TokenInfo
    shared.py         ← cert parsing, stamp, pyHanko signing (OS-agnostic)
    windows_provider.py ← WindowsPkcs11Provider (.dll, System32)
    macos_provider.py   ← MacOSPkcs11Provider (.dylib, Homebrew, etc.)
    __init__.py       ← get_signing_provider() → chọn theo sys.platform
  pdf_engine/
    base.py           ← PdfEngine, PdfDocument Protocol
    pdfium_engine.py  ← primary (pypdfium2 + pikepdf + reportlab)
    pymupdf_engine.py ← legacy AGPL path
  qt_compat/          ← Qt import wrapper
  license_client/     ← skeleton
  update_client/      ← skeleton
core/
  pkcs11.py           ← backward-compat shim only
  recent.py           ← delegates to packages.platform
```

---

## Còn lại trước commercial release

Xem `docs/compliance/PHASE0_BLOCKERS.md` — phần "Must Resolve Before Commercial Release":

1. Download official PDF.js 5.6.205 để có clean chain of custody.
2. Fixture tests cho non-AGPL PDF edit pipeline (pikepdf + reportlab).
3. Smoke test thực tế trên macOS (mở app, load PDF, render, search, signing flow).
4. Smoke test thực tế trên Windows sau khi tách shared.
5. Pin Fluent UI icon source/license commit hoặc thay icon tự thiết kế.
6. SBOM/license table đầy đủ từ build environment (`pip-licenses` + CycloneDX).
7. EULA, Privacy Policy, Third-party Notices.

---

## Phase gate

Phase 1 (split Windows/macOS/VPS) được phép mở khi checklist trên được giải quyết hoặc
được defer với lý do rõ ràng bằng văn bản.
