# Third-Party Notices

3T Reader uses the following third-party components. All licenses are
compatible with the commercial distribution strategy described in
`docs/compliance/THIRD_PARTY_MANIFEST.md`.

---

## UI Framework

### PySide6 / Qt for Python
- **Version:** 6.11.0
- **License:** LGPL-3.0-only (dynamic linking) / GPL / Commercial
- **Source:** https://pypi.org/project/PySide6/
- **Note:** Qt WebEngine bundles Chromium; see Qt's Chromium notices at
  https://code.qt.io/cgit/qt/qtwebengine.git/

### pyqtdarktheme
- **License:** MIT
- **Source:** https://pypi.org/project/pyqtdarktheme/

---

## PDF Rendering & Processing

### PDF.js
- **Version:** 5.6.205
- **License:** Apache License 2.0
- **Source:** https://github.com/mozilla/pdf.js/releases/tag/v5.6.205
- **Bundle location:** `third_party/pdfjs/`
- **Nested licenses:**
  - `third_party/pdfjs/web/cmaps/LICENSE`
  - `third_party/pdfjs/web/standard_fonts/LICENSE_FOXIT`
  - `third_party/pdfjs/web/standard_fonts/LICENSE_LIBERATION`
  - `third_party/pdfjs/web/wasm/LICENSE_*`

### pypdfium2
- **Version:** 5.7.0
- **License:** BSD-3-Clause, Apache-2.0 (PDFium), dependency licenses
- **Source:** https://pypi.org/project/pypdfium2/

### pikepdf / qpdf
- **Version:** 10.5.1
- **License:** MPL-2.0 (copyleft applies to pikepdf source changes only)
- **Source:** https://pypi.org/project/pikepdf/

### reportlab
- **Version:** 4.4.5
- **License:** BSD (HPND)
- **Source:** https://pypi.org/project/reportlab/

### PyMuPDF / MuPDF  *(optional legacy — NOT included in commercial builds)*
- **Version:** 1.27.2.2
- **License:** AGPL-3.0 / Artifex Commercial
- **Note:** Loaded only when `THREET_READER_PDF_ENGINE=legacy`. Not shipped
  in default commercial builds. Requires separate Artifex license for
  closed-source distribution.

---

## Digital Signing

### pyHanko
- **Version:** 0.34.1
- **License:** MIT
- **Source:** https://pypi.org/project/pyHanko/

### python-pkcs11
- **License:** MIT
- **Source:** https://pypi.org/project/python-pkcs11/

### PyKCS11  *(optional legacy — NOT included in commercial builds)*
- **Version:** 1.5.18
- **License:** GPL (with LGPL option for OpenSC integration)
- **Note:** Optional dependency only. Not in default or commercial builds.

---

## Cryptography & Security

### cryptography
- **Version:** 46.0.7
- **License:** Apache-2.0 OR BSD-3-Clause
- **Source:** https://pypi.org/project/cryptography/

---

## Image Processing

### Pillow
- **Version:** 12.2.0
- **License:** MIT-CMU (HPND)
- **Source:** https://pypi.org/project/Pillow/

---

## HTTP Client

### requests
- **Version:** 2.33.1
- **License:** Apache-2.0
- **Source:** https://pypi.org/project/requests/

---

## Icons

### Microsoft Fluent UI System Icons
- **License:** MIT License
- **Source:** https://github.com/microsoft/fluentui-system-icons
- **Pinned commit:** `f981da3508ad681da9bbd45c74f210e8c3fef72d` (2026-05-18)
- **Files:** `assets/icons/folder_open.svg`, `history.svg`, `chevron_left.svg`,
  `chevron_right.svg`, `zoom_out.svg`, `zoom_in.svg`, `fit_page.svg`,
  `save.svg`, `print.svg`, `usb.svg`, `pen.svg`, `fullscreen.svg`

### Lucide Icons
- **License:** ISC License (MIT-compatible)
- **Source:** https://github.com/lucide-icons/lucide
- **Pinned commit:** `5b40f2c5a76a27eeb81c8f1b1c311121dee45495` (2026-05-15)
- **Files:** `assets/icons/file_plus.svg`, `undo.svg`, `object_plus.svg`,
  `edit_object.svg`

---

## Build Tooling  *(not shipped in app)*

### PyInstaller
- **Version:** 6.20.0
- **License:** GPL-2.0-or-later with bootloader exception
  (exception allows distributing non-free programs built with PyInstaller)
- **Source:** https://pypi.org/project/pyinstaller/

---

## Required Actions Before Commercial Release

- [ ] Run `pip-licenses` from Windows build environment to generate
  machine-readable SBOM.
- [ ] Collect and include Qt/Chromium third-party notices per LGPL requirements.
- [ ] Generate `CycloneDX` SBOM: `cyclonedx-py requirements requirements.txt`.
- [ ] Verify PySide6 LGPL dynamic linking compliance for each OS build.
