from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RenderedPage:
    width: int
    height: int
    stride: int
    samples: bytes


class PdfDocument(Protocol):
    @property
    def page_count(self) -> int:
        ...

    @property
    def needs_password(self) -> bool:
        ...

    def authenticate(self, password: str) -> bool:
        ...

    def save_without_encryption(self, output_path: str) -> None:
        ...

    def render_page_rgb(self, page_number: int, scale: float = 1.0) -> RenderedPage:
        ...

    def close(self) -> None:
        ...


class PdfEngine(Protocol):
    def open(self, path: str) -> PdfDocument:
        ...

    def page_count(self, path: str) -> int:
        ...

    def create_blank_pdf(self, output_path: str, width_pt: float, height_pt: float) -> None:
        ...

    def rebuild_pdf_with_ops(self, base_path: str, output_path: str, ops: list[dict]) -> None:
        ...

    def watermark_pdf(self, input_path: str, output_path: str, text: str,
                      color: tuple = (0.6, 0.6, 0.6), angle: float = 45.0,
                      apply_to_pages: list[int] | None = None) -> None:
        ...

    def delete_pages(self, input_path: str, output_path: str, page_numbers: list[int]) -> None:
        ...

    def rotate_pages(self, input_path: str, output_path: str, page_rotations: dict) -> None:
        ...

    def merge_pdfs(self, input_paths: list[str], output_path: str) -> None:
        ...

    def split_pdf(self, input_path: str, output_dir: str,
                  page_ranges: list[tuple]) -> list[str]:
        ...
