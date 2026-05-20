# Mac to Windows Handoff Guide

Date: 2026-05-20

This document is the practical handoff guide for moving from the closed Phase 0
foundation on this Mac to parallel Phase 1 development on a Windows machine.

## Current Mac machine snapshot

- Hostname: `MacBook-Pro-cua-HIEUPC.local`
- User: `hieupc`
- OS: macOS 13.7.8
- Kernel: Darwin 22.6.0
- Hardware: MacBook Pro, Model Identifier `MacBookPro14,1`
- CPU: Intel Core i5, 2.3 GHz, 2 cores
- Memory: 8 GB
- Xcode path: `/Applications/Xcode.app/Contents/Developer`
- Working directory: `/Users/hieupc`
- Phase 0 repo path: `/Volumes/DATA/Công Việc/3t reader/3T_Reader_Phase0`

## Current repo state on this Mac

- Phase 0 technical foundation is closed.
- Phase 0 baseline tag: `phase0-closed`
- Phase 0 baseline commit: `67062d3 chore(phase0): final cleanup`
- Phase 1 start commit/tag: `038f480 Phase 1 workflow handoff docs`
- Existing tag: `phase1-start`
- Branches currently prepared in this workspace:
  - `main`
  - `phase1-mac`
  - `phase1-shared`

## What this Mac workspace is for now

- Continue macOS work on `phase1-mac`.
- Use `phase1-shared` only for cross-platform changes that must flow into both
  desktop branches.
- Do not continue Phase 0 feature work here.
- Do not use `reader_pdf_extracted` as an active workspace.

## What the Windows machine should do

The Windows machine must start from the same closed Phase 0 baseline.

Recommended Windows branch:

- `phase1-win`

Recommended Windows workspace name:

- `3T_Reader_Phase1_Win`

## Preferred transfer methods to Windows

Use one of these, in order of preference:

1. Git remote clone from the same repository.
2. Git bundle if there is no convenient remote access.
3. A plain archive only if the full `.git` history and tags are preserved.

Do not move only the source files without tags/history, because Phase 1 needs
the exact `phase0-closed` baseline.

## If a Git remote exists

On the Mac:

```bash
git tag phase0-closed 67062d3
git push origin phase0-closed
git push origin phase1-start
```

On Windows:

```bash
git clone <repo-url> 3T_Reader_Phase1_Win
cd 3T_Reader_Phase1_Win
git checkout phase0-closed
git checkout -b phase1-win
```

## If no Git remote is available

On the Mac:

```bash
git bundle create phase0-closed.bundle phase0-closed
```

Move `phase0-closed.bundle` to Windows.

On Windows:

```bash
git clone phase0-closed.bundle 3T_Reader_Phase1_Win
cd 3T_Reader_Phase1_Win
git checkout -b phase1-win
```

## If you must use a file copy

Only copy a workspace if all of the following are true:

- the copy includes the full `.git` directory,
- the copy includes the `phase0-closed` tag,
- the copy excludes build artifacts and temp files,
- the copy is used only to bootstrap a new Windows repo checkout.

Do not continue editing from the copied tree as if it were the source of truth.

## Windows setup checklist

After checkout on Windows:

- Confirm `git branch --show-current` is `phase1-win`.
- Confirm `git tag --points-at HEAD` includes `phase0-closed`.
- Confirm the repo root still matches the Phase 0 handoff docs.
- Create the Windows work area separate from the Mac workspace.
- Keep Windows-only adapters, packaging, and token middleware work in the
  Windows branch.

## What not to bring over

- Do not carry `dist/`, `build/`, cache, or virtual environment directories.
- Do not carry macOS bundle-specific assumptions into Windows.
- Do not reuse the Phase 0 working tree as the Windows development tree.

## Shared work rule

When both platforms need the same change:

- create the change in `phase1-shared`,
- merge or cherry-pick into `phase1-mac`,
- merge or cherry-pick into `phase1-win`.

## Summary

- Mac continues on `phase1-mac`.
- Windows starts from `phase0-closed` and creates `phase1-win`.
- Shared changes go through `phase1-shared`.
- Phase 0 stays locked as the common baseline.
