from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TokenInfo:
    driver: str
    signer_name: str = ""
    tax_code: str = ""
    driver_path: str = ""
    token_index: int = 0
    token_label: str = ""
    serial: str = ""
    manufacturer: str = ""
    model: str = ""
    issuer_name: str = ""
    cert_serial: str = ""


class SigningProvider(Protocol):
    def get_last_error(self) -> str:
        ...

    def detect_driver(self) -> str | None:
        ...

    def list_tokens(self, pin: str | None = None) -> list[TokenInfo]:
        ...

    def select_token(self, token_info: TokenInfo | None) -> None:
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
        field_name: str | None = None,
        reason: str | None = None,
        location: str | None = None,
        contact_info: str | None = None,
        tsa_url: str | None = None,
        enable_ltv: bool = False,
    ) -> None:
        ...

    async def sign_pdf_batch(
        self,
        jobs: list[dict],
        pin: str,
        *,
        tsa_url: str | None = None,
        enable_ltv: bool = False,
    ) -> None:
        ...

