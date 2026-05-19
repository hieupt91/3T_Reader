# Third-Party Manifest

Phase 0.7 manual manifest. This must be verified with `pip-licenses` and a CycloneDX SBOM before commercial release.

## Primary Runtime Dependencies

| Component | Version / Source | Current Purpose | License Status | Phase 0 Decision |
| --- | --- | --- | --- | --- |
| PySide6 / Qt for Python | 6.11.0 | Qt desktop UI, WebEngine, widgets | LGPL/GPL/commercial depending on distribution and modules | Primary UI binding. Must complete LGPL compliance review and Qt/Chromium notices. |
| pyqtdarktheme | Unpinned | Dark Qt stylesheet | Needs exact license/version verification | Keep temporarily; consider replacing with local stylesheet to reduce dependency risk. |
| pypdfium2 | 5.7.0 | Experimental PDF read/render engine | Needs SBOM/license verification | Primary non-AGPL migration target. |
| pikepdf | 10.5.1 | Experimental structural PDF operations | Needs SBOM/license verification | Primary PDF structure/edit migration target. |
| pyHanko | 0.34.1 | PDF signing/stamp workflow | Needs SBOM/license verification | Keep if compatible after dependency audit. |
| python-pkcs11 | Unpinned | PKCS#11 token/cert/signing session | Expected MIT; verify exact package metadata | Primary signing library. |
| cryptography | 46.0.7 | X.509 parsing and crypto dependencies | Apache-2.0/BSD style; verify exact metadata | Keep with notices. |
| Pillow | 12.2.0 | Image conversion support | HPND style; verify exact metadata | Keep with notices. |
| requests | 2.33.1 | Future HTTP client/update/license support | Apache-2.0; verify exact metadata | Keep if used by VPS client later. |

## Optional / Legacy Dependencies

| Component | Version | Purpose | Risk | Decision |
| --- | --- | --- | --- | --- |
| PyMuPDF / MuPDF | 1.27.2.2 | Prototype PDF edit/render engine | AGPL/commercial | Optional legacy only. Do not ship commercially without Artifex commercial license or full replacement. |
| PyKCS11 | 1.5.18 | Legacy PKCS#11 compatibility | GPL risk | Optional legacy only after legal review. Not in primary dependencies. |
| PyInstaller | 6.20.0 | Build packaging | GPL with bootloader exception; verify | Build dependency only. Keep notices. |

## Bundled Assets / Third-Party Source

| Asset | Location | Source | License Status | Decision |
| --- | --- | --- | --- | --- |
| PDF.js bundle | `third_party/pdfjs` | Migration copy from previous packaged `pdfjs_viewer/pdfjs` | `LICENSE` and nested licenses included, but source release/tag not pinned | Replace with official PDF.js release before commercial release. |
| Toolbar SVG icons | `assets/icons` | `download_icons.py` points to Microsoft Fluent UI System Icons | License text/source commit missing | Pin source and include license, or replace with custom brand assets. |
| PDF.js standard fonts/wasm/cmaps | `third_party/pdfjs/web/*` | PDF.js distribution | License files are present under `web/` | Keep all nested license files and verify notices. |

## Explicitly Removed From Main Path

| Component | Reason |
| --- | --- |
| pdfjs-viewer-pyqt6 | GPL-3.0-or-later wrapper. App now uses internal `app.pdf_viewer` with direct PDF.js bundle. |
| PyQt6 | GPL/commercial binding. App now imports Qt via `packages.qt_compat` targeting PySide6. |

## Required Verification Before Commercial Release

- Run `pip-licenses` for installed runtime and build environments.
- Generate CycloneDX SBOM.
- Store exact license files for Python packages, PDF.js, Qt/Chromium, icons, fonts, and build tools.
- Verify whether any Qt modules used are GPL-only or require commercial Qt.
- Verify pypdfium2/PDFium and pikepdf/qpdf notices with legal/compliance review.
