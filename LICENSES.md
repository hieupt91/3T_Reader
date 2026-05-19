# Licenses

## 3T Reader

Copyright 2026 3T Company. All rights reserved.

3T Reader source code in this repository is proprietary and confidential.
Distribution of this software requires a commercial license agreement.

---

## Third-Party Component Licenses

For the full list of third-party components and their license obligations,
see **THIRD_PARTY_NOTICES.md** in this directory.

### License Summary

| Component | License | Commercial Use |
|---|---|---|
| PySide6 / Qt 6.11.0 | LGPL-3.0 (dynamic link) | ✅ Allowed |
| PDF.js 5.6.205 | Apache-2.0 | ✅ Allowed |
| pypdfium2 5.7.0 | BSD-3-Clause + Apache-2.0 | ✅ Allowed |
| pikepdf 10.5.1 | MPL-2.0 | ✅ Allowed (copyleft applies to pikepdf changes only) |
| reportlab 4.4.5 | HPND (BSD-style) | ✅ Allowed |
| pyHanko 0.34.1 | MIT | ✅ Allowed |
| python-pkcs11 | MIT | ✅ Allowed |
| cryptography 46.0.7 | Apache-2.0 / BSD-3-Clause | ✅ Allowed |
| Pillow 12.2.0 | MIT-CMU (HPND) | ✅ Allowed |
| requests 2.33.1 | Apache-2.0 | ✅ Allowed |
| pyqtdarktheme | MIT | ✅ Allowed |
| Fluent UI System Icons | MIT | ✅ Allowed — commit f981da35 (2026-05-18) |
| Lucide Icons | ISC | ✅ Allowed — commit 5b40f2c5 (2026-05-15) |
| PyInstaller 6.20.0 | GPL + bootloader exception | ✅ Build-only (exception covers non-free apps) |
| **PyMuPDF** (optional) | **AGPL-3.0** | ❌ Not shipped in commercial builds |
| **PyQt6** (removed) | **GPL-3.0** | ❌ Removed — replaced by PySide6 LGPL |
| **pdfjs-viewer-pyqt6** (removed) | **GPL-3.0-or-later** | ❌ Removed |
| **PyKCS11** (optional) | **GPL** | ❌ Not shipped in commercial builds |

### PDF.js Nested Licenses

The bundled PDF.js distribution (`third_party/pdfjs/`) includes additional
license files for embedded components:

- CMaps: `third_party/pdfjs/web/cmaps/LICENSE`
- Standard fonts (Foxit): `third_party/pdfjs/web/standard_fonts/LICENSE_FOXIT`
- Standard fonts (Liberation): `third_party/pdfjs/web/standard_fonts/LICENSE_LIBERATION`
- WebAssembly modules: `third_party/pdfjs/web/wasm/LICENSE_*`

### Qt / Chromium Notices

PySide6 bundles Qt WebEngine which includes Chromium. Before commercial
distribution, collect and include Qt's third-party Chromium notices
as required by the LGPL terms. See:
https://code.qt.io/cgit/qt/qtwebengine-chromium.git/

### Required Before Commercial Release

- [ ] Run `pip-licenses` from Windows build environment to generate SBOM.
- [ ] Collect Qt/Chromium third-party notices per LGPL requirements.
- [ ] `cyclonedx-py requirements requirements.txt` → CycloneDX SBOM.
- [ ] Verify PySide6 LGPL dynamic linking compliance per OS.
- [ ] EULA and Privacy Policy (required before Phase 3 / license server launch).
