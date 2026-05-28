# 3T Reader / 3T Document AI - Feature Matrix and Mac Parity Handover

Date: 2026-05-28

Purpose:
- One consolidated reference for what is already in the product now.
- One checklist for what the macOS team must match to reach Windows parity.
- One release-facing summary of the current commercial direction.

This document summarizes work done from 2026-05-22 to 2026-05-28 and the
current code status at this repo snapshot.

## 1. Current product snapshot

The project is no longer just a PDF reader prototype.

It now has:
- Desktop UI shell with ribbon, menus, sidebar, tabs, theme support, recent files, and app branding.
- PDF core with open, render, search, thumbnails, bookmarks, zoom, rotate, print, and page navigation.
- PDF editing and annotation with text/image insert, draw, highlight, underline, strikeout, redact, watermark, page numbers, split/merge/delete/extract, password handling, and export.
- Signing flows for USB token, PKCS#11 middleware, PFX/P12, signature field, handwritten/signature stamp, and signature verification.
- AI layer for translate, summarize, chat with PDF, semantic search, and provider abstraction.
- VPS-backed license/update flow with activation, validation, heartbeat, revoke, update check, and language pack download.

## 2. What was added or hardened from 2026-05-22 onward

### UI and brand

- App icon added to main window and launcher.
- Ribbon icons added for language and signature verification.
- Language chooser moved into the File/View area instead of sitting awkwardly at the far left.
- AI settings dialog was restyled for readability.
- Signature validation popup was redesigned to show a compact "valid / invalid" summary.

### Language

- Built-in UI translation layer added.
- Language pack download flow added through VPS-hosted static JSON files.
- App stores the selected language and falls back to built-in strings if a pack is missing.

### Signing

- USB token detection was hardened for Windows and macOS middleware discovery.
- PFX/P12 signing support is available.
- Signature field creation exists.
- Signature appearance was changed so the exported file does not keep the visible selection border.
- Signature info stamp now includes:
  - subject name
  - tax code / CCCD when present
  - CA/provider name
  - certificate serial
  - validity period
  - certificate status
  - signing time
- Verification now checks the currently opened PDF directly instead of forcing another file picker.

### Validation and backend

- VPS license backend was hardened.
- Secrets moved out of `docker-compose.yml`.
- Admin/staff passwords are hashed.
- Invalid token input no longer causes API 500.
- Release upload now computes SHA-256 automatically.

### PDF / editing

- Inline text and image insertion was tightened up.
- Rotation behavior when inserting content was corrected to avoid inverted output.
- Multi-line annotation selection was improved.
- Export paths for Word and Excel were verified with real probe runs.

## 3. Feature matrix

### 3.1 PDF core

Status: implemented in current product baseline.

Included features:
- Open PDF
- Multi-tab document workflow
- Thumbnail sidebar
- Bookmark / TOC sidebar
- Search text and search navigation
- Zoom in / zoom out
- Fit width / fit page
- Page jump
- Rotate page
- Fullscreen / presentation style viewing
- Print
- Recent files

### 3.2 PDF editing

Status: implemented, with some items still needing final polish on Mac parity.

Included features:
- Insert text
- Insert image
- Draw / pen
- Highlight
- Underline
- Strikeout
- Redact
- Add comment / note
- Watermark
- Add page numbers
- Merge PDFs
- Split PDFs
- Delete pages
- Extract pages
- Password protect / remove password
- Compression
- Export pages to images
- Export PDF to text
- Export PDF to Word
- Export PDF to Excel
- Undo for edit flow

### 3.3 Signing

Status: implemented on Windows and structurally ready for macOS adapter parity.

Included features:
- Check USB token presence
- Detect PKCS#11 middleware
- Sign with USB token
- Sign with PFX / P12
- Create signature field
- Signature placement preview
- Handwritten / signature image stamp
- Visible signature info stamp
- Verify signature validity for the opened file

### 3.4 AI / OCR

Status: adapter layer exists; product value layer is still expanding.

Included features:
- Translate PDF content
- Summarize document
- Chat with PDF
- Semantic search
- AI provider selection
- Settings for API keys and local Ollama

Providers currently abstracted:
- Anthropic / Claude
- OpenAI
- Google Gemini
- Ollama local
- 3T AI server hook

### 3.5 License / update / language

Status: implemented.

Included features:
- Activation
- Validate cached token
- Heartbeat
- Deactivate
- Offline grace period
- Device fingerprint
- macOS Keychain storage
- Windows Credential Manager storage
- JSON fallback cache
- Update check
- Update download verification by SHA-256
- Language pack download from VPS

### 3.6 Platform and packaging

Status: implemented enough for Windows and partially prepared for macOS.

Included features:
- Shared Qt compatibility layer
- Shared path adapter
- App data / cache / logs per OS
- Single-instance handling
- App icon and asset pipeline
- Windows packaging and installer flow
- Mac-oriented provider and keychain adapter

## 4. Current code structure that matters to Mac parity

Shared modules:
- `packages/qt_compat`
- `packages/platform`
- `packages/pdf_engine`
- `packages/signing`
- `packages/license_client`
- `packages/ai`

App-facing modules:
- `app/window.py`
- `app/actions/*`
- `app/pdf_viewer.py`
- `app/language_manager.py`
- `app/icon_utils.py`

Mac-specific hooks already present:
- `packages/signing/macos_provider.py`
- `packages/license_client/keychain.py`
- `packages/platform/paths.py`
- `packages/platform/fonts.py`
- `packages/platform/single_instance.py`
- `packages/platform_ui.py`

## 5. What the macOS team must implement or verify to reach parity

### Must verify on real macOS hardware

- App launches cleanly as a `.app` bundle.
- PDF open/render/search/thumbnail workflow works on macOS WebEngine.
- Keyboard shortcuts map correctly to macOS conventions.
- Native menu bar behaves correctly.
- Single-instance logic works on macOS.
- Keychain storage works for license tokens.
- Language pack download and fallback works.
- Printing works from the Mac build.
- USB token middleware detection works with real vendor drivers.
- Signing works end-to-end with real CA middleware.

### Must complete for release quality

- App signing and notarization.
- `.dmg` packaging.
- Update manifest and update download workflow for macOS.
- Brand labels and bundle metadata.
- Mac path conventions for app data, cache, logs, and temp files.

### Must not diverge from Windows contract

- Same open/search/edit/sign/update/license contract.
- Same command names where possible.
- Same update and license API contract.
- Same language pack format.
- Same signing semantics.

## 6. Commercial and copyright risk points

This is the short version.

Safe / preferred for commercial builds:
- PySide6
- pypdfium2
- pikepdf
- cryptography
- python-pkcs11
- reportlab open-source use with correct notice handling

High-risk or legacy items that should not ship in the commercial build unless
the license plan is explicit:
- PyMuPDF legacy path
- GPL wrapper paths for PDF.js if still present in any release bundle
- Unlicensed or borrowed icons, fonts, screenshots, or logos

## 7. Release and git workflow for the Mac team

Recommended flow:

1. Pull the current repo snapshot.
2. Read this document first.
3. Implement the missing macOS parity items in the shared contract first.
4. Keep Mac-specific differences in adapters, not in business logic.
5. Run smoke tests on macOS hardware.
6. Build `.app` and `.dmg`.
7. Run signing/notarization checks.
8. Verify update and license flows against the VPS backend.
9. Only then tag or publish the Mac build.

Suggested branch discipline:
- Shared contract work: `phase1-shared`
- Mac implementation: `phase1-mac`
- Backend/VPS work: `phase1-backend`
- Windows verification: `phase1-win`

## 8. Current readiness statement

- Product direction: aligned with the commercial target.
- Windows parity: substantially ahead and already functioning as a real product shell.
- Mac parity: structurally prepared, but still needs real hardware verification and release packaging.
- Legal/commercial readiness: not final until third-party notices, asset provenance, and build licensing are locked.

## 9. Related docs

- `docs/2026-05-28_PROJECT_REVIEW_AND_HANDOFF.md`
- `docs/PHASE1_MAC_HANDOVER.md`
- `docs/PHASE1_WIN_STATUS.md`
- `docs/PHASE1_3_STREAM_PLAN.md`
- `docs/LICENSE_CLIENT_GUIDE.md`
- `docs/VPS_DEPLOY_GUIDE.md`
- `docs/VPS_LICENSE_TARGET.md`
- `docs/DEPENDENCY_STRATEGY.md`
- `docs/ASSET_SOURCES.md`
- `docs/LICENSE_RISK_REGISTER.md`

