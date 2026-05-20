# Phase 0 Closure Assessment

Date: 2026-05-20

## Decision

Phase 0 is **closed as a technical foundation phase**.

Phase 0 is **not** a commercial release gate. Several commercial-release items remain intentionally deferred.

## What Phase 0 achieved

- The repo is cleaned and structured as a shared foundation for Windows and macOS.
- Windows-only assumptions have been removed from the shared layer.
- Platform-specific behavior now lives behind adapters.
- PDF operations are behind a PDF engine abstraction.
- Qt is accessed through `packages.qt_compat`.
- Signing is behind a provider protocol and OS-specific providers.
- GPL wrapper usage was removed from the app boundary.
- The non-AGPL PDF path is the default path.
- Compliance and third-party tracking files exist.
- Smoke tests for the foundation pass locally.

## What Phase 0 does not claim

- It does not claim commercial release readiness.
- It does not claim all third-party source custody is pinned to final vendor archives.
- It does not claim all legal/compliance notices are final.
- It does not claim real hardware smoke tests on both target desktop platforms are complete.
- It does not claim the final Windows/macOS/VPS split has begun.

## Deferred commercial blockers

These items are still required before a commercial release:

- Official PDF.js source custody pinning from Mozilla.
- Final SBOM generation from the build environment.
- Final legal notices: EULA, Privacy Policy, Third-party Notices, enterprise update/license terms.
- Fixture validation of the PDF edit pipeline with real documents.
- Real macOS and Windows smoke tests on target hardware.
- Final icon/license provenance pin or replacement with owned assets.
- Final Qt/WebEngine licensing review for the chosen packaging model.

## Result

Phase 0 is a valid and usable base for Phase 1 planning.
Phase 1 should start from this repo state, not from the original prototype.

The operational handoff rules are defined in `docs/WORKFLOW_CONVENTION.md`.
