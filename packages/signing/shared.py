"""Shared signing utilities — no OS-specific paths or assumptions."""
from __future__ import annotations

import os
import unicodedata


def _safe_get_pkcs11_attr(obj, attr):
    try:
        return obj[attr]
    except Exception:
        return None


def _extract_tax_code_from_text(text: str) -> str | None:
    import re

    match = re.search(r"\b(\d{10}(?:-\d{3})?)\b", text or "")
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{13,14})\b", text or "")
    return match.group(1) if match else None


def strip_accents(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    return only_ascii.replace("đ", "d").replace("Đ", "D").strip()


def extract_signer_identity_from_der(cert_der: bytes | None) -> dict[str, str] | None:
    if not cert_der:
        return None
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        cert = x509.load_der_x509_certificate(cert_der)
        subject = cert.subject

        cn = subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn:
            name = cn[0].value.strip()
        else:
            org = subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
            name = org[0].value.strip() if org else ""

        safe_name = strip_accents(name)
        identity: dict[str, str] = {
            "name": safe_name or "Khong ro",
            "subject": subject.rfc4514_string(),
            "serial_hex": format(cert.serial_number, "X"),
        }
        tax_code = _extract_tax_code_from_text(f"{identity['name']} {identity['subject']}")
        if tax_code:
            identity["tax_code"] = tax_code
        return identity
    except Exception:
        return None


def build_vietnamese_stamp_style(
    signer_display_name: str,
    *,
    tax_code: str | None = None,
    signed_at: str | None = None,
):
    import textwrap
    from pyhanko.pdf_utils.layout import AxisAlignment, Margins, SimpleBoxLayoutRule
    from pyhanko.pdf_utils.text import TextBoxStyle
    from pyhanko.stamp import TextStampStyle

    safe_name = strip_accents((signer_display_name or "").strip()) or "Khong ro"
    display_tax = tax_code or _extract_tax_code_from_text(safe_name)

    wrapped = textwrap.wrap(safe_name, width=28) or ["Khong ro"]
    signer_lines = "\n".join(
        f"Ky boi: {line}" if idx == 0 else f"       {line}"
        for idx, line in enumerate(wrapped[:2])
    )
    stamp_text = (
        "DA KY SO\n"
        + signer_lines + "\n"
        + (f"MST: {display_tax}" if display_tax else "MST: Khong ro") + "\n"
        + (f"Ky luc: {signed_at}" if signed_at else "Ky luc: Khong ro")
    )

    layout_rule = SimpleBoxLayoutRule(
        x_align=AxisAlignment.ALIGN_MIN,
        y_align=AxisAlignment.ALIGN_MIN,
        margins=Margins(left=4, right=4, top=4, bottom=4),
    )
    return TextStampStyle(
        stamp_text=stamp_text,
        background_opacity=0.0,
        border_width=0,
        text_box_style=TextBoxStyle(
            font_size=9,
            leading=11,
            box_layout_rule=layout_rule,
        ),
    )


async def sign_pdf_with_session(
    session,
    lib_path: str,
    input_path: str,
    output_path: str,
    *,
    signer_name: str = "Khong ro",
    page_number: int = 1,
    box: tuple[float, float, float, float] | None = None,
) -> None:
    """Core pyHanko signing — OS-agnostic. Caller is responsible for opening/closing session."""
    import shutil
    import tempfile
    from datetime import datetime
    from pkcs11.constants import Attribute, ObjectClass
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers
    from pyhanko.sign.pkcs11 import PKCS11Signer
    from pyhanko.sign.signers import PdfSignatureMetadata

    if box is None:
        box = (50, 50, 300, 100)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()

    try:
        certs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
        if not certs:
            raise RuntimeError("Không tìm thấy certificate trên USB Token!")

        signing_cert = certs[-1]
        cert_id = signing_cert[Attribute.ID]
        cert_identity = extract_signer_identity_from_der(
            _safe_get_pkcs11_attr(signing_cert, Attribute.VALUE)
        )
        cert_name = cert_identity.get("name") if cert_identity else ""
        cert_tax = cert_identity.get("tax_code") if cert_identity else None

        signer_obj = PKCS11Signer(session, cert_id=cert_id)
        display_name = (signer_name or "").strip() or cert_name or "Khong ro"
        signed_at_vn = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        stamp_style = build_vietnamese_stamp_style(
            display_name,
            tax_code=cert_tax,
            signed_at=signed_at_vn,
        )

        with open(input_path, "rb") as f:
            writer = IncrementalPdfFileWriter(f)
            fields.append_signature_field(
                writer,
                sig_field_spec=fields.SigFieldSpec(
                    sig_field_name="Signature1",
                    box=box,
                    on_page=max(0, page_number - 1),
                ),
            )
            meta = PdfSignatureMetadata(field_name="Signature1", name=display_name)
            pdf_signer = signers.PdfSigner(
                signature_meta=meta,
                signer=signer_obj,
                stamp_style=stamp_style,
            )
            with open(tmp_path, "wb") as out:
                await pdf_signer.async_sign_pdf(writer, output=out)

        shutil.copy2(tmp_path, output_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
