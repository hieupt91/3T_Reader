# Workflow Convention

This document defines the project convention for moving from Phase 0 into
Phase 1 and Phase 2 without mixing foundations, platform branches, or release
artifacts.

## Core rule

- Phase 0 is the shared foundation.
- Phase 1 is the platform split.
- Phase 2 is product hardening and release work.
- Do not keep developing Phase 0 and Phase 1 in the same working tree.

## Source of truth

- `main` keeps the canonical history.
- Phase milestones are recorded by tags.
- Active development happens on phase-specific branches or workspaces.
- Docs must match code. If docs and code disagree, code wins.

## Phase tags

Use tags to mark immutable milestones:

- `phase0-closed`
- `phase1-start`
- `phase1-win-ready`
- `phase1-mac-ready`
- `phase2-start`

Rules:

- A tag is a snapshot, not a branch.
- Never rewrite or reuse a phase tag for a different meaning.
- Create the next phase from the last closed tag, not from a dirty branch head.

## Branch naming

Use branch names that describe purpose, not local machine names:

- `phase1-win`
- `phase1-mac`
- `phase1-shared`
- `phase1-backend`
- `phase2-release`

Rules:

- One branch = one responsibility.
- Do not let a Windows branch absorb macOS-only behavior.
- Do not let a macOS branch absorb Windows-only behavior.
- Shared code changes go through `phase1-shared` first when they affect both desktop targets.

## Workspace naming

Use one clean workspace per active stream:

- `3T_Reader_Phase0` for the closed foundation only.
- `3T_Reader_Phase1_Win` for Windows development.
- `3T_Reader_Phase1_Mac` for macOS development.
- `3T_Reader_Phase1_Shared` for common changes if needed.
- `3T_Reader_Phase1_Backend` for Linux VPS backend work.

Rules:

- Do not keep Phase 0 and Phase 1 edits in the same folder.
- Do not copy a working tree from one platform branch into another and then continue editing both.
- Each workspace must be reproducible from the tag that created it.

## Split policy

Phase 1 begins only when all of the following are true:

- Phase 0 is closed in `docs/PHASE0_CLOSURE.md`.
- `docs/compliance/PHASE0_BLOCKERS.md` contains only explicit deferred items.
- Shared code contains no Windows-specific path assumptions.
- Platform adapters exist for paths, single instance behavior, font resolution, and signing.
- The non-AGPL PDF path is the default path.
- The repo has a clear compliance manifest.

## Desktop split policy

Desktop branches must share:

- UI layout and workflow.
- command names and toolbar order.
- document open/edit/search/print behavior.
- PDF engine abstraction.
- license/update client contracts.

Desktop branches may differ only in:

- app bundle layout.
- installer packaging.
- code signing and notarization.
- native token/middleware integration.
- OS-specific file paths and system fonts.

## Shared code policy

The shared layer may contain:

- pure business logic.
- PDF engine interfaces.
- signing interfaces.
- platform-neutral compliance helpers.
- cross-platform UI state and document actions.

The shared layer may not contain:

- hardcoded Windows paths.
- macOS-only bundle assumptions.
- OS-specific installer logic.
- platform-specific middleware discovery.
- release signing or notarization commands.

## Merge policy

- Shared fixes start in the shared branch, then flow into Windows and macOS.
- Platform-specific fixes stay in the relevant platform branch.
- Never merge a platform branch into another platform branch directly unless the change is explicitly shared and reviewed.
- Rebase or cherry-pick small fixes when needed; avoid wide cross-branch copying.

## Release policy

- Phase 1 produces platform-ready streams.
- Phase 2 produces release candidates.
- Commercial release happens only after the compliance checklist and target-hardware smoke tests pass.

## Recommended handoff sequence

1. Close Phase 0 with `phase0-closed`.
2. Create `phase1-win`, `phase1-mac`, `phase1-shared`, and `phase1-backend` from that tag.
3. Make shared changes in `phase1-shared`.
4. Merge shared changes into both desktop branches.
5. Keep backend work isolated in the backend branch.
6. When platform streams are stable, cut `phase2-start`.

## Practical rule for this project

If a change affects both Windows and macOS behavior, design the API once in shared code and implement the OS-specific detail in the adapter. Do not duplicate business logic across branches.
