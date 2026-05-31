"""Shared signing utilities - no OS-specific paths or assumptions."""
from __future__ import annotations

import os
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone


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


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_vn_datetime(dt: datetime | None) -> str:
    if dt is None:
        return "Khong ro"
    return dt.astimezone().strftime("%d/%m/%Y %H:%M:%S")


def _extract_display_name(name_obj) -> str:
    from cryptography.x509.oid import NameOID

    if name_obj is None:
        return ""
    for oid in (NameOID.COMMON_NAME, NameOID.ORGANIZATION_NAME, NameOID.ORGANIZATIONAL_UNIT_NAME):
        try:
            attrs = name_obj.get_attributes_for_oid(oid)
        except Exception:
            attrs = []
        if attrs:
            value = str(attrs[0].value or "").strip()
            if value:
                return value
    try:
        human = name_obj.human_friendly
        if human:
            return str(human).strip()
    except Exception:
        pass
    try:
        return name_obj.rfc4514_string().strip()
    except Exception:
        return ""


def _normalize_provider_name(issuer_name: str) -> str:
    haystack = strip_accents(issuer_name).upper()
    for token, label in (
        ("VIETTEL", "Viettel-CA"),
        ("VNPT", "VNPT-CA"),
        ("FPT", "FPT-CA"),
        ("MISA", "MISA-CA"),
        ("BKAV", "BKAV-CA"),
        ("EFY", "EFY-CA"),
        ("NEWTEL", "NewTel-CA"),
    ):
        if token in haystack:
            return label
    return issuer_name or "Khong ro"


def extract_certificate_details_from_der(cert_der: bytes | None) -> dict[str, object] | None:
    if not cert_der:
        return None
    try:
        from cryptography import x509

        cert = x509.load_der_x509_certificate(cert_der)
        subject_name = _extract_display_name(cert.subject)
        issuer_name = _extract_display_name(cert.issuer)
        raw_subject = cert.subject.rfc4514_string()
        raw_issuer = cert.issuer.rfc4514_string()
        tax_code = _extract_tax_code_from_text(f"{subject_name} {raw_subject} {raw_issuer}") or ""

        not_before = _as_utc(
            getattr(cert, "not_valid_before_utc", None) or getattr(cert, "not_valid_before", None)
        )
        not_after = _as_utc(
            getattr(cert, "not_valid_after_utc", None) or getattr(cert, "not_valid_after", None)
        )
        now = datetime.now(timezone.utc)
        if not_before is not None and now < not_before:
            cert_status = "Chua hieu luc"
        elif not_after is not None and now > not_after:
            cert_status = "Het han"
        else:
            cert_status = "Con han"

        return {
            "subject_name": subject_name or "Khong ro",
            "subject_raw": raw_subject,
            "issuer_name": issuer_name or "Khong ro",
            "issuer_raw": raw_issuer,
            "issuer_provider": _normalize_provider_name(issuer_name or raw_issuer),
            "tax_code": tax_code,
            "serial_hex": format(cert.serial_number, "X"),
            "public_key_bits": getattr(getattr(cert, "public_key", lambda: None)(), "key_size", None),
            "valid_from_dt": not_before,
            "valid_to_dt": not_after,
            "valid_from": _format_vn_datetime(not_before),
            "valid_to": _format_vn_datetime(not_after),
            "certificate_status": cert_status,
        }
    except Exception:
        return None


def extract_signer_identity_from_der(cert_der: bytes | None) -> dict[str, str] | None:
    if not cert_der:
        return None
    try:
        details = extract_certificate_details_from_der(cert_der)
        if not details:
            return None
        safe_name = strip_accents(str(details.get("subject_name") or ""))
        safe_issuer = strip_accents(str(details.get("issuer_name") or ""))
        identity: dict[str, str] = {
            "name": safe_name or "Khong ro",
            "subject": str(details.get("subject_raw") or ""),
            "issuer_name": safe_issuer or "Khong ro",
            "issuer": str(details.get("issuer_raw") or ""),
            "serial_hex": str(details.get("serial_hex") or ""),
            "display_name": str(details.get("subject_name") or safe_name or "Khong ro"),
            "issuer_provider": str(details.get("issuer_provider") or safe_issuer or "Khong ro"),
            "valid_from": str(details.get("valid_from") or ""),
            "valid_to": str(details.get("valid_to") or ""),
            "certificate_status": str(details.get("certificate_status") or ""),
        }
        tax_code = _extract_tax_code_from_text(f"{identity['name']} {identity['subject']}")
        if tax_code:
            identity["tax_code"] = tax_code
        return identity
    except Exception:
        return None


def build_signature_info_text(
    *,
    subject_name: str,
    tax_code: str = "",
    issuer_provider: str = "",
    serial_hex: str = "",
    valid_from: str = "",
    valid_to: str = "",
    certificate_status: str = "",
    signed_at: str = "",
) -> str:
    lines = [
        "ĐÃ KÝ SỐ",
        f"Tên chủ thể chứng thư số: {subject_name or 'Không rõ'}",
        f"Mã số thuế / CCCD: {tax_code or 'Không có'}",
        f"Tên nhà cung cấp chữ ký số: {issuer_provider or 'Không rõ'}",
        f"Số serial chứng thư số: {serial_hex or 'Không rõ'}",
        f"Thời hạn hiệu lực chứng thư: {valid_from or 'Không rõ'} - {valid_to or 'Không rõ'}",
        f"Trạng thái chứng thư: {certificate_status or 'Không rõ'}",
        f"Thời điểm ký: {signed_at or 'Không rõ'}",
    ]
    return "\n".join(lines)


def build_vietnamese_stamp_style(
    signer_display_name: str,
    *,
    tax_code: str | None = None,
    signed_at: str | None = None,
    issuer_name: str | None = None,
    token_serial: str | None = None,
    cert_serial: str | None = None,
):
    import textwrap
    from pyhanko.pdf_utils.layout import AxisAlignment, Margins, SimpleBoxLayoutRule
    from pyhanko.pdf_utils.text import TextBoxStyle
    from pyhanko.stamp import TextStampStyle

    safe_name = str(signer_display_name or "").strip() or "Khong ro"
    display_tax = tax_code or _extract_tax_code_from_text(safe_name)

    def _wrap_value(label: str, value: str, *, width: int = 33, max_lines: int = 2) -> list[str]:
        value = (value or "Khong ro").strip()
        chunks = textwrap.wrap(
            value,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        )[:max_lines] or ["Khong ro"]
        return [f"{label}: {chunks[0]}"] + [f"  {chunk}" for chunk in chunks[1:]]

    subject = safe_name or "Khong ro"
    issuer = str(issuer_name or "").strip() or "Khong ro"
    serial = token_serial or cert_serial or ""
    stamp_lines = [
        "ĐÃ KÝ SỐ",
        *_wrap_value("Tên chủ thể chứng thư số", subject, width=31, max_lines=2),
        *_wrap_value("Tên nhà cung cấp chữ ký số", issuer, width=34, max_lines=1),
        f"Thời điểm ký: {signed_at or 'Không rõ'}",
        f"Mã số thuế / CCCD: {display_tax or 'Không có'}",
    ]
    if serial:
        stamp_lines.extend(_wrap_value("Số serial chứng thư số", serial, width=34, max_lines=1))
    stamp_lines.append("Trạng thái: Hợp lệ; tài liệu chưa bị sửa")
    stamp_text = "\n".join(stamp_lines)

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
            font_size=7,
            leading=9,
            border_width=0,
            box_layout_rule=layout_rule,
        ),
    )


def _pick_signing_certificate(session, attribute_mod, object_class_mod):
    certs = list(session.get_objects({attribute_mod.CLASS: object_class_mod.CERTIFICATE}))
    if not certs:
        raise RuntimeError("Khong tim thay certificate tren USB Token!")

    private_key_ids = {
        _safe_get_pkcs11_attr(key_obj, attribute_mod.ID)
        for key_obj in session.get_objects({attribute_mod.CLASS: object_class_mod.PRIVATE_KEY})
    }
    private_key_ids.discard(None)

    scored_candidates: list[tuple[tuple[int, int, int, int], object, bytes | None, dict[str, object] | None]] = []
    for index, cert in enumerate(certs):
        cert_id = _safe_get_pkcs11_attr(cert, attribute_mod.ID)
        cert_der = _safe_get_pkcs11_attr(cert, attribute_mod.VALUE)
        cert_details = extract_certificate_details_from_der(cert_der)
        subject_raw = str(cert_details.get("subject_raw") if cert_details else "")
        issuer_raw = str(cert_details.get("issuer_raw") if cert_details else "")
        matches_private_key = cert_id in private_key_ids if private_key_ids else True
        likely_leaf = bool(subject_raw) and subject_raw != issuer_raw
        has_subject = bool(str(cert_details.get("subject_name") if cert_details else "").strip())
        score = (
            1 if matches_private_key else 0,
            1 if likely_leaf else 0,
            1 if has_subject else 0,
            -index,
        )
        scored_candidates.append((score, cert, cert_id, cert_details))

    _score, signing_cert, cert_id, cert_details = max(scored_candidates, key=lambda item: item[0])
    return signing_cert, cert_id, cert_details


async def sign_pdf_with_session(
    session,
    lib_path: str,
    input_path: str,
    output_path: str,
    *,
    signer_name: str = "Khong ro",
    page_number: int = 1,
    box: tuple[float, float, float, float] | None = None,
    token_serial: str | None = None,
) -> None:
    """Core pyHanko signing - OS-agnostic. Caller manages the PKCS#11 session."""
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
        _signing_cert, cert_id, cert_details = _pick_signing_certificate(
            session,
            Attribute,
            ObjectClass,
        )
        if cert_id is None:
            raise RuntimeError("Khong tim thay khoa bi mat phu hop voi chung thu so tren USB Token!")
        cert_name = str(cert_details.get("subject_name") if cert_details else "")
        cert_tax = str(cert_details.get("tax_code") if cert_details else "") or ""
        cert_issuer = str(cert_details.get("issuer_provider") if cert_details else "") or ""
        cert_serial = str(cert_details.get("serial_hex") if cert_details else "") or ""

        signer_obj = PKCS11Signer(session, cert_id=cert_id)
        display_name = (signer_name or "").strip() or cert_name or "Khong ro"
        visible_subject = cert_name or display_name
        signed_at_vn = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        field_name = f"Signature_{uuid.uuid4().hex[:12]}"
        stamp_style = build_vietnamese_stamp_style(
            visible_subject,
            tax_code=cert_tax,
            signed_at=signed_at_vn,
            issuer_name=cert_issuer,
            token_serial=token_serial,
            cert_serial=cert_serial,
        )
        with open(input_path, "rb") as f:
            writer = IncrementalPdfFileWriter(f, strict=False)
            meta = PdfSignatureMetadata(field_name=field_name, name=visible_subject)
            pdf_signer = signers.PdfSigner(
                signature_meta=meta,
                signer=signer_obj,
                stamp_style=stamp_style,
                new_field_spec=fields.SigFieldSpec(
                    sig_field_name=field_name,
                    box=box,
                    on_page=max(0, page_number - 1),
                ),
            )
            with open(tmp_path, "wb") as out:
                await pdf_signer.async_sign_pdf(writer, output=out)

        os.replace(tmp_path, output_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def sign_pdf_with_pkcs12(
    pfx_path: str,
    passphrase: str | bytes | None,
    input_path: str,
    output_path: str,
    *,
    signer_name: str = "Khong ro",
    page_number: int = 1,
    box: tuple[float, float, float, float] | None = None,
) -> None:
    """Sign a PDF using a local PKCS#12/PFX file."""
    from datetime import datetime

    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers
    from pyhanko.sign.signers import PdfSignatureMetadata

    if box is None:
        box = (50, 50, 300, 100)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()

    try:
        passphrase_bytes = passphrase.encode("utf-8") if isinstance(passphrase, str) else passphrase
        signer = signers.SimpleSigner.load_pkcs12(
            pfx_path,
            passphrase=passphrase_bytes,
        )

        cert_details = None
        signing_cert = getattr(signer, "signing_cert", None)
        if signing_cert is not None:
            cert_der = None
            if hasattr(signing_cert, "dump"):
                try:
                    cert_der = signing_cert.dump()
                except Exception:
                    cert_der = None
            if cert_der is not None:
                cert_details = extract_certificate_details_from_der(cert_der)

        cert_name = str(cert_details.get("subject_name") if cert_details else "")
        cert_tax = str(cert_details.get("tax_code") if cert_details else "") or ""
        cert_issuer = str(cert_details.get("issuer_provider") if cert_details else "") or ""
        cert_serial = str(cert_details.get("serial_hex") if cert_details else "") or ""

        display_name = (
            (signer_name or "").strip()
            or cert_name
            or os.path.splitext(os.path.basename(pfx_path))[0]
            or "Khong ro"
        )
        visible_subject = cert_name or display_name
        field_name = f"Signature_{uuid.uuid4().hex[:12]}"
        signed_at_vn = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        stamp_style = build_vietnamese_stamp_style(
            visible_subject,
            tax_code=cert_tax,
            signed_at=signed_at_vn,
            issuer_name=cert_issuer,
            cert_serial=cert_serial,
        )
        with open(input_path, "rb") as f:
            writer = IncrementalPdfFileWriter(f, strict=False)
            meta = PdfSignatureMetadata(field_name=field_name, name=visible_subject)
            pdf_signer = signers.PdfSigner(
                signature_meta=meta,
                signer=signer,
                stamp_style=stamp_style,
                new_field_spec=fields.SigFieldSpec(
                    sig_field_name=field_name,
                    box=box,
                    on_page=max(0, page_number - 1),
                ),
            )
            with open(tmp_path, "wb") as out:
                await pdf_signer.async_sign_pdf(writer, output=out)

        os.replace(tmp_path, output_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def validate_signed_pdf_status(path: str) -> dict[str, object]:
    """Validate the PDF signature integrity first, then best-effort trust."""
    try:
        import asyncio

        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import async_validate_pdf_signature
        from pyhanko.sign.validation.generic_cms import validate_sig_integrity
        from pyhanko.sign.validation.utils import CMSAlgorithmUsagePolicy
        from pyhanko_certvalidator.policy_decl import DisallowWeakAlgorithmsPolicy

        with open(path, "rb") as f:
            reader = PdfFileReader(f, strict=False)
            signatures = list(reader.embedded_signatures)
            if not signatures:
                return {
                    "ok": False,
                    "integrity_ok": False,
                    "intact": False,
                    "valid": False,
                    "trusted": False,
                    "revoked": False,
                    "overall_status": "Không tìm thấy chữ ký số hợp lệ trong PDF.",
                    "message": "Không tìm thấy chữ ký số hợp lệ trong PDF đã lưu. Nếu chỉ chèn ảnh hoặc text thì đây không phải chữ ký số.",
                }

            embedded_sig = signatures[-1]
            cert_details = None
            signer_cert = getattr(embedded_sig, "signer_cert", None)
            if signer_cert is not None and hasattr(signer_cert, "dump"):
                try:
                    cert_details = extract_certificate_details_from_der(signer_cert.dump())
                except Exception:
                    cert_details = None

            public_key_bits = None
            if cert_details:
                public_key_bits = cert_details.get("public_key_bits")

            policy_warning = ""
            if isinstance(public_key_bits, int) and public_key_bits and public_key_bits < 2048:
                policy_warning = f"Khóa RSA {public_key_bits} bit, thấp hơn khuyến nghị 2048 bit."

            permissive_policy = CMSAlgorithmUsagePolicy.lift_policy(
                DisallowWeakAlgorithmsPolicy(rsa_key_size_threshold=0)
            )

            try:
                raw_digest = embedded_sig.compute_digest()
                signer_cert_obj = getattr(embedded_sig, "signer_cert", None)
                if signer_cert_obj is None:
                    raise RuntimeError("Không tìm thấy chứng thư của người ký.")

                digest_ok, sig_ok = validate_sig_integrity(
                    embedded_sig.signer_info,
                    signer_cert_obj,
                    "data",
                    raw_digest,
                    algorithm_usage_policy=permissive_policy,
                )
                intact = bool(digest_ok)
                valid = bool(sig_ok)
            except Exception as exc:
                intact = False
                valid = False
                trust_error = str(exc)
            else:
                trust_error = ""

            status = None
            trusted = False
            revoked = False
            if intact and valid:
                try:
                    status = asyncio.run(async_validate_pdf_signature(embedded_sig))
                    trusted = bool(getattr(status, "trusted", False))
                    revoked = bool(getattr(status, "revoked", False))
                except Exception as exc:
                    trust_error = str(exc)

            signing_time = getattr(status, "signer_reported_dt", None) or getattr(
                embedded_sig, "self_reported_timestamp", None
            )
            signing_time_ok = None
            if cert_details and signing_time is not None:
                valid_from_dt = cert_details.get("valid_from_dt")
                valid_to_dt = cert_details.get("valid_to_dt")
                signing_time_utc = _as_utc(signing_time)
                if (
                    isinstance(valid_from_dt, datetime)
                    and isinstance(valid_to_dt, datetime)
                    and signing_time_utc is not None
                ):
                    signing_time_ok = valid_from_dt <= signing_time_utc <= valid_to_dt

            integrity_ok = intact and valid
            overall_ok = integrity_ok and not revoked
            if overall_ok and trusted:
                overall_status = "Chữ ký số hợp lệ và đã được xác minh."
            elif overall_ok and signing_time_ok is False:
                overall_status = "Chữ ký hợp lệ về mặt kỹ thuật nhưng thời điểm ký ngoài thời hạn hiệu lực."
            elif overall_ok:
                overall_status = "Chữ ký số hợp lệ về mặt kỹ thuật, nhưng chưa xác minh được đầy đủ chuỗi tin cậy."
            elif revoked:
                overall_status = "Chữ ký bị thu hồi."
            else:
                overall_status = "Chữ ký không hợp lệ hoặc tài liệu đã bị sửa đổi."
                if trust_error:
                    overall_status = f"{overall_status} {trust_error}"

            subject_name = str(cert_details.get("subject_name") if cert_details else "")
            issuer_name = str(cert_details.get("issuer_provider") if cert_details else "")
            serial_hex = str(cert_details.get("serial_hex") if cert_details else "")
            valid_from = str(cert_details.get("valid_from") if cert_details else "")
            valid_to = str(cert_details.get("valid_to") if cert_details else "")
            cert_status = str(cert_details.get("certificate_status") if cert_details else "")

            return {
                "ok": integrity_ok and not revoked,
                "integrity_ok": integrity_ok,
                "intact": intact,
                "valid": valid,
                "trusted": trusted,
                "revoked": revoked,
                "signing_time": signing_time,
                "signing_time_ok": signing_time_ok,
                "subject_name": subject_name,
                "issuer_name": issuer_name,
                "serial_hex": serial_hex,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "certificate_status": cert_status,
                "overall_status": overall_status,
                "message": overall_status,
                "validation_error": trust_error,
                "policy_warning": policy_warning,
            }
    except Exception as exc:
        return {
            "ok": False,
            "integrity_ok": False,
            "intact": False,
            "valid": False,
            "trusted": False,
            "revoked": False,
            "overall_status": f"Chua kiem tra duoc: {exc}",
            "message": f"Chua kiem tra duoc trang thai chu ky: {exc}",
        }
