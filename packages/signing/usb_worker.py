from __future__ import annotations

import asyncio
import json
import sys
import traceback

from packages.signing import get_signing_provider
from packages.signing.provider import TokenInfo


def _token_info_from_payload(payload: dict) -> TokenInfo:
    return TokenInfo(
        driver=str(payload.get("driver") or ""),
        signer_name=str(payload.get("signer_name") or ""),
        tax_code=str(payload.get("tax_code") or ""),
        driver_path=str(payload.get("driver_path") or ""),
        token_index=int(payload.get("token_index") or 0),
        token_label=str(payload.get("token_label") or ""),
        serial=str(payload.get("serial") or ""),
        manufacturer=str(payload.get("manufacturer") or ""),
        model=str(payload.get("model") or ""),
        issuer_name=str(payload.get("issuer_name") or ""),
        cert_serial=str(payload.get("cert_serial") or ""),
    )


def run_job(payload: dict) -> dict[str, object]:
    provider = get_signing_provider()
    token_payload = payload.get("token") or {}
    token_info = _token_info_from_payload(token_payload) if token_payload else None
    if token_info is not None:
        provider.select_token(token_info)

    async def _do_sign():
        await provider.sign_pdf(
            str(payload["input_path"]),
            str(payload["output_path"]),
            str(payload["pin"]),
            signer_name=str(payload.get("signer_name") or "Khong ro"),
            page_number=int(payload.get("page_number") or 1),
            box=tuple(payload.get("box") or (50, 50, 300, 100)),
            field_name=str(payload.get("field_name") or "") or None,
            reason=str(payload.get("reason") or "") or None,
            location=str(payload.get("location") or "") or None,
            contact_info=str(payload.get("contact_info") or "") or None,
        )

    asyncio.run(_do_sign())
    return {"ok": True}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(json.dumps({"ok": False, "error_type": "UsageError", "error_message": "Missing payload path"}, ensure_ascii=True))
        return 2

    payload_path = args[0]
    try:
        with open(payload_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        result = run_job(payload)
    except Exception as exc:
        result = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
        }

    print(json.dumps(result, ensure_ascii=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
