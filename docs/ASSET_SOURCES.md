# Asset Sources

Phase 0 status: asset provenance is not yet clean enough for commercial release.

Current assets:

- `assets/icons/*.svg`
- `download_icons.py` indicates the icons were downloaded from Microsoft Fluent UI System Icons, but the project does not yet include the upstream license text or exact source commit.
- Duplicate `*.svg.svg` files from the prototype were removed during Phase 0.2.

Required before release:

- Replace icons with a documented permissive set or custom-designed brand assets.
- Store original source files for logo/icon/UI brand kit.
- Add license text and attribution where required.
- If keeping Fluent UI icons, pin the upstream source commit and include the upstream license in `LICENSES.md` / `NOTICE.md`.

PDF.js:

- `third_party/pdfjs` is a Phase 0.4 migration copy from the previously packaged `pdfjs_viewer/pdfjs` directory.
- It must be replaced with an official PDF.js distribution pinned by version/source commit before commercial release.
- Keep `third_party/pdfjs/LICENSE` and all license files under `web/`.
