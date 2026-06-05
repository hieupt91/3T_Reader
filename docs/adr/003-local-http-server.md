# ADR 003 - Local HTTP Server For PDF.js

## Status

Accepted.

## Decision

3T Reader serves PDF.js and PDF documents through `app.local_server` on localhost instead of loading PDF.js modules from `file://`.

## Rationale

- Modern PDF.js uses ES modules that do not load reliably from `file://` in QtWebEngine.
- A localhost server gives consistent URL resolution and security checks.
- Tests can validate static-file restrictions and path traversal behavior.

## Consequences

- Local server security is release-critical.
- Viewer URLs should be built through `LocalPDFJSServer`.
