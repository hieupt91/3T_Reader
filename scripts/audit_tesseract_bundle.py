"""Report bundled Tesseract files and conservative keep/remove candidates."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESSERACT_DIR = ROOT / "third_party" / "tesseract"
KEEP_NAMES = {
    "tesseract.exe",
    "libtesseract-5.dll",
    "libleptonica-6.dll",
}
KEEP_PREFIXES = (
    "libpng",
    "libjpeg",
    "libtiff",
    "libwebp",
    "libopenjp2",
    "libz",
    "liblz",
    "libstdc++",
    "libgcc",
    "libwinpthread",
)
DROP_SUFFIXES = (".html", ".1.html", ".5.html")
TRAINING_EXES = {
    "ambiguous_words.exe",
    "classifier_tester.exe",
    "cntraining.exe",
    "combine_lang_model.exe",
    "combine_tessdata.exe",
    "dawg2wordlist.exe",
    "lstmeval.exe",
    "lstmtraining.exe",
    "merge_unicharsets.exe",
    "mftraining.exe",
    "set_unicharset_properties.exe",
    "shapeclustering.exe",
    "text2image.exe",
    "unicharambigs.exe",
}


def classify(path: Path) -> str:
    lower = path.name.lower()
    if lower in KEEP_NAMES or lower.startswith(KEEP_PREFIXES):
        return "keep"
    if lower.endswith(DROP_SUFFIXES) or lower in TRAINING_EXES or lower.endswith("-uninstall.exe"):
        return "candidate-remove"
    return "needs-runtime-check"


def main() -> int:
    if not TESSERACT_DIR.exists():
        print(f"Missing: {TESSERACT_DIR}")
        return 1
    rows = []
    for path in sorted(TESSERACT_DIR.iterdir(), key=lambda p: p.name.lower()):
        if path.is_file():
            rows.append((classify(path), path.name, path.stat().st_size))
    total = sum(size for _kind, _name, size in rows)
    print(f"Tesseract files: {len(rows)}")
    print(f"Total bytes: {total}")
    for kind, name, size in rows:
        print(f"{kind:20} {size:12} {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
