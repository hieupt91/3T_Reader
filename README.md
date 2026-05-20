# 3T Reader Phase 0

Phase 0 turns the existing Reader3T PDF prototype into a clean technical foundation for the 3T Reader / 3T Document AI direction.

Current scope:

- Clean source workspace without `venv`, `dist`, `build`, `.git`, `.agents`, `__pycache__`, or recent/temp files.
- Keep one desktop codebase while preparing platform adapters for Windows and macOS.
- Prepare Linux VPS integration points for license and update services.
- Document third-party license risks before any closed-source commercial release.

Not yet in this phase:

- Splitting into final Windows/macOS/VPS implementation streams.
- Adding AI/OCR features.
- Replacing GPL/AGPL dependencies.
- Shipping commercial builds.

PDF engine note:

- Default engine is `PdfiumEngine` with pypdfium2/pikepdf/reportlab.
- Legacy PyMuPDF can be selected only for prototype debugging with `THREET_READER_PDF_ENGINE=pymupdf`.
- Commercial release must keep legacy PyMuPDF out of builds and verify the non-AGPL edit pipeline with tests.

See [docs/PHASE0_SCOPE.md](docs/PHASE0_SCOPE.md), [docs/PHASE0_CLOSURE.md](docs/PHASE0_CLOSURE.md), and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Compliance status is tracked in [docs/compliance/THIRD_PARTY_MANIFEST.md](docs/compliance/THIRD_PARTY_MANIFEST.md) and [docs/compliance/PHASE0_BLOCKERS.md](docs/compliance/PHASE0_BLOCKERS.md).
