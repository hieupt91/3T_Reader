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
- Remaining: edit operations in `app/actions/edit.py` still use `fitz` directly for text/image insertion and undo rebuilds. This is the next PDF migration target before any commercial release.

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
