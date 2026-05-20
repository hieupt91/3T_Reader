# Phase 1 Dual-Machine Workflow

This document is the operational guide for Phase 1 dual-machine development.
It implements the policy defined in [`WORKFLOW_CONVENTION.md`](WORKFLOW_CONVENTION.md).
Read that document first — this one is the hands-on execution of it.

## Goal

- Use the closed Phase 0 snapshot as the common starting point.
- Develop macOS on the Mac machine.
- Develop Windows on the Windows machine.
- Keep shared changes coordinated without mixing working trees.

## Fixed Phase 0 baseline

Phase 0 is closed and tagged:

- Tag: **`phase0-closed`**
- Commit: `67062d3 chore(phase0): final cleanup — remove dead code, pin deps, add workflow convention`

Do not continue feature work in the Phase 0 workspace after this tag.

## Branch model

Use one branch per active stream:

- `phase1-mac` on the Mac machine.
- `phase1-win` on the Windows machine.
- `phase1-shared` only when a change affects both desktop platforms.
- `phase1-backend` later, when VPS work begins.

## Machine rules

### Mac machine

- Work only on `phase1-mac`.
- Do not edit Windows-only adapters in this workspace.
- Keep macOS bundle, notarization, token middleware, and mac fonts here.

### Windows machine

- Work only on `phase1-win`.
- Do not edit macOS-specific bundle or notarization code here.
- Keep Windows DLL token lookup, installer, and Windows fonts here.

### Shared work

- If a change affects both platforms, create or update `phase1-shared`.
- Merge or cherry-pick the shared change into both platform branches.
- Keep the shared layer free of OS-specific path assumptions.

## Recommended setup on each machine

### On Mac

1. Clone the repo.
2. Checkout `phase0-closed`.
3. Create `phase1-mac`.
4. Develop only macOS-specific work and shared fixes that are explicitly intended for Mac.

### On Windows

1. Clone the repo.
2. Checkout `phase0-closed`.
3. Create `phase1-win`.
4. Develop only Windows-specific work and shared fixes that are explicitly intended for Windows.

## Practical git flow

### 1. Phase 0 tag — already created

The tag `phase0-closed` is already on commit `67062d3`.
If you have a remote, push it once:

```bash
git push origin phase0-closed
```

### 2. On Mac

```bash
git clone <repo-url> 3T_Reader_Phase1_Mac
cd 3T_Reader_Phase1_Mac
git checkout phase0-closed
git checkout -b phase1-mac
```

### 3. On Windows

```bash
git clone <repo-url> 3T_Reader_Phase1_Win
cd 3T_Reader_Phase1_Win
git checkout phase0-closed
git checkout -b phase1-win
```

### 4. For shared changes

```bash
git checkout -b phase1-shared phase0-closed
```

Then merge or cherry-pick into `phase1-mac` and `phase1-win`.

## What belongs where

### `phase1-mac`

- macOS bundle and app-path behavior
- macOS installer packaging
- code signing and notarization
- macOS token middleware discovery
- macOS font resolution and UI polish if platform-specific

### `phase1-win`

- Windows app bundle / executable packaging
- Windows installer packaging
- code signing if needed
- Windows token middleware discovery
- Windows font resolution and UI polish if platform-specific

### `phase1-shared`

- UI and workflow behavior shared by both platforms
- PDF engine abstraction changes
- signing protocol changes
- license/update client contracts
- compliance docs and shared helpers

## Merge discipline

- Never copy the whole Mac tree into the Windows tree or vice versa.
- Never maintain divergent business logic in both platform branches.
- Shared behavior changes should happen once, then flow down to both branches.
- Platform-specific fixes stay platform-specific unless they clearly belong in shared code.

## Phase gate reminder

Phase 1 starts only after:

- Phase 0 is tagged and closed.
- The branch/workspace rule above is agreed.
- The team is ready to keep Mac work on Mac hardware and Windows work on Windows hardware.

## Simple mental model

- Phase 0: shared foundation.
- Phase 1: same product, two machines, two platform branches.
- Phase 2: packaging, hardening, release.

For the full Windows/macOS/Linux VPS split policy, see
[`PHASE1_3_STREAM_PLAN.md`](PHASE1_3_STREAM_PLAN.md).
