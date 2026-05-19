# Phase 0 Completion Blockers

The repository is cleaner, but Phase 0 is not complete until the following items are resolved or explicitly accepted as post-Phase-0 work.

## Must Resolve Before Commercial Release

- Verify non-AGPL PDF edit pipeline with fixture tests; do not ship legacy PyMuPDF engine.
- Complete password decrypt/save support through a compliant non-AGPL library.
- Replace migration PDF.js bundle with official pinned PDF.js release.
- Pin Fluent UI icon source/license or replace all icons with owned brand assets.
- Generate SBOM and license notices from the final build environment.
- Review PySide6/Qt LGPL obligations, QtWebEngine/Chromium notices, and deployment requirements.
- Keep PyKCS11 out of commercial builds unless legal review approves optional legacy plugin.
- Add EULA, Privacy Policy, Third-party Notices, and enterprise update/license terms.

## Can Move To Split Gate After Review

- Shared code imports Qt through `packages.qt_compat`.
- PDF operations go through `packages.pdf_engine`.
- Signing UI goes through `packages.signing`.
- License/update placeholders exist for Linux VPS.
- Windows/macOS have not forked UI/UX or feature logic.

## Recommended Next Technical Steps

1. Add fixture tests for non-AGPL PDF edit pipeline.
2. Replace PDF.js migration copy with official release.
3. Add basic smoke tests for app startup and PDF engine selection.
4. Create final Phase 0 completion report.
5. Ask for approval before splitting Windows/macOS/VPS streams.
