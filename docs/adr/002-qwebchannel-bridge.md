# ADR 002 - QWebChannel Bridge

## Status

Accepted.

## Decision

Qt/Python communicates with PDF.js overlays through QWebChannel bridge objects registered by `app.webchannel`.

## Rationale

- QWebChannel gives typed callbacks from JavaScript to Python without polling files or local storage.
- It keeps inline edit, area pick, notes, and signature preview flows inside the viewer context.
- Shared bridge helpers reduce duplicate channel setup code.

## Consequences

- New viewer interactions should reuse `register_webchannel_object`.
- JavaScript bridge names must remain stable for injected assets.
