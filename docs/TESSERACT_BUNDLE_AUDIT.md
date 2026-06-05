# Tesseract Bundle Audit

Generated from `scripts/audit_tesseract_bundle.py` on 2026-06-05.

## Summary

- Bundle path: `third_party/tesseract/`
- Files scanned: 87
- Total size: 234,304,657 bytes
- Conservative keep set: 15 files, 112,931,904 bytes
- Candidate remove set: 32 files, 62,077,696 bytes
- Needs runtime DLL load check: 40 files, 59,295,057 bytes

## Decision

Do not delete DLLs only from filename classification. The OCR runtime must be checked with a real OCR flow and a DLL-load trace before removing files marked `needs-runtime-check`.

Safe next packaging step:

1. Remove documentation/training tools in `candidate-remove` in a staging copy only.
2. Run OCR on at least one English and one Vietnamese PDF/image sample.
3. Verify loaded DLLs with Process Monitor or an equivalent DLL-load trace.
4. Update `3T_Reader.spec` only after the staging copy passes OCR smoke tests.

## Candidate Remove Files

These are training utilities, manpage HTML files, or uninstall helper files that are not expected to be needed by normal OCR:

- `ambiguous_words.1.html`
- `ambiguous_words.exe`
- `classifier_tester.1.html`
- `classifier_tester.exe`
- `cntraining.1.html`
- `cntraining.exe`
- `combine_lang_model.1.html`
- `combine_lang_model.exe`
- `combine_tessdata.1.html`
- `combine_tessdata.exe`
- `dawg2wordlist.1.html`
- `dawg2wordlist.exe`
- `lstmeval.1.html`
- `lstmeval.exe`
- `lstmtraining.1.html`
- `lstmtraining.exe`
- `merge_unicharsets.1.html`
- `merge_unicharsets.exe`
- `mftraining.1.html`
- `mftraining.exe`
- `set_unicharset_properties.1.html`
- `set_unicharset_properties.exe`
- `shapeclustering.1.html`
- `shapeclustering.exe`
- `tesseract-uninstall.exe`
- `tesseract.1.html`
- `text2image.1.html`
- `text2image.exe`
- `unicharambigs.5.html`
- `unicharset.5.html`
- `unicharset_extractor.1.html`
- `wordlist2dawg.1.html`

## Keep Files

The audit script marks the core executable, core OCR libraries, image codecs, compression libraries, and C++ runtime dependencies as keep:

- `tesseract.exe`
- `libtesseract-5.dll`
- `libleptonica-6.dll`
- `libgcc_s_seh-1.dll`
- `libjpeg-8.dll`
- `liblz4.dll`
- `liblzma-5.dll`
- `libopenjp2-7.dll`
- `libpng16-16.dll`
- `libstdc++-6.dll`
- `libtiff-6.dll`
- `libwebp-7.dll`
- `libwebpmux-3.dll`
- `libwinpthread-1.dll`
- `libzstd.dll`

## Verification

Command run:

```powershell
.\.venv313\Scripts\python.exe scripts\audit_tesseract_bundle.py
```

Result: audit completed successfully. No files were deleted.
