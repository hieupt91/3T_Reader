# PDF.js Source Record

Phase 0.7 status: incomplete source provenance.

Current bundle:

- Location: `third_party/pdfjs`
- Origin: copied from the previous packaged dependency directory `pdfjs_viewer/pdfjs`.
- Reason: remove app dependency on the GPL `pdfjs-viewer-pyqt6` wrapper while keeping direct PDF.js integration possible.

Included license files:

- `third_party/pdfjs/LICENSE`
- `third_party/pdfjs/web/cmaps/LICENSE`
- `third_party/pdfjs/web/iccs/LICENSE`
- `third_party/pdfjs/web/standard_fonts/LICENSE_FOXIT`
- `third_party/pdfjs/web/standard_fonts/LICENSE_LIBERATION`
- `third_party/pdfjs/web/wasm/LICENSE_*`

Required before release:

- Download official PDF.js distribution from Mozilla.
- Record release version and source URL.
- Record source commit or release tag.
- Replace the migration copy.
- Verify all nested license files remain present.
