# Bug report

Date: 2026-08-15

## B-001 — PyInstaller hidden import warning

- Status: BROKEN (P1)
- Evidence: build log reports `Hidden import 'packages.platform.macos' not found`.
- Impact: the bundle builds, but Mac-specific runtime packaging has not been proven complete.
- Fix plan: inspect `packages/platform` module names, correct the spec hidden import, rebuild, launch and run platform smoke tests.
- Retest: build log has no missing Mac hidden import and packaged app exercises paths/fonts/single-instance behavior successfully.

## B-002 — Parity evidence incomplete

- Status: PARTIAL (P1)
- Evidence: app launch only; no click-everything or Windows/Mac paired workflow evidence yet.
- Fix plan: complete all matrices and attach screenshots/logs/output fixtures.
