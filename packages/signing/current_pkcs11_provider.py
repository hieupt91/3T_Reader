from __future__ import annotations

from .provider import TokenInfo


class CurrentPkcs11Provider:
    """Adapter around the prototype signing code.

    Phase 0 keeps the existing implementation available but creates a boundary
    so Windows and macOS providers can diverge later without changing UI code.
    """

    def detect_driver(self) -> str | None:
        from core.pkcs11 import detect_pkcs11_lib

        return detect_pkcs11_lib()

    def get_token_info(self, pin: str | None = None) -> TokenInfo | None:
        from core.pkcs11 import get_token_signer_info

        info = get_token_signer_info(pin)
        if not info:
            return None
        return TokenInfo(
            driver=info.get("driver", ""),
            signer_name=info.get("name", ""),
            tax_code=info.get("tax_code", ""),
        )

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
        from core.pkcs11 import sign_pdf

        await sign_pdf(
            input_path,
            output_path,
            pin,
            signer_name=signer_name,
            page_number=page_number,
            box=box,
        )
