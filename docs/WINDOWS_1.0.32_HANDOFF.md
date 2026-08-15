# Windows 1.0.32 handoff snapshot

This immutable branch is the Windows reference used by the macOS parity audit.
It contains the full tracked application source, assets, dependency manifests,
PyInstaller spec, Inno Setup installer, tests and release evidence available at
the 1.0.32 bootstrap milestone.

## Release identity

| Item | Value |
|---|---|
| Application version | 1.0.32 |
| Bootstrap installer | `3TReader-1.0.32-win-r7.exe` |
| Installer SHA-256 | `B2EAA47BBD6675A6629766F5355B03395A96F5E3BC4A3F3CD036C5C69BA32AAA` |
| Python build environment | Python 3.13, PyInstaller one-dir, Nuitka optional modules |
| UI runtime | PySide6 / Qt WebEngine + PDF.js |
| PDF read/write | pypdfium2 + pikepdf |
| OCR | bundled Tesseract + pytesseract |

## Capability matrix

| ID | Windows 1.0.32 capability | UI / entry point | Source area | Evidence | Mac status | Port owner |
|---|---|---|---|---|---|---|
| W32-001 | Open, tabs, recent files, drag/drop, PDF viewer | File menu, ribbon, drop area | `app/window.py`, `app/pdf_viewer.py` | `tests/test_smoke_windows.py` | MISSING | Mac team |
| W32-002 | Page rotate, insert, delete, extract, merge/split | Trang ribbon and context menu | `app/actions/pages.py`, `app/actions/annotate.py` | `tests/test_rotate_crash_guard.py`, `tests/test_pdf_save_helpers.py` | PARTIAL | Mac team |
| W32-003 | Highlight, underline, strikeout, notes, draw | Chú thích ribbon/context menu | `app/actions/annotate.py`, `assets/js/` | `tests/test_viewer_annotation_regressions.py` | PARTIAL | Mac team |
| W32-004 | Edit original text and insert text/image | Sửa PDF ribbon | `app/actions/edit.py` | `tests/test_edit_ocr_font.py` | MISSING | Mac team |
| W32-005 | OCR and searchable scan workflow | OCR ribbon/dialog | `packages/ocr/`, `app/ocr_dialog.py` | `tests/test_ocr_runtime.py` | PARTIAL | Mac team |
| W32-006 | AI chat, translation and TTS | AI ribbon/dialogs | `app/ai_*`, `packages/ai/` | relevant `tests/test_ai_*` | PARTIAL | Mac team |
| W32-007 | Print, export Office, document conversion | File/Export | `app/actions/document_ops.py`, `packages/document_core/` | `tests/test_office_com.py` | MISSING | Mac team |
| W32-008 | USB/PFX/batch signing | Ký số ribbon | `app/actions/sign.py`, `packages/signing/` | `tests/test_signing_*` | PARTIAL | Mac team |
| W32-009 | License, signed updater, delta bootstrap | License/help update dialogs | `packages/license_client/`, `packages/updater/` | `tests/test_update_client_v2.py`, `tests/test_delta_runtime.py` | MISSING | Windows owner / Mac team |
| W32-010 | P2P ScanDoc transfer | License/Transfer dialogs | `packages/transfer/`, `app/transfer_*` | transfer tests and handoff docs | PARTIAL | Mac team |

## Workflow and evidence

Run the complete regression suite with `python -m pytest tests -q`. The primary
QA records are `docs/QA_REPORT_2026-08-12.md`,
`docs/QA_TOAN_DIEN_2026-08-04.md`, `docs/QA_HEAVY_FILE_2026-08-04.md`, and
`docs/audit_2026-07-30/FINAL_AUDIT_REPORT.md`. Windows installer construction
uses `build_secure.py`, `3T_Reader.spec`, `installer_script.iss`, and
`scripts/build_installer_assets.py`.

Windows-only behaviours include registry PDF association/icon refresh, UAC
installer flow, Office/WPS COM conversion, Windows Credential Manager and
PKCS#11 middleware discovery. These are references for parity; they must not
be removed without an explicit cross-platform replacement and retest.

## Security/compliance reference

The updater verifies SHA-256 and Ed25519 signatures before install. The B53
delta layer only patches verified allow-listed code below `_internal`; the
bootstrap and executable remain immutable. License verification, audit logging
and signing safeguards are documented in the security/audit handoff documents
under `docs/`.
