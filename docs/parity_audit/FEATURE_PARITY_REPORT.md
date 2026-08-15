# Feature parity report

Date: 2026-08-15  
Build: `origin/phase1-mac@8012431`, local unsigned macOS `.app/.dmg`  
Environment: macOS 13.7.8 x86_64, Python 3.14.6, PyInstaller 6.20.0  
Evidence: `dist/mac/3T Reader.app`, `dist/mac/3T_Reader_mac.dmg`, `tests/test_update_client_signature.py`

## Baseline result

| Area | Status | Evidence / required work |
|---|---|---|
| PDF open/render/search/thumbnail/bookmark | PARTIAL (P1) | Bundle launches; full workflow click-test with the Windows reference is still required. |
| Edit/annotate/page operations/export | PARTIAL (P1) | Source paths exist; must test save/reopen and output hashes on both platforms. |
| OCR/AI | PARTIAL (P1) | Must test real documents, loading/error/cancel states and provider failures. |
| Signing | PARTIAL (P0) | USB token and real middleware have not been tested on this machine. |
| License/update | PASS for v1 verification; PARTIAL for B53 delta | 8 security tests pass; delta must remain disabled until Mac bundle patching is proven safe. |
| ScanDoc transfer | PARTIAL (P1) | Must test QR, send/receive, timeout, retry and malformed pairing code. |

No untested item is declared PASS. Retest after the Windows/Mac workflow matrix is completed.
