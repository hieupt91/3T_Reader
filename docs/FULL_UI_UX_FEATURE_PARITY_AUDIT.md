# Full UI/UX & Feature Parity Audit — Windows → macOS

## Mandate

Windows is the **master functional reference**. macOS is the implementation.
The target is 100% functional, workflow and important-state parity, while the
Mac interface remains native to macOS rather than a visual copy of Windows.

No feature may be omitted, downgraded or declared unnecessary without an
explicit product decision. A feature is not complete merely because source
code or a similarly named function exists.

## Evidence standard

Audit as a real user, not only by reading code:

1. Build and launch the Windows reference and macOS build.
2. Walk every interactive UI surface on both applications.
3. Exercise each workflow using real files, then verify saved/reopened output.
4. Capture evidence: screenshots, test result, log, defect reproduction or
   explicit manual-pass note for every matrix row.
5. A `PARTIAL` result is unfinished. Do not claim parity until a retest is
   marked `PASS`.

If a Mac build/signing environment is unavailable, record the exact blocker;
do not replace real UI testing with a source-only conclusion.

## Required deliverables

Create and maintain these reports in `docs/parity_audit/`:

1. `FEATURE_PARITY_REPORT.md`
2. `UI_UX_PARITY_REPORT.md`
3. `WORKFLOW_PARITY_REPORT.md`
4. `SETTINGS_PARITY_REPORT.md`
5. `SHORTCUT_PARITY_REPORT.md`
6. `BUG_REPORT.md`
7. `MISSING_FEATURES.md`
8. `IMPLEMENTATION_REPORT.md`
9. `FINAL_REGRESSION_REPORT.md`

Every report must state date, tested build/version, environment, tester,
evidence location and totals. Never replace a previous report silently.

## Shared status vocabulary

Use exactly one of:

| Status | Meaning |
|---|---|
| `PASS` | Same user capability and workflow; tested successfully. |
| `PARTIAL` | Exists but lacks a required state, path or result. |
| `MISSING` | Windows capability has no Mac equivalent. |
| `BROKEN` | Visible/implemented but fails under test. |
| `DIFFERENT UX` | Capability works but Mac flow needs native-UX review. |
| `WINDOWS ONLY` | Requires an explicit platform/business reason and approval. |
| `MAC NATIVE EQUIVALENT` | Same capability via an intentionally native Mac pattern. |

Every non-`PASS` item needs severity (`P0`–`P3`), owner, required outcome,
implementation plan and retest criterion.

## Feature Parity Matrix

Record all features, including hidden entry points:

| ID | Windows | macOS | Status | Windows UI location | Mac UI equivalent | Workflow evidence | Required work |
|---|---|---|---|---|---|---|---|
| F001 | | | | | | | |

Inventory sources include main menu, toolbar/ribbon, sidebar, tab bar, status
bar, menus inside dialogs, overflow/drop-down controls, context menu, hover,
double-click, long press, keyboard shortcut, drag/drop, settings/preferences,
empty/error/loading states and file association entry points.

## UI inventory and click-everything rule

For every screen/component document its location, purpose, state, shortcut,
tooltip/accessibility label and evidence. Click, right-click, hover, focus,
keyboard-activate, drag and resize every available control. An icon without
text is not exempt: trace its real workflow until its purpose is known.

### Main window

Audit title, toolbar, navigation, sidebar, content area, status/bottom controls,
tab bar, split view, search/filter/sort, context menu, resize and fullscreen.

### Toolbar

For every button, icon, dropdown, segmented control, search field and overflow
item test: normal, hover, active, disabled, tooltip, click result, loading,
error, confirmation and shortcut.

### Menus

Audit App, File, Edit, View, Window, Help, document/tab/context menus, toolbar
menus and “More” menus. Click every menu item, including disabled cases and
items reachable only after selection.

### Dialogs, sheets and popups

Test open/close/cancel/confirm, keyboard focus, default action, validation,
error/retry, success, window resize and parent-window blocking behavior.

## Workflow matrix

Each Windows workflow must be run end-to-end on Mac:

| ID | Workflow | Windows evidence | macOS result | Status | Gap / retest |
|---|---|---|---|---|---|
| W001 | Open → edit → save → reopen | | | | |

Minimum workflow families:

- application launch, recent files, multiple documents/tabs/windows;
- open/import/drag-drop, unsupported/missing/corrupt/locked files;
- view/search/navigate/zoom/fullscreen/resize;
- edit/annotate/undo/redo/save/save-as/reopen;
- page operations, print, export/import, OCR, AI, signing and ScanDoc transfer;
- licensing/activation, update, preferences, logs/error recovery;
- cancel, retry, interruption and recovery paths.

Use the same small, large, multi-page, image-heavy, scan, OCR, metadata,
annotation, form (if supported), corrupt and permission-restricted documents
where Windows supports them.

## State matrix

For every meaningful screen/control/workflow record at least:

- normal, hover, selected/active, focused and disabled;
- loading/processing and cancel;
- empty/no-data;
- success;
- error/retry/recovery;
- drag start, drag target and drop;
- small, medium, large and fullscreen window sizes.

Check clipping, overlap, hidden actions, tab/sidebar behavior, PDF scaling,
dialog positioning and layout readability at every size.

## Settings / Preferences parity

Inventory every Windows setting and map it to a Mac preference UI or native
equivalent: General, Appearance, Language, File handling, PDF, Import/Export,
OCR, Performance, Storage, Cloud/Sync, Keyboard shortcuts, Notifications,
Security, Advanced and About. A setting that is unavailable on Mac remains
`MISSING` until the product owner explicitly approves a platform exception.

## Shortcut parity

Create a complete action table; include application-specific shortcuts, menu
accelerators, dialog shortcuts and contextual shortcuts. Mac should use native
command mappings where appropriate (`Cmd+O`, `Cmd+S`, `Cmd+W`, `Cmd+F`) while
retaining the Windows action/capability. Verify conflicts and focus behavior.

| Action | Windows shortcut | macOS shortcut | Tested | Status |
|---|---|---|---|---|

## macOS-native UX review

Functional parity does not require pixel parity. For each mapped screen assess:

- window lifecycle and multiple-window behavior;
- native toolbar/sidebar/navigation split patterns;
- sheet vs modal dialog choice;
- menu-bar placement and Command shortcuts;
- right-click/trackpad context interaction;
- drag/drop and native file picker;
- fullscreen, tabs and window management;
- information hierarchy, grouping, spacing, typography, icon/button size and
  accessibility.

Document `DIFFERENT UX` when the Mac path can achieve the same result but is
not yet naturally discoverable or consistent with macOS conventions.

## Accessibility and performance

Audit keyboard-only navigation, tab order, focus visibility, VoiceOver labels,
accessibility identifiers, contrast, Dynamic Type/scale behavior and tooltip
availability. Measure perceived startup, opening normal/large documents,
multiple documents, search, scrolling, OCR, import/export, rendering, CPU and
memory. If Windows provides progress/background feedback, Mac needs an
equivalent understandable state.

## Error UX

Intentionally test invalid input, missing/corrupt/locked files, permission
denied, disk/full write failure where safely reproducible, network offline,
cancelled operations and interrupted processes. Report whether the user sees
a clear cause, next action, Retry/Cancel/recovery option and preserved data.

## Implementation and release gate

Prioritize gaps:

- `P0`: Windows workflow unavailable/broken with critical user impact.
- `P1`: Important feature incomplete or unreliable.
- `P2`: Native UX/discoverability problem.
- `P3`: visual polish or minor refinement.

Implement every `P0`, `P1`, `MISSING`, `BROKEN` and important `PARTIAL` item;
build macOS; rerun full audit and regression; then compare against Windows
again. A build that launches is not evidence of parity.

The audit may close only when all Windows UI/features/workflows/settings/
shortcuts have an inventory, every interactive surface has evidence, no P0 or
P1 remains, no primary workflow is partial, and the final regression report is
green. Any untested Mac-only runtime item must remain explicitly open.
