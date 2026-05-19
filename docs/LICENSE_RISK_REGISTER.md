# License Risk Register

This is a Phase 0 technical register, not legal advice.

| Component | Current Use | Risk | Phase 0 Decision |
| --- | --- | --- | --- |
| PyQt6 | Desktop UI and Qt WebEngine | GPL/commercial. Closed-source distribution requires careful licensing. | Keep for prototype only. Decide PySide6 migration or commercial PyQt before release. |
| pdfjs-viewer-pyqt6 | PDF.js viewer wrapper | GPL-3.0-or-later. High risk for closed-source app distribution. | Mark for replacement with PySide6/PDF.js integration or commercial SDK. |
| PyMuPDF/MuPDF | Thumbnail, print, PDF edit | AGPL/commercial. High risk for closed-source commercial app. | Phase 0.2 introduced `packages/pdf_engine`; edit operations still need migration. Buy commercial license or replace before release. |
| PyKCS11 | USB token detection | GPL risk. | Prefer `python-pkcs11` MIT or isolate signing plugin after legal review. |
| Icon SVG assets | Toolbar icons | Source/license not documented. | Treat as unapproved until replaced or provenance is recorded. |
| GitHub updater | Public release update channel | Not suitable for B2B enterprise update trust. | Disable direct GitHub path; prepare VPS update manifest. |
