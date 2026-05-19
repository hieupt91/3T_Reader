# PDF.js Source Record

## Current Bundle

- **Location:** `third_party/pdfjs`
- **PDF.js version:** 5.6.205
- **Source URL:** https://github.com/mozilla/pdf.js/releases/tag/v5.6.205
- **License:** Apache License 2.0

Origin: migrated from previous packaged dependency `pdfjs_viewer/pdfjs`.
The GPL wrapper `pdfjs-viewer-pyqt6` is not used; app integrates PDF.js directly
via `app/pdf_viewer.py` using `QWebEngineView`.

## Included License Files

- `third_party/pdfjs/LICENSE` — Apache 2.0 (PDF.js main)
- `third_party/pdfjs/web/cmaps/LICENSE`
- `third_party/pdfjs/web/iccs/LICENSE`
- `third_party/pdfjs/web/standard_fonts/LICENSE_FOXIT`
- `third_party/pdfjs/web/standard_fonts/LICENSE_LIBERATION`
- `third_party/pdfjs/web/wasm/LICENSE_*`

## Required Before Commercial Release

- [ ] Download official PDF.js 5.6.205 distribution from Mozilla and replace current bundle
      to establish clean chain of custody.
- [ ] Record source commit: `git clone https://github.com/mozilla/pdf.js` and verify
      tag `v5.6.205` matches bundled build checksums.
- [ ] Verify all nested license files remain present after replacement.
- [ ] Add sha256 checksums of `build/pdf.mjs` and `web/viewer.mjs` to this file.
