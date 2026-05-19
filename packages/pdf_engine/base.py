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
