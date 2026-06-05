# ADR 001 - PDF Engine Choice

## Status

Accepted.

## Decision

3T Reader uses the internal PDF engine abstraction in `packages/pdf_engine` with Pdfium as the primary rendering backend and pikepdf/reportlab for edit/save operations.

## Rationale

- Pdfium gives stable page rendering for the embedded PDF.js/Qt workflow.
- pikepdf provides reliable structural PDF edits and atomic save helpers.
- Keeping engine access behind `packages/pdf_engine` avoids binding UI code to one low-level library.

## Consequences

- UI and actions should call the engine abstraction instead of importing rendering libraries directly.
- Regression tests should cover behavior through `packages/pdf_engine`.
