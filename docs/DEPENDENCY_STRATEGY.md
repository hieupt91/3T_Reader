# Dependency Strategy

Phase 0 keeps the prototype running while making risky dependencies visible and replaceable.

## UI

Current target: `PySide6` through `packages.qt_compat`.

Commercial target:

- Use `PySide6` plus LGPL compliance.
- Keep `pdfjs-viewer-pyqt6` out of app code and commercial builds.
- Integrate PDF.js directly with a documented Apache-2.0 bundle or use a commercial SDK.

Phase 0.4 status:

- App imports now go through `packages.qt_compat`.
- PyQt fallback has been removed from `packages.qt_compat`.
- `app/window.py` uses the internal `app.pdf_viewer.PDFViewerWidget`.
- `pdfjs-viewer-pyqt6` has been removed from the primary dependency list.
- `third_party/pdfjs` contains the PDF.js bundle and license files copied from the previous packaged dependency for migration. Before release, replace it with a fresh official PDF.js distribution pinned by version/source commit.

## PDF Engine

Legacy fallback: PyMuPDF adapter in `packages/pdf_engine/pymupdf_engine.py`.

Commercial-safe migration target: `packages/pdf_engine/pdfium_engine.py` using `pypdfium2` for read/render and `pikepdf/reportlab` for overlay-based edit operations.

Commercial target:

- Keep PyMuPDF/MuPDF out of commercial builds.
- Use `pypdfium2/PDFium` for render and `pikepdf/reportlab` for edit overlays.

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
- Phase 0.8 makes `PdfiumEngine` the default engine.
- `PyMuPdfEngine` is available only through `THREET_READER_PDF_ENGINE=pymupdf` for legacy prototype testing.
- The pikepdf/reportlab edit path needs fixture tests before commercial release.

## Signing

Current: prototype code in `core/pkcs11.py`, wrapped by `packages/signing/current_pkcs11_provider.py`.

Commercial target:

- Prefer `python-pkcs11` where technically possible.
- Keep Windows and macOS PKCS#11 probing behind provider classes.
- Do not bundle vendor token DLL/dylib files.

Phase 0.6 status:

- `PyKCS11` has been removed from primary dependencies.
- Token detection, certificate reading, and signing use `python-pkcs11`.
- `PyKCS11` is only listed as an optional legacy dependency for emergency compatibility testing.

## License And Update

Current: placeholders only.

Commercial target:

- Linux VPS API.
- Signed license tokens.
- Signed update manifests.
- OS-native credential storage.
