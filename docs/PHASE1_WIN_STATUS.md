# Phase 1 Windows Status

This document summarizes the current state of the `phase1-win` stream.

## Done

- Windows PKCS#11 provider now supports configurable vendor DLL paths via `THREET_READER_WINDOWS_PKCS11_PATHS`.
- Windows PKCS#11 search now includes common vendor locations under `System32`, `SysWOW64`, `Program Files`, `Program Files (x86)`, and `LOCALAPPDATA`.
- Windows single-instance handling uses a `Local\...` mutex name and checks `ERROR_ALREADY_EXISTS` directly.
- Windows installer metadata is aligned with the current brand and uses `build\installer` as the output directory.
- Installer URLs now point to `https://3tcomputer.com`.
- PyInstaller spec collects package-provided binaries and data for `pypdfium2` and `pikepdf`.
- The repo README now documents the Windows phase assumptions and token override environment variable.
- Platform smoke tests cover Windows mutex naming and Windows PKCS#11 search behavior.
- Windows PDF rendering now works through a local HTTP PDF.js server with a JavaScript MIME fix for `.mjs`.
- The Windows workspace passes the platform smoke suite: `26 passed, 1 skipped`.
- A full Windows packaging pass now succeeds on this machine: `PyInstaller` builds `dist\3T_Reader` and Inno Setup compiles `build\installer\Setup_3T_Reader_v1.0.2.exe`.
- The packaged Windows app launches successfully from the built `dist\3T_Reader\3T_Reader.exe`.

## Not Done

- Token hardware integration has not been tested with a real USB token and vendor middleware.

## Current Blocker

- The remaining work is no longer PDF.js rendering.
- The next practical blocker is real token hardware validation.

## Next Steps

- Test real USB token detection and signing on a Windows machine with vendor middleware installed.
- If you want a fuller release readiness pass, run one end-to-end install/uninstall cycle from `build\installer\Setup_3T_Reader_v1.0.2.exe`.

## Release Readiness

- This stream is in a good state to commit and push to the `phase1-win` branch.
- Do not mark it as `phase1-win-ready` yet.
- The `phase1-win-ready` milestone should wait until real token signing validation is complete.

## Files Touched In This Stream

- `app/local_server.py`
- `app/pdf_viewer.py`
- `packages/platform/single_instance.py`
- `packages/signing/windows_provider.py`
- `packages/qt_compat/__init__.py`
- `packages/qt_compat/QtWebEngineCore.py`
- `installer_script.iss`
- `3T_Reader.spec`
- `README.md`
- `tests/test_smoke_platform.py`
