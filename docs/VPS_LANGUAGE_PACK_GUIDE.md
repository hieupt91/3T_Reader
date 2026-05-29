# VPS Language Pack Guide

This guide matches the live backend layout on the VPS.

Status: verified live on 2026-05-29. The files below are already published and reachable over HTTPS:

- `https://reader.3tcomputer.com/downloads/language/vi.json`
- `https://reader.3tcomputer.com/downloads/language/en.json`

## Current public URLs

The desktop app loads language packs from:

```text
https://reader.3tcomputer.com/downloads/language/{code}.json
```

The same backend is also reachable at:

```text
https://license.3tcomputer.com/downloads/language/{code}.json
```

Both hostnames are routed by the Cloudflare Tunnel to the same backend container on port `8000`.

## Live storage path

On the VPS, the backend repo lives at:

```text
/home/hieupt/projects/3T_Reader/phase1-backend
```

Language packs are stored under:

```text
/home/hieupt/projects/3T_Reader/phase1-backend/downloads/language/
```

Current live files:

- `vi.json`
- `en.json`

Inside the container, the same folder is mounted as:

```text
/downloads/language/
```

Do not use `/data/downloads/language` for this deployment. That was part of an older placeholder layout and is not present on the live host.

## Recommended file names

- `vi.json`
- `en.json`

If new languages are added later, keep the file name equal to the language code:

- `ja.json`
- `zh.json`
- `fr.json`

## Expected JSON shape

```json
{
  "code": "en",
  "version": "2026-05-28.1",
  "updated_at": "2026-05-28T00:00:00+07:00",
  "strings": {
    "menu.file": "File",
    "menu.navigate": "Navigate",
    "menu.view": "View",
    "menu.tools": "Tools",
    "menu.page": "Page",
    "menu.security": "Security",
    "menu.sign": "Sign",
    "menu.ocr": "OCR",
    "menu.ai": "AI",
    "menu.license": "License",
    "menu.language": "Language",
    "menu.help": "Help",
    "lang.vietnamese": "Vietnamese",
    "lang.english": "English",
    "lang.download": "Download language pack...",
    "tab.file_view": "File & View",
    "tab.annotate": "Annotate",
    "tab.page": "Page",
    "tab.security_export": "Security & Export",
    "tab.ocr_ai": "OCR & AI",
    "tab.sign": "Sign",
    "status.no_file": "No file opened",
    "status.page": "Page: -"
  }
}
```

## Deploy steps

1. Create the directory if needed:

```bash
mkdir -p /home/hieupt/projects/3T_Reader/phase1-backend/downloads/language
```

2. Upload `vi.json` and/or `en.json` into that folder.
3. Verify over HTTPS:

```bash
curl -I https://reader.3tcomputer.com/downloads/language/en.json
curl https://reader.3tcomputer.com/downloads/language/en.json
```

## Notes

- The app falls back to built-in translations if a language pack is missing.
- No backend API change is needed for language packs; they are plain static files in the `downloads` folder.
- If you update the backend compose file, keep `THREET_DOWNLOADS_DIR=/downloads` aligned with the static file path.
