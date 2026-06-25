# 3T Reader - Deep Technical Audit (English)

## 1. Purpose

This document is a technical handover and deep audit of the current `3T Reader` codebase.

It is intended for:

- engineers taking over the project,
- reviewers who need a realistic view of what is already implemented,
- maintainers who need to understand the architecture before making changes,
- technical stakeholders who need a code-grounded status report.

This document is based on the current repository state, not on older planning notes alone.

It was assembled from:

- the current desktop application source,
- the current backend/API source,
- test suites,
- packaged documentation inside `docs.zip`,
- vendor/runtime assets and build/deploy scripts.

## 2. What This Project Actually Is

`3T Reader` is not just a PDF viewer. In its current form, it is a desktop PDF platform with multiple subsystems:

- PDF viewing via embedded PDF.js
- annotation
- direct object editing on PDFs
- OCR
- AI chat/summarization/translation/semantic search
- digital signing via USB token and PFX
- batch signing
- export/conversion workflows
- software licensing
- signed update delivery
- supporting backend/API logic for licensing, updates, orders, and admin workflows

There are two major runtime surfaces in this repository:

- the desktop application (`main.py`, `app/`, `packages/`)
- the backend/API side (`main_api.py`, `vps_*`, deployment scripts)

## 3. Important Reality Check: Older Docs vs Current Code

The packaged docs inside `docs.zip` describe an older architecture in some places.

Examples:

- they mention `PyQt5 + QWebEngine`
- they describe a heavier `PyMuPDF` role
- they present some high-level status notes that are no longer fully aligned with the code

The current codebase has moved in important ways:

- the active Qt binding layer is now `PySide6`
- the default PDF engine path is now centered on `pypdfium2 + pikepdf + reportlab`
- the viewer architecture relies heavily on `PDF.js + QWebEngine + local HTTP server + QWebChannel`
- many behaviors are now enforced by tests as architecture contracts

For any technical decision, the current source and current tests should be treated as the source of truth.

## 4. High-Level Repository Structure

### 4.1 Top-Level Files and Folders

- `main.py`: desktop app entrypoint
- `main_api.py`: FastAPI application
- `app/`: desktop UI and viewer orchestration
- `packages/`: shared core/domain packages
- `tests/`: behavioral, regression, security, and architecture tests
- `third_party/pdfjs/`: bundled PDF.js runtime
- `assets/`: application icons, JS hooks, CSS, UI media
- `scripts/`: audit/build/support scripts
- `docs.zip`: packaged technical docs and generated API documentation

There are also many operational root-level scripts for build, deploy, conversion, testing, and release work.

### 4.2 `app/`

This is the desktop application layer.

Most important files:

- `window.py`: main application window and top-level orchestration
- `pdf_viewer.py`: PDF viewer widget built on `QWebEngineView`
- `local_server.py`: local HTTP server for PDF.js and PDF file delivery
- `webchannel.py`: JS/Python bridge registration layer
- `actions/`: feature actions grouped by capability
- `sidebar.py`: thumbnail/document sidebar logic
- `language_manager.py`: language pack and translation management
- `welcome_widget.py`: empty-state landing surface
- `updater.py`, `update_dialog.py`: update UI
- `ai_*_dialog.py`: AI feature dialogs

### 4.3 `packages/`

This folder holds domain and infrastructure logic:

- `packages.pdf_engine`
- `packages.platform`
- `packages.license_client`
- `packages.signing`
- `packages.ocr`
- `packages.ai`
- `packages.document_core`
- `packages.updater`
- `packages.update_client`
- `packages.qt_compat`

## 5. Desktop Runtime Architecture

### 5.1 Entry Point: `main.py`

`main.py` is responsible for:

- handling Qt WebEngine subprocess modes early
- handling special worker modes, including USB signing and export worker entrypoints
- enabling crash logging via `faulthandler`
- enforcing single-instance behavior
- creating the Qt application
- setting theme, icon, and startup UI state
- performing startup license checks
- opening startup PDF paths when provided

It also explicitly avoids running normal app initialization when the current process is a Qt WebEngine helper process.

### 5.2 Single-Instance Handling

Core file: `packages/platform/single_instance.py`

Behavior:

- the app tries to keep one primary desktop instance
- a second instance forwards file-open requests to the first instance
- Windows uses OS-specific locking/messaging strategies
- this behavior is covered by tests

This is not cosmetic. It affects how startup, file opening, and user expectations work in production.

### 5.3 Main Window: `app/window.py`

`PDFReaderApp` is the coordination center of the desktop product.

It handles:

- tabbed document management
- active viewer management
- sidebars
- ribbon/menu/status bar construction
- open/save/save-as/close flows
- per-tab state tracking
- annotation flush points
- temporary file cleanup
- startup and shutdown resource coordination

This file currently carries a large amount of responsibility.

Important note:

- `app/tab_state.py` suggests an attempt to move toward a more structured tab-state model
- but much of the code still relies on `_tabs_data` dictionaries

That means the codebase is partway through a cleanup direction, not fully there yet.

## 6. Viewer Stack

### 6.1 Core Design

The application does not use a native Qt PDF widget as the primary viewer.

Instead, it uses:

- `QWebEngineView`
- a bundled `PDF.js`
- a localhost HTTP server
- a `QWebChannel` bridge between Python and JavaScript

Core files:

- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/webchannel.py`
- `assets/js/pdfjs_ui_hooks.js`

### 6.2 Why the Local HTTP Server Exists

The local server is not accidental. It is a structural part of the application.

It exists to:

- serve PDF files to PDF.js over HTTP
- serve PDF.js assets cleanly to WebEngine
- avoid direct local-file browser restrictions and related access friction
- inject controlled behavior into served JS assets where needed
- expose signature metadata endpoints for interactive viewer behavior

### 6.3 `app/local_server.py`

This is one of the most important modules in the repository.

Responsibilities:

- run a localhost server on `127.0.0.1`
- serve PDF payloads
- serve PDF.js static assets
- serve signature metadata endpoints
- enforce file/path safety rules
- cache processed display bytes and signature metadata

Security-relevant behavior includes:

- only allowing absolute PDF paths
- blocking path traversal patterns
- requiring files to be explicitly registered/whitelisted
- restricting static extensions

Viewer-stability-relevant behavior includes:

- normalizing display PDFs
- flattening/stripping signature widget behavior to reduce PDF.js crashes
- preparing metadata for JS-side signature hit testing

This file is guarded by focused tests, including security tests.

### 6.4 `app/pdf_viewer.py`

`PDFViewerWidget` wraps `QWebEngineView` and adds application-specific viewer logic.

Responsibilities:

- initialize the web engine view
- inject startup scripts and styles
- load the local PDF.js viewer
- register webchannel objects
- track current page and zoom
- expose navigation helpers
- manage live edit overlays
- perform soft and hard reloads after document mutations

It injects:

- `assets/js/polyfill.js`
- `pdfjs_overrides.css`
- `assets/js/pdfjs_ui_hooks.js`
- dynamic theme JS

### 6.5 Soft Reload

The soft reload path is one of the most technically sensitive parts of the viewer.

Goal:

- refresh mutated PDF content without a disruptive full viewer reload

Approach:

- capture existing rendered canvases
- build a temporary freeze overlay
- optionally update overlay object visuals
- reopen the new PDF bytes inside PDF.js
- restore scroll/page position
- remove the freeze overlay after the new render completes

This is a practical UX optimization, but it is fragile enough that viewer regression tests matter a lot here.

### 6.6 JS Hooks: `assets/js/pdfjs_ui_hooks.js`

This file is the active front-end glue for PDF.js inside the desktop app.

It handles:

- suppressing unwanted default PDF.js UI chrome
- loading `qwebchannel.js`
- exposing helper bridge access
- tracking page/view state
- collecting and caching selection payloads
- handling signature-click interaction
- supporting Ctrl+drag panning
- clearing temporary overlays during viewer lifecycle events

This file is not just UI sugar. It is part of the functional runtime contract.

### 6.7 QWebChannel Design

Core file: `app/webchannel.py`

This project uses a shared, stable-bridge model rather than spawning isolated ad hoc channels for each feature.

Stable bridge object names include:

- `pageStateBridge`
- `noteToolsBridge`
- `areaPickBridge`
- `sigPickBridge`
- `sigPreviewBridge`
- `signatureInfoBridge`
- `inlineTextBridge`
- `inlineImageBridge`
- `objectActionBridge`
- `editExistingTextBridge`

The registration layer swaps Python-side targets behind stable JS-facing proxies.

That design reduces front-end churn and is explicitly reinforced by tests.

## 7. Annotation and Editing

### 7.1 Annotation

Core file: `app/actions/annotate.py`

Implemented annotation flows include:

- highlight
- underline
- strikeout
- sticky notes
- interaction with free-draw flows

Important implementation detail:

- annotation writes are queued and debounced through `_AnnotationOpQueue`
- heavy actions flush the queue before proceeding

This is a real design choice, not an incidental optimization.

It improves responsiveness, but it introduces ordering and lifecycle complexity.

### 7.2 PDF Editing

Core file: `app/actions/edit.py`

This is one of the largest and most complex files in the project.

It covers:

- insert text
- insert image
- draw rectangles/overlays
- redact content
- select and manipulate previously inserted objects
- object move/resize/rotate/delete
- edit-existing-text workflows

Architecture pattern:

- maintain a list of edit operations
- preview them live in the viewer
- commit them through backend PDF rewriting
- refresh the viewer via soft or hard reload depending on context

Critical caveat:

- "edit existing text" is not true semantic content-stream text editing
- it is effectively a replace-by-covering workflow, closer to redact-and-reinsert than to native object mutation

Any future engineer must understand that distinction before making assumptions.

### 7.3 Inline Editors

Related files:

- `app/pdf_inline_editor.py`
- `assets/js/inline_text_bridge.js`
- `assets/js/inline_image_bridge.js`

These support live on-page editing overlays for text and image placement, including:

- drag
- resize
- rotate
- confirm/cancel
- Python/JS state synchronization

### 7.4 Save Pipeline

Core file: `app/actions/_pdf_save.py`

This file is important because saving modified PDFs from a WebEngine-backed viewer is not trivial on Windows.

Key behavior:

- load `about:blank` to release the viewer file handle before replacement when needed
- write through staged temp files
- use `os.replace` with retries
- choose soft reload vs hard reload carefully

This is a practical workaround layer for real runtime behavior, not an abstraction accident.

## 8. Sidebars and Shell UI

### 8.1 Sidebar System

Files:

- `app/sidebar.py`
- `app/annotation_sidebar.py`
- `app/signature_sidebar.py`

The thumbnail sidebar includes:

- background thumbnail generation/loading
- lazy loading of visible thumbnails
- document/signature-related cache coordination
- page context actions

### 8.2 Ribbon

Files:

- `app/ribbon_bar.py`
- `app/ribbon_builder.py`

The app includes an Office-style ribbon UI.

Current state:

- the ribbon implementation works
- but `RibbonBuilder` is still largely an adapter
- significant construction logic still lives inside `PDFReaderApp`

That means the UI shell is partially refactored, not fully decomposed.

### 8.3 Menu, Status Bar, Welcome Surface

- `app/menu_builder.py`: adapter around main-window menu construction
- `app/status_bar_builder.py`: status bar setup
- `app/welcome_widget.py`: empty-state UI with recent files and primary actions

These parts are functional, but they also show signs of an incremental refactor path rather than a clean-slate architecture.

## 9. PDF Engine Layer

### 9.1 Structure

Folder: `packages/pdf_engine/`

Main files:

- `base.py`
- `pdfium_engine.py`
- `pymupdf_engine.py`
- `__init__.py`

### 9.2 Default Path: Pdfium + PikePDF + ReportLab

The default engine path is centered on:

- `pypdfium2`
- `pikepdf`
- `reportlab`

This combination is used for:

- page rendering
- page count access
- document merge/split/delete/rotate
- overlays
- watermarking
- output rebuilding

Important behavior includes:

- font path handling for Vietnamese-compatible text rendering
- rotation semantics adjusted to match viewer-side expectations

### 9.3 PyMuPDF Path

`packages/pdf_engine/pymupdf_engine.py` remains present as a legacy/alternate path.

It still matters for:

- compatibility
- specific workflow history
- some alternate implementation strategies

But the codebase is no longer primarily "PyMuPDF-driven" in the way older docs suggest.

## 10. OCR

Files:

- `packages/ocr/engine.py`
- `app/actions/ocr.py`
- `app/ocr_dialog.py`

The OCR system:

- locates Tesseract executables and tessdata
- supports multiple discovery paths
- can OCR pages/documents
- uses `pytesseract`
- integrates with the PDF pipeline through rendering helpers

This is a real subsystem with tests, not a placeholder feature.

## 11. AI Subsystem

### 11.1 Scope

Files under `packages/ai/` and `app/ai_*`

Implemented AI-facing features:

- chat with PDF
- summarize document
- translate content
- semantic search

### 11.2 Provider Layer

Core file: `packages/ai/provider.py`

The provider layer supports multiple AI backends, including:

- OpenAI
- Anthropic
- Groq
- OpenRouter
- Gemini
- HuggingFace
- Ollama

It contains logic to distinguish:

- invalid credentials
- quota exhaustion
- provider fallback behavior

That is operationally meaningful. It is not a thin wrapper.

### 11.3 Chat with PDF

Files:

- `packages/ai/chat_pdf.py`
- `app/ai_chat_dialog.py`

The chat pipeline:

- extracts PDF text with `pdfplumber`
- falls back to `pypdfium2`
- can use OCR-derived fallback content
- wraps PDF content as untrusted user-provided material
- persists chat history in cache

The desktop dialog is non-modal and designed to remain useful while the user is still reading the PDF.

### 11.4 Summarization

Files:

- `packages/ai/summarize.py`
- `app/ai_summarize_dialog.py`

It supports:

- generic document summarization
- document-type-aware prompts
- contract-data extraction mode

Current issue:

- the source file shows encoding/mojibake corruption in some user-facing strings

The feature exists, but the code quality here is not fully clean.

### 11.5 Translation

File: `packages/ai/translate.py`

The translation layer includes:

- language detection heuristics
- non-AI fallback logic
- AI-assisted translation
- offline dictionary support

### 11.6 Semantic Search

Files:

- `packages/ai/semantic_search.py`
- `app/ai_search_dialog.py`

Current implementation:

- chunk text
- generate embeddings through OpenAI
- store cached index as `json + npy`
- perform cosine similarity with `numpy`

Current limitation:

- this path is OpenAI-specific rather than provider-agnostic
- it requires `OPENAI_API_KEY`

So the feature is implemented, but it is less abstracted than the rest of the AI subsystem.

## 12. Digital Signing

### 12.1 Scope

Files:

- `app/actions/sign.py`
- `packages/signing/`
- supporting signature dialogs/UI/sidebar files

Implemented capabilities:

- USB token signing
- PFX signing
- hand signature / stamp placement
- batch signing
- signature information workflows

### 12.2 Viewer-Integrated Placement

The signing UX is tightly integrated with the PDF viewer:

- pick location in the viewer
- preview placement visually
- confirm placement
- perform signing

This is not a detached file-processing-only pipeline.

### 12.3 Windows Provider

Core file: `packages/signing/windows_provider.py`

This is a large, practical integration module for real USB token environments.

It includes:

- environment overrides
- registry scanning
- vendor path scanning
- DLL discovery
- bitness checks
- subprocess probing

This is a compatibility-heavy subsystem. Any future refactor must preserve practical token support, not just improve code aesthetics.

### 12.4 Shared Signing Helpers

Core file: `packages/signing/shared.py`

Responsibilities include:

- certificate detail extraction
- stamp content/style helpers
- atomic replacement of signed outputs
- shared utility behavior used by providers

## 13. Licensing, Trial, and Updates

### 13.1 License Client

Files:

- `packages/license_client/vps_client.py`
- `packages/license_client/token_verifier.py`
- `packages/license_client/fingerprint.py`
- `packages/license_client/credential_manager.py`
- `packages/license_client/keychain.py`
- `packages/license_client/trial.py`
- `packages/license_client/models.py`

Behavior includes:

- activation
- validation
- heartbeat
- deactivation
- offline signed-token verification
- grace-period handling

This is a real client licensing subsystem, not a superficial key check.

### 13.2 Device Fingerprint

File: `packages/license_client/fingerprint.py`

Current strategy:

- on Windows, prefer `MachineGuid`
- otherwise fall back to MAC/hostname/platform data
- hash and shorten the result

### 13.3 Credential Storage

Windows:

- prefer `keyring`
- fall back to DPAPI-protected local file storage

macOS:

- use Keychain via the `security` CLI

### 13.4 Trial

File: `packages/license_client/trial.py`

Current behavior:

- 30-day trial tracking
- stores `first_launch` and `last_seen_at`
- uses platform-appropriate persistence

### 13.5 Update Client

Files:

- `packages/updater/update_client.py`
- `packages/update_client/checker.py`
- `packages/update_client/manifest.py`

Behavior:

- check update endpoint
- receive update manifest
- verify manifest signature via Ed25519
- verify downloaded file checksum
- only then proceed

This is a signed-update trust chain, not a plain "download latest exe" flow.

## 14. Platform Layer

### 14.1 Paths

`packages/platform/paths.py`

Provides:

- app data paths
- cache paths
- log paths

### 14.2 Fonts

`packages/platform/fonts.py`

Finds platform-appropriate font files, including Vietnamese-friendly candidates.

This matters because PDF text insertion/rendering quality depends on actual available fonts.

### 14.3 Secure Config

`packages/platform/secure_config.py`

Encrypts sensitive config values using a machine-derived Fernet key.

This includes AI/API-related secrets.

### 14.4 Recent Files

`packages/platform/recent.py`

Used by the welcome UI and recent-file workflows.

## 15. Conversion and Export

### 15.1 Opening Non-PDF Documents

File: `app/actions/document_converter.py`

Supports flows such as:

- image to PDF
- Office document to PDF
- XML to PDF or related handling paths
- runtime download of supporting modules when needed

### 15.2 Export

Files:

- `app/actions/export.py`
- `packages/document_core/export_runner.py`
- `packages/document_core/converter.py`

Supported export targets include:

- DOCX
- XLSX
- image
- text

The export system uses subprocess isolation where appropriate to reduce crash risk.

## 16. Backend/API Side

### 16.1 `main_api.py`

This is a substantial FastAPI application.

It includes endpoints and workflows for:

- support/legal pages
- admin/staff auth
- orders
- license operations
- update-manifest workflows
- release/admin/config/device-related surfaces

Important note:

- it contains multiple concerns in one place
- it is functional, but not strongly decomposed

### 16.2 `vps_*` Files

Examples:

- `vps_license_service.py`
- `vps_order_service.py`
- `vps_models.py`
- `vps_schemas.py`

These confirm that the repository also carries backend/business logic for the Reader ecosystem, not just desktop code.

## 17. Internationalization

Core file: `app/language_manager.py`

Capabilities:

- selected language storage through `QSettings`
- built-in translation maps
- downloadable language packs
- validation and local storage of pack payloads

Current issue:

- there are visible mojibake/encoding problems in this file as well

So the i18n system exists and functions, but some source hygiene problems remain.

## 18. Dependencies

### 18.1 Main Dependencies from `pyproject.toml`

Key runtime dependencies include:

- `PySide6`
- `pyqtdarktheme`
- `pypdfium2`
- `pikepdf`
- `reportlab`
- `pyHanko`
- `python-pkcs11`
- `cryptography`
- `Pillow`
- `requests`
- `pytesseract`
- `pdf2docx`
- `pdfplumber`
- `openpyxl`
- `numpy`

Optional dependencies include:

- `openai`
- `anthropic`
- `PyMuPDF`
- `PyKCS11`
- `pyinstaller`
- `sphinx`

### 18.2 `requirements.txt`

This file also includes:

- `pyttsx3`
- Windows-specific `pywin32`

Practical interpretation:

- `pyproject.toml` is closer to the modern dependency definition
- `requirements.txt` looks more like an operational snapshot

## 19. Vendor, Assets, and Generated Material

### 19.1 `third_party/pdfjs`

This is a significant bundled vendor runtime.

Observed contents include:

- many `.bcmap` files
- many `.ftl` localization files
- `.mjs`
- `.wasm`
- fonts
- static HTML/CSS/JS assets

This folder is runtime-critical but should be treated carefully as vendor material.

The project prefers patching around it through:

- local-server behavior
- CSS overrides
- injected JS hooks

rather than deeply rewriting vendor internals.

### 19.2 `assets/`

Contains:

- SVG icons
- PNG assets
- JS hooks and bridge helpers
- CSS overrides
- application icons

### 19.3 `docs.zip`

This file is meaningful.

It contains:

- historical project markdown docs
- Sphinx source docs
- generated API docs
- generated module HTML pages

It should be treated as auxiliary technical documentation, not as runtime source.

## 20. Tests and Architecture Contracts

This is one of the most important parts of the codebase.

The tests do more than validate output. Many of them lock in architecture decisions.

Important test files include:

- `tests/test_viewer_annotation_regressions.py`
- `tests/test_stability_contracts.py`
- `tests/test_pdf_engine.py`
- `tests/test_pdf_pipeline.py`
- `tests/test_ai_provider.py`
- `tests/test_license_client.py`
- `tests/test_update_client.py`
- `tests/test_local_server.py`
- `tests/test_local_server_security.py`
- `tests/test_single_instance.py`
- `tests/test_ocr_engine.py`
- `tests/test_ai_chat_pdf.py`
- `tests/test_language_manager.py`

Examples of what is implicitly or explicitly enforced:

- stable QWebChannel bridging patterns
- viewer JS integration assumptions
- local server security requirements
- update verification behavior
- licensing behavior
- PDF pipeline expectations

Future maintainers should treat these tests as design constraints, not just regression checks.

## 21. Build, Deploy, and Operational Scripts

### 21.1 `scripts/`

Includes:

- Windows signing helper script
- source export script
- OCR bundle audit script
- hardcoded-string audit script
- cache repair script

### 21.2 Root-Level Operational Files

Examples:

- `3T_Reader.spec`
- `installer_script.iss`
- `build_secure.py`
- `deploy_final.py`
- `direct_deploy.py`
- `direct_deploy2.py`
- `sftp_deploy.py`
- `update_vps_config.py`

This repository contains production-adjacent operational logic, not only application source.

## 22. Binary Artifacts, Test Files, and Generated Outputs

The repo contains many:

- sample/test PDFs
- generated PDFs
- images
- logs
- archives
- temporary or experiment-oriented utility files

These are not all equal in maintenance value.

Some are:

- test fixtures
- reproduction artifacts
- output samples

They matter for understanding project history and behavior, but they are not the same thing as core source modules.

## 23. Current Delivery Status

### 23.1 Clearly Implemented and Real

The following are clearly implemented in the current code:

- PDF.js-based viewer in desktop WebEngine
- localhost file/asset delivery layer
- multi-tab document workflow
- thumbnail and annotation sidebars
- annotation write queue
- PDF object editing via overlay + rewrite pipeline
- save pipeline with file-lock handling
- OCR
- AI chat/summarize/translate/semantic search
- licensing with offline token verification
- signed update verification
- USB token and PFX signing
- batch signing
- export and conversion workflows
- language pack support

### 23.2 Working but Architecturally Heavy

The following work, but carry structural weight:

- `app/window.py`
- `app/actions/edit.py`
- `app/actions/sign.py`
- `main_api.py`

These are important but maintenance-expensive modules.

### 23.3 Notable Technical Debt

- encoding/mojibake corruption in some source strings
- semantic search is OpenAI-specific rather than fully provider-abstracted
- partial refactor state in UI shell organization
- mixed operational scripts and production code in one repo
- vendor/generated artifacts living close to active source

## 24. Key Technical Truths Future Engineers Must Remember

1. The viewer is a browser-based PDF.js stack inside a desktop shell.

2. The local HTTP server is part of the architecture, not a temporary workaround to remove casually.

3. Viewer state, JS hooks, and webchannel behavior are deeply interconnected.

4. Save behavior on Windows is constrained by WebEngine file locking.

5. "Edit existing text" is not true native PDF text-object editing.

6. Licensing and updates both rely on trust-chain verification behavior that should not be simplified away.

7. Windows token signing code is practical compatibility code and must be handled carefully.

## 25. Suggested Reading Order for New Engineers

Best entry path:

1. Read this file.
2. Read:
   - `main.py`
   - `app/window.py`
   - `app/pdf_viewer.py`
   - `app/local_server.py`
   - `app/webchannel.py`
3. Read feature-heavy actions:
   - `app/actions/edit.py`
   - `app/actions/annotate.py`
   - `app/actions/sign.py`
   - `app/actions/_pdf_save.py`
4. Read core packages:
   - `packages/pdf_engine/pdfium_engine.py`
   - `packages/license_client/vps_client.py`
   - `packages/updater/update_client.py`
   - `packages/signing/windows_provider.py`
5. Read tests:
   - `tests/test_stability_contracts.py`
   - `tests/test_viewer_annotation_regressions.py`
   - `tests/test_local_server_security.py`

## 26. Overall Assessment

This is a real product codebase with real production pressure visible in its design.

It solves practical problems:

- embedding PDF.js in a desktop application
- handling Windows file locking around PDF mutation
- supporting OCR and AI features
- integrating digital signatures with real-world USB token environments
- maintaining signed licensing and update flows

It is not a minimal or especially clean codebase.

It is a living, practical system with:

- strong functional scope
- meaningful workarounds
- partial refactors
- some clear technical debt
- significant runtime/vendor complexity

The correct maintenance mindset is:

- respect the existing contracts
- understand why the workarounds exist
- refactor incrementally
- avoid broad "cleanup" changes without behavioral proof

## 27. Important Files at a Glance

Desktop runtime:

- `main.py`
- `app/window.py`
- `app/pdf_viewer.py`
- `app/local_server.py`
- `app/webchannel.py`

Core actions:

- `app/actions/edit.py`
- `app/actions/annotate.py`
- `app/actions/sign.py`
- `app/actions/export.py`
- `app/actions/document_converter.py`
- `app/actions/_pdf_save.py`

Core packages:

- `packages/pdf_engine/pdfium_engine.py`
- `packages/pdf_engine/pymupdf_engine.py`
- `packages/license_client/vps_client.py`
- `packages/signing/windows_provider.py`
- `packages/updater/update_client.py`
- `packages/ocr/engine.py`
- `packages/ai/provider.py`
- `packages/ai/chat_pdf.py`

Tests/contracts:

- `tests/test_stability_contracts.py`
- `tests/test_viewer_annotation_regressions.py`
- `tests/test_local_server.py`
- `tests/test_local_server_security.py`
- `tests/test_pdf_engine.py`

Ops/build:

- `main_api.py`
- `3T_Reader.spec`
- `installer_script.iss`
- `build_secure.py`
- `deploy_final.py`
- `direct_deploy2.py`
- `scripts/*`

