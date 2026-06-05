# ADR 004 - Signing Architecture

## Status

Accepted.

## Decision

Digital signing uses pyHanko for PDF signature creation and token/PFX integration through app-level signing actions.

## Rationale

- pyHanko is purpose-built for PDF signatures and validation workflows.
- Separating signing actions from edit actions keeps signed-document warnings explicit.
- Token/PFX flows can share PDF placement and preview helpers.

## Consequences

- Edits after signing must warn users that signatures can be invalidated.
- Signing tests should focus on generated PDF structure and validation state.
