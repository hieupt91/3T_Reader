# Split Gate

Do not split implementation streams until Phase 0 is reviewed and the workflow convention is agreed.

The split point is reached when:

- Source workspace is clean.
- Brand is consistently `3T Reader`.
- License risks are documented.
- Manual third-party manifest exists and blockers are explicit.
- Platform adapter exists for app paths and single instance behavior.
- Update path no longer points to a public personal GitHub repo.
- Future package boundaries exist for platform, PDF engine, signing, license, update, and backend.

After approval, split work into:

- Windows desktop stream.
- macOS desktop stream.
- Shared desktop/core packages.
- Linux VPS backend stream.

The Windows/macOS streams must not fork UX or feature behavior. They should only differ in platform adapters, build, installer, signing, notarization, and native credential/token integration.

Before approving split, review `docs/compliance/PHASE0_BLOCKERS.md` and `docs/WORKFLOW_CONVENTION.md`.
