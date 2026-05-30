# 3T Reader Baseline Status Handoff

Date: 2026-05-30
Branch: `release-1.0.7-baseline-ocr-ai`

## Current baseline

This branch is the cleaned baseline rebuilt from `1.0.7`, then selectively ported with OCR, AI fallback, language fixes, watermark removal, and signature flow fixes. The goal is to stabilize the product before the next installer/export round.

## Completed and usable

- OCR runtime now works with bundled Tesseract when `OCR_TESSERACT_CMD` / bundled `_internal/Tesseract-OCR` is available.
- OCR engine path handling was fixed; `TESSDATA_PREFIX` is now used instead of the broken quoted `--tessdata-dir`.
- Language switching no longer force-downloads a server pack on every change.
- Built-in language coverage exists for `vi`, `en`, `fr`, `zh`, `ko`, `th`.
- Corrupted/mojibake language packs in AppData are ignored instead of overriding built-in translations.
- Watermark removal works for the current app-generated overlay style.
- Watermark removal was verified for both:
  - remove current page only
  - remove one page first, then remove all remaining pages
- Handwritten signature / stamp now writes back into the current file instead of creating a fresh temp PDF every time.
- Signature field creation supports multiple fields in one session and avoids duplicate field-name crashes by auto-suffixing names.
- Chat PDF now shows the user message immediately before the AI response returns.

## Partially stabilized / still under observation

- OCR current page is modal and acceptable.
- OCR full document was changed to non-modal to avoid repeated modal UI flicker / stacked dialog behavior. This needs another manual test pass.
- Signature field visual behavior is back on the previous known-good display path after reverting the last risky UI tweak.
- Bundled Tesseract exists in `dist\3T_Reader\_internal\Tesseract-OCR`, but the existing `dist` executable is old and does not include the newest source fixes until rebuilt.

## Known unfinished items

- Signature UX still needs a cleaner visual treatment:
  - less intrusive preview/field display
  - parity between blank field placement and signed field visualization
- USB token / PFX signing still uses export-to-new-file legal signing flow; that is intentional, but UX can still be improved.
- AI features still require the user to supply an API key or local Ollama setup.
- Large-file print performance and crash hardening are not fully finished.
- Annotation precision, object editing smoothness, and several UI consistency issues remain open.

## Most important next tasks

1. Re-test `OCR toàn bộ` after the non-modal change.
2. Re-test signature field placement flow:
   - place multiple fields
   - stop after the last field
   - verify save to current file
   - verify no duplicate-name crash
3. Decide final visual behavior for blank signature fields vs signed fields in PDF.js display.
4. Rebuild `dist` and installer only after the above manual tests pass.

## Notes for tonight

- Do not trust the current `dist\3T_Reader\3T_Reader.exe` as a full validation artifact; it predates the latest source fixes.
- For source testing without system Tesseract installed, launch the app with:
  - `OCR_TESSERACT_CMD=dist\3T_Reader\_internal\Tesseract-OCR\tesseract.exe`
  - `TESSDATA_PREFIX=dist\3T_Reader\_internal\Tesseract-OCR\tessdata`
- If the next manual test shows OCR full-document is still flickering, move the progress UI to a persistent dock/tool window or use a worker + status panel instead of a dialog.
