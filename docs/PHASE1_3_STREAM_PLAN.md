# Phase 1 Three-Stream Plan

This document defines how Phase 1 is split into three execution streams:

- Windows desktop
- macOS desktop
- Linux VPS backend

The purpose is to keep a single product direction while letting each platform
move at its own speed after the shared Phase 0 foundation is closed.

## Baseline

- Shared baseline tag: `phase0-closed`
- Phase 1 handoff tag: `phase1-start`

Do not start Phase 1 work from any source tree that is not based on one of
those closed snapshots.

## Stream ownership

### Windows stream

Branch: `phase1-win`

Machine: Windows desktop/laptop

Owns:

- Windows app packaging and executable layout
- Windows token middleware discovery
- Windows app-path behavior
- Windows-specific installer workflow
- Windows-specific code signing if needed
- Windows smoke tests

### macOS stream

Branch: `phase1-mac`

Machine: macOS desktop/laptop

Owns:

- macOS app bundle layout
- macOS token middleware discovery
- macOS app-path behavior
- macOS notarization and signing workflow
- macOS-specific packaging and deployment rules
- macOS smoke tests

### Linux VPS stream

Branch: `phase1-backend`

Machine: Linux server or VPS

Owns:

- license API
- update API
- device binding / activation services
- revocation and heartbeat services
- release manifest hosting
- audit logging
- admin endpoints

## Shared stream

Branch: `phase1-shared`

Owns:

- UI and workflow behavior that must match on Windows and macOS
- PDF engine boundary changes
- signing protocol/interface changes
- license client interface
- update client interface
- compliance/docs updates that affect all streams

Shared changes must be merged into both desktop streams when they affect the
desktop app surface.

## What must stay shared

These items must not drift between Windows and macOS:

- document open/save/search/edit workflow
- toolbar command order
- menu structure and command names
- PDF rendering behavior
- annotation and sign flow semantics
- license validation contract
- update check contract

## What may differ by stream

### Windows may differ in

- installer format
- executable bundle layout
- token middleware discovery paths
- Windows-specific fonts and system integration
- Windows-specific signing and shell integration

### macOS may differ in

- `.app` bundle structure
- notarization and code signing flow
- token middleware discovery paths
- macOS fonts and system integration
- macOS file association and bundle metadata

### Linux VPS may differ in

- API implementation details
- database schema and migrations
- deployment model
- server-side release/update storage
- admin panel and audit tooling

## Update policy

### Update shared docs first when behavior changes

If a change affects the project rules or stream boundaries, update:

- `docs/WORKFLOW_CONVENTION.md`
- `docs/PHASE1_DUAL_MACHINE_WORKFLOW.md`
- `docs/PHASE0_CLOSURE.md`
- this file

### Update stream docs when stream responsibilities change

If a stream gains or loses responsibility, update:

- `docs/PHASE1_3_STREAM_PLAN.md`
- any stream-specific README or handoff note

### Update code before release notes

If the behavior is real in code, update the code first.
If the behavior is only planned, keep it in docs as planned work.

### Update branches when a shared fix lands

If a shared fix lands in `phase1-shared`:

1. merge or cherry-pick it into `phase1-win`
2. merge or cherry-pick it into `phase1-mac`
3. record the change in the stream notes if needed

## Implementation order

Recommended sequence:

1. Keep `phase0-closed` frozen.
2. Let macOS continue on `phase1-mac`.
3. Let Windows continue on `phase1-win`.
4. Start `phase1-backend` only when the desktop contract is stable.
5. Keep shared contract changes in `phase1-shared`.

## Checkpoint policy

Use a checkpoint when a stream reaches a meaningful stage:

- `win-checkpoint-1`
- `mac-checkpoint-1`
- `backend-checkpoint-1`

Use checkpoints for:

- packaging progress
- smoke test progress
- API contract changes
- adapter boundary changes
- compliance or license changes

## Release synchronization

Do not release one desktop platform on a contract that the other platform does
not support yet unless the difference is explicitly documented.

Before a release candidate:

- desktop feature parity must be reviewed
- shared contract changes must be merged to both desktop branches
- VPS APIs must match the desktop client contract
- compliance artifacts must be updated

## Reporting format

When reporting progress, use the same structure for all three streams:

- branch name
- machine used
- files changed
- contract changes
- tests run
- blockers
- next update required

## Practical rule

If the same product behavior is expected on both Windows and macOS, the change
should first be expressed as a shared contract. Then each platform branch
implements its own OS-specific adapter behind that contract.
