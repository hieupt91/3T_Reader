# Phase 0 Scope

Phase 0 goal: convert the existing Windows-oriented prototype into a clean, auditable foundation for commercial Windows + macOS + Linux VPS development.

In scope:

- Remove build/runtime/tooling artifacts from the working source.
- Fix repo hygiene and `.gitignore`.
- Standardize brand names to `3T Reader`.
- Document license risks and asset provenance gaps.
- Prepare platform adapters for OS-specific behavior.
- Prepare placeholder modules for PDF engine, signing, license, update, and backend.
- Isolate direct PyMuPDF usage behind `packages/pdf_engine`.
- Maintain compliance notes in `docs/compliance`.

Out of scope:

- Final Windows/macOS directory split.
- Linux VPS implementation.
- AI/OCR implementation.
- Full dependency replacement for GPL/AGPL libraries.
- Commercial installer signing/notarization.

Start splitting streams only after this scope is complete and reviewed.

Current blocker list: `docs/compliance/PHASE0_BLOCKERS.md`.
