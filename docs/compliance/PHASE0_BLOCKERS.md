# Phase 0 Completion Blockers

## Resolved in Phase 0

- [x] Signing provider split by OS: `WindowsPkcs11Provider` (System32/SysWOW64 DLLs)
      and `MacOSPkcs11Provider` (.dylib/.so middleware) in `packages/signing/`.
- [x] Font resolution moved to `packages/platform/fonts.py` — no more hardcoded
      `C:\Windows\Fonts` in shared code.
- [x] `core/pkcs11.py` is now a thin shim; all OS-specific logic removed from shared layer.
- [x] Shared signing utilities in `packages/signing/shared.py` — no OS assumptions.
- [x] `main.py` UI font resolved per OS (Segoe UI on Windows, SF Pro Text on macOS).
- [x] PDF.js version identified: 5.6.205 (Apache 2.0). Source record updated.
- [x] Qt imported exclusively via `packages.qt_compat` throughout app code.
- [x] PDF operations isolated via `packages.pdf_engine` abstraction.
- [x] `pdfjs-viewer-pyqt6` GPL wrapper removed.
- [x] `PyQt6` direct imports removed; `PySide6` is the target binding.

## Must Resolve Before Commercial Release

- [ ] Download official PDF.js 5.6.205 from Mozilla to establish clean chain of custody.
- [ ] Verify non-AGPL PDF edit pipeline with fixture tests; do not ship legacy PyMuPDF engine.
- [ ] Complete password decrypt/save support through a compliant non-AGPL library (pikepdf).
- [ ] Pin Fluent UI icon source/license commit or replace all icons with owned brand assets.
- [ ] Generate SBOM (`pip-licenses` + CycloneDX) from final build environment.
- [ ] Review PySide6/Qt LGPL obligations, QtWebEngine/Chromium notices, and deployment requirements.
- [ ] Keep PyKCS11 out of commercial builds unless legal review approves optional legacy plugin.
- [ ] Add EULA, Privacy Policy, Third-party Notices, and enterprise update/license terms.
- [ ] Smoke test on macOS: app launch, PDF load, page render, search, signing flow.
- [ ] Smoke test on Windows: confirm adapter still reads DLL and font correctly after split.

## Phase Split Gate

Phase 1 (Windows/macOS/VPS stream split) is permitted when:
- Shared code contains zero OS-specific path assumptions.
- Compliance checklist above is resolved or explicitly deferred with written rationale.
- At least basic smoke tests pass on both platforms.
