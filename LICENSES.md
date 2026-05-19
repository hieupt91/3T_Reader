# Third-Party Licenses

Phase 0.7 status: manual manifest exists, but exact license texts/SBOM are not complete.

See:

- `docs/compliance/THIRD_PARTY_MANIFEST.md`
- `docs/compliance/PDFJS_SOURCE.md`
- `docs/LICENSE_RISK_REGISTER.md`

Primary items requiring final license files/notices:

- PySide6 / Qt for Python
- Qt WebEngine / Chromium notices
- PDF.js and nested fonts/wasm/cmaps notices
- pypdfium2 / PDFium
- pikepdf / qpdf
- pyHanko
- python-pkcs11
- cryptography
- Pillow
- requests
- pyqtdarktheme, or replacement local theme
- Fluent UI icons, or replacement owned brand assets

Optional legacy items not allowed in commercial builds without review:

- PyMuPDF / MuPDF
- PyKCS11
