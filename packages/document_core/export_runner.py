"""Standalone export runner for PDF -> Word / Excel."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="export_runner")
    parser.add_argument("task", choices=("docx", "xlsx"))
    parser.add_argument("pdf_path")
    parser.add_argument("output_path")
    args = parser.parse_args(argv)

    try:
        from packages.document_core.converter import (
            convert_pdf_to_docx,
            convert_pdf_to_xlsx,
        )

        def _progress(msg: str) -> None:
            print(msg, flush=True)

        if args.task == "docx":
            convert_pdf_to_docx(args.pdf_path, args.output_path, progress_cb=_progress)
        else:
            convert_pdf_to_xlsx(args.pdf_path, args.output_path, progress_cb=_progress)
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
