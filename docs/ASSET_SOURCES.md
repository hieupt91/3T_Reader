# Asset Sources

Phase 0 status: asset provenance is not yet clean enough for commercial release.

Current assets:

- `assets/icons/*.svg`
- Several duplicate `*.svg.svg` files exist from the prototype.
- `download_icons.py` indicates the icons were downloaded from Microsoft Fluent UI System Icons, but the project does not yet include the upstream license text or exact source commit.

Required before release:

- Replace icons with a documented permissive set or custom-designed brand assets.
- Store original source files for logo/icon/UI brand kit.
- Add license text and attribution where required.
- Remove duplicate or unused SVG files.
- If keeping Fluent UI icons, pin the upstream source commit and include the upstream license in `LICENSES.md` / `NOTICE.md`.
