# Workflow parity report

Date: 2026-08-15. Windows is the master reference. No end-to-end workflow is marked PASS until run on both builds with the same fixture.

| Workflow family | Status | Required evidence |
|---|---|---|
| Launch/recent/tabs/windows | PARTIAL (P1) | Screen recording or screenshots plus reopen result. |
| Open/import/drag-drop/invalid files | MISSING (P1) | Test unsupported, missing, corrupt, locked and permission-denied files. |
| View/search/zoom/fullscreen/resize | PARTIAL (P1) | Same fixture and shortcut table on Windows/Mac. |
| Edit/annotate/undo/save/reopen | PARTIAL (P0) | Compare reopened PDF output, not only on-screen overlay. |
| Pages/print/export/OCR/AI | PARTIAL (P1) | Capture output files, error/retry/cancel behavior. |
| Signing/license/update/transfer | PARTIAL (P0) | Real token/middleware and transfer failure paths required. |

