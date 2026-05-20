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

See [docs/PHASE0_SCOPE.md](docs/PHASE0_SCOPE.md), [docs/PHASE0_CLOSURE.md](docs/PHASE0_CLOSURE.md), [docs/WORKFLOW_CONVENTION.md](docs/WORKFLOW_CONVENTION.md), and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Compliance status is tracked in [docs/compliance/THIRD_PARTY_MANIFEST.md](docs/compliance/THIRD_PARTY_MANIFEST.md) and [docs/compliance/PHASE0_BLOCKERS.md](docs/compliance/PHASE0_BLOCKERS.md).

## Windows Phase 1 Notes

Windows-only work belongs in the `phase1-win` stream. Keep shared UX and business logic out of this branch unless the same change is intended for macOS and moved through the shared stream first.

Current Windows-specific packaging assumptions:

- PyInstaller onedir output is expected at `dist\3T_Reader`.
- The PyInstaller spec collects native package data/binaries for `pypdfium2` and `pikepdf`.
- Inno Setup output is written to `build\installer`.
- The installer uses the same single-instance mutex as runtime: `Local\3T_Reader_SingleInstance_v1`.

Windows USB token notes:

- The Windows PKCS#11 provider scans `System32`, `SysWOW64`, `Program Files`, `Program Files (x86)`, and `LOCALAPPDATA`.
- To force one or more custom vendor DLL locations, set `THREET_READER_WINDOWS_PKCS11_PATHS`.
- Multiple entries are separated with the Windows path separator `;`.
- Example: `set THREET_READER_WINDOWS_PKCS11_PATHS=D:\Tokens\vendor.dll;E:\CA\PKCS11`

Windows setup and release workflow:

- Start with [SETUP_WINDOWS.md](SETUP_WINDOWS.md) if you want the one-page entrypoint for Windows team onboarding.
- Start with [docs/setup_windows.md](docs/setup_windows.md) for clone, run, test, build, and release steps.
- Use [docs/PHASE1_WIN_HANDOFF.md](docs/PHASE1_WIN_HANDOFF.md) when you need the current stream summary and next steps.
- Use [docs/PHASE1_WIN_STATUS.md](docs/PHASE1_WIN_STATUS.md) for the short state snapshot.
