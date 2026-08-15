# Windows 1.0.32 parity reference

Date: 2026-08-15  
Reference branch: `phase1-win-1.0.32`  
Reference commit: `60c5b69694711ce083b9e8ef6db21a220ba5a826`  
Reference tag: `phase1-win-1.0.32` (`45b72d82591b121837609d93c618babdf0e7e39e`)

## Release identity

- Application: Windows 1.0.32
- Bootstrap installer: `3TReader-1.0.32-win-r7.exe`
- Installer SHA-256: `B2EAA47BBD6675A6629766F5355B03395A96F5E3BC4A3F3CD036C5C69BA32AAA`
- Runtime: PySide6/Qt WebEngine + PDF.js, pypdfium2 + pikepdf, bundled Tesseract

## Capability baseline imported from Windows handoff

| ID | Capability | Mac audit status | Required Mac evidence |
|---|---|---|---|
| W32-001 | Open, tabs, recent, drag/drop, PDF viewer | PARTIAL (P1) | Same fixture, tabs/recent/drop and reopen evidence. |
| W32-002 | Rotate, insert, delete, extract, merge/split pages | PARTIAL (P1) | Saved PDF output and page-order comparison. |
| W32-003 | Highlight, underline, strikeout, notes, draw | PARTIAL (P1) | Visual and reopened annotation evidence. |
| W32-004 | Edit original text; insert text/image | MISSING (P0) | Mac implementation plus save/reopen regression. |
| W32-005 | OCR/searchable scan | PARTIAL (P1) | Same scanned fixture, OCR text and cancel/error states. |
| W32-006 | AI chat, translation, TTS | PARTIAL (P1) | Provider success/offline/error and audio evidence. |
| W32-007 | Print, Office export, document conversion | MISSING (P1) | Word/Excel outputs and print preview comparison. |
| W32-008 | USB/PFX/batch signing | PARTIAL (P0) | Real middleware/token plus verification evidence. |
| W32-009 | License, signed updater, delta bootstrap | PARTIAL (P0) | Full update verification; delta remains disabled until Mac safety proof. |
| W32-010 | P2P ScanDoc transfer | PARTIAL (P1) | QR/send/receive/timeout/retry/malformed-code evidence. |

## Windows evidence caveat

The handoff lists the Windows QA files and tests, but PR #1 currently reports
failed CI for lint and Python 3.11/3.12/3.13. Therefore this document is the
capability reference, not a claim that the Windows snapshot is release-green.
The failing checks must be fixed or explicitly explained before final parity
closure.

## Required next steps

1. Team Windows fixes/triages all PR checks and publishes the final result.
2. Team Mac runs the same fixtures/workflows against the Mac build.
3. Update the nine parity reports with screenshots, logs and output hashes.
4. Do not mark a row `PASS` based on source presence alone.
