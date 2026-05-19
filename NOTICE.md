# Notices

3T Reader Phase 0 source cleanup.

This workspace contains prototype code and third-party dependencies that still require license review before commercial distribution.

Phase 0.4 notes:

- PDF.js is loaded directly from `third_party/pdfjs` by the internal viewer.
- `pdfjs-viewer-pyqt6` is no longer imported by app code and must not be included in commercial builds.
- PySide6 is the target Qt binding; LGPL compliance and third-party notices remain required.

Phase 0.7 notes:

- Manual third-party manifest added at `docs/compliance/THIRD_PARTY_MANIFEST.md`.
- The current PDF.js bundle is a migration copy and must be replaced with an official pinned release before commercial release.
- Icon source/license is not yet pinned.
