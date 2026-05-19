from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TokenInfo:
    driver: str
    signer_name: str = ""
    tax_code: str = ""


class SigningProvider(Protocol):
    def get_last_error(self) -> str:
        ...

    def detect_driver(self) -> str | None:
        ...

    def get_token_info(self, pin: str | None = None) -> TokenInfo | None:
        ...

    async def sign_pdf(
        self,
        input_path: str,
        output_path: str,
        pin: str,
        *,
        signer_name: str,
        page_number: int,
        box: tuple[float, float, float, float],
    ) -> None:
        ...
