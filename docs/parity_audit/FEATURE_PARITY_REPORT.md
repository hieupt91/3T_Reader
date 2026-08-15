# Feature parity report

Date: 2026-08-15  
Build: `origin/phase1-mac@b025994`, local unsigned macOS `.app/.dmg`
Windows reference: `phase1-win-1.0.32@60c5b69694711ce083b9e8ef6db21a220ba5a826`
Environment: macOS 13.7.8 x86_64, Python 3.14.6, PyInstaller 6.20.0  
Evidence: `dist/mac/3T Reader.app`, `dist/mac/3T_Reader_mac.dmg`, `tests/test_update_client_signature.py`

## Baseline result

The Windows 1.0.32 capability IDs W32-001…W32-010 are recorded in
`WINDOWS_1.0.32_REFERENCE.md`. Mac statuses remain open until paired UI and
workflow evidence is attached.

| Area | Status | Evidence / required work |
|---|---|---|
| PDF open/render/search/thumbnail/bookmark (W32-001) | PARTIAL (P1) | Bundle launches; full workflow click-test with the Windows reference is still required. |
| Edit/annotate/page operations/export (W32-002…W32-004, W32-007) | PARTIAL/MISSING (P0/P1) | Source paths exist; original-text editing and Office/print parity remain unverified. |
| OCR/AI/TTS (W32-005…W32-006) | PARTIAL (P1) | Must test real documents, loading/error/cancel states and provider failures. |
| Signing (W32-008) | PARTIAL (P0) | USB token and real middleware have not been tested on this machine. |
| License/update (W32-009) | PASS for v1 verification; PARTIAL for B53 delta | 8 security tests pass; delta must remain disabled until Mac bundle patching is proven safe. |
| ScanDoc transfer (W32-010) | PARTIAL (P1) | Must test QR, send/receive, timeout, retry and malformed pairing code. |

No untested item is declared PASS. PR #1's failing CI is tracked separately in
`WINDOWS_1.0.32_REFERENCE.md`; it must be resolved before final release sign-off.
