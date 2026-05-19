# Dependency Strategy

Phase 0 keeps the prototype running while making risky dependencies visible and replaceable.

## UI

Current: `PyQt6`, `PyQt6-WebEngine`, `pdfjs-viewer-pyqt6`.

Commercial target:

- Prefer `PySide6` plus LGPL compliance, or buy commercial PyQt.
- Remove `pdfjs-viewer-pyqt6` from commercial builds.
- Integrate PDF.js directly with a documented Apache-2.0 bundle or use a commercial SDK.

## PDF Engine

Current: PyMuPDF adapter in `packages/pdf_engine/pymupdf_engine.py`.

Commercial target:

- Buy PyMuPDF/MuPDF commercial license, or
- Replace with `pypdfium2/PDFium` for render and `pikepdf/qpdf` for structural operations.

All new code should call `packages.pdf_engine.get_pdf_engine()` instead of importing `fitz` directly.

Phase 0.2 migration status:

- Done: open/decrypt PDF flow.
- Done: thumbnail rendering.
- Done: print rendering.
- Done: blank PDF creation.
- Done in Phase 0.3: edit operations and undo rebuilds now call `PdfEngine.rebuild_pdf_with_ops()`.

Current state:

- Direct `fitz` imports should only exist in `packages/pdf_engine/pymupdf_engine.py`.
- PyMuPDF remains a commercial-release blocker unless a commercial license is purchased.
- Replacing PyMuPDF should primarily require a new `PdfEngine` implementation.

## Signing

Current: prototype code in `core/pkcs11.py`, wrapped by `packages/signing/current_pkcs11_provider.py`.

Commercial target:

- Prefer `python-pkcs11` where technically possible.
- Keep Windows and macOS PKCS#11 probing behind provider classes.
- Do not bundle vendor token DLL/dylib files.

## License And Update

Current: placeholders only.

Commercial target:

- Linux VPS API.
- Signed license tokens.
- Signed update manifests.
- OS-native credential storage.
