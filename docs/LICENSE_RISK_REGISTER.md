# License Risk Register

This is a Phase 0 technical register, not legal advice.

| Component | Current Use | Risk | Phase 0 Decision |
| --- | --- | --- | --- |
| PyQt6 | Removed from app code and primary dependencies | GPL/commercial. Closed-source distribution requires careful licensing. | Do not use in commercial builds. Target PySide6. |
| PySide6 / Qt for Python | Desktop UI and Qt WebEngine target | LGPL/GPL/commercial depending on distribution. LGPL requires compliance. | Use PySide6 with LGPL notices/packaging review, or Qt commercial if business later chooses. |
| pdfjs-viewer-pyqt6 | Removed from app imports | GPL-3.0-or-later. High risk for closed-source app distribution. | Keep out of commercial builds. Internal viewer loads PDF.js directly. |
| PDF.js | Internal viewer bundle | Apache-2.0 plus bundled notices/fonts/wasm licenses. | Replace migration copy with official pinned PDF.js release and keep notices. |
| PyMuPDF/MuPDF | Thumbnail, print, PDF edit | AGPL/commercial. High risk for closed-source commercial app. | Phase 0.3 isolates direct usage in `packages/pdf_engine/pymupdf_engine.py`. Buy commercial license or replace before release. |
| PyKCS11 | USB token detection | GPL risk. | Prefer `python-pkcs11` MIT or isolate signing plugin after legal review. |
| Icon SVG assets | Toolbar icons | Source/license not documented. | Treat as unapproved until replaced or provenance is recorded. |
| GitHub updater | Public release update channel | Not suitable for B2B enterprise update trust. | Disable direct GitHub path; prepare VPS update manifest. |
