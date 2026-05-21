# Licenses — 3T Reader

3T Reader is proprietary software developed by 3T Company.  
Copyright © 2026 3T Company. All rights reserved.

This software incorporates third-party open-source components listed below.  
Full license texts are in `THIRD_PARTY_NOTICES.md`.

---

## Third-Party Components

| Component | Version | License | Usage |
|---|---|---|---|
| **PySide6** | 6.11.0 | LGPL v3 | Desktop UI framework (Qt) |
| **pyqtdarktheme** | 0.1.7 | MIT | Dark/light theme for Qt |
| **pypdfium2** | 5.7.0 | Apache-2.0 / BSD-3-Clause | PDF rendering (PDFium) |
| **pikepdf** | 10.5.1 | MPL-2.0 | PDF structure manipulation |
| **reportlab** | 4.4.5 | BSD | PDF generation |
| **pyHanko** | 0.34.1 | MIT | PDF digital signatures |
| **python-pkcs11** | 0.9.4 | MIT | USB token PKCS#11 interface |
| **cryptography** | 46.0.7 | Apache-2.0 / BSD | Cryptographic operations |
| **Pillow** | 12.2.0 | HPND | Image processing |
| **requests** | 2.33.1 | Apache-2.0 | HTTP client |
| **pytesseract** | ≥ 0.3.13 | Apache-2.0 | Tesseract OCR Python wrapper |
| **Tesseract OCR** | 5.x | Apache-2.0 | OCR engine (system install) |
| **PDF.js** | (bundled) | Apache-2.0 | PDF rendering in WebView |
| **PyInstaller** | 6.20.0 | GPL + bootloader exception | App packaging (build only) |

---

## Assets

- **Application icons** (`assets/3TReader.icns`, `assets/icon.ico`, `assets/icon_*.png`):  
  Original artwork created by 3T Company. All rights reserved.

- **UI icons** (`assets/icons/*.svg`):  
  Original artwork created by 3T Company. All rights reserved.

- **Logo** (`assets/logo*.svg`):  
  Original artwork created by 3T Company. All rights reserved.

---

## Compliance Notes

- **PySide6 (LGPL v3):** 3T Reader links dynamically to PySide6/Qt libraries. In compliance with LGPL v3, users may replace the Qt libraries. Qt source code is available at https://code.qt.io
- **pikepdf (MPL-2.0):** MPL-2.0 allows use in proprietary software. Source: https://github.com/pikepdf/pikepdf
- **PyInstaller bootloader exception:** Permits commercial use despite GPL base license.
- **Tesseract OCR:** Installed separately on the end-user system; not bundled in the application.
