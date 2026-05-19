import asyncio
import os
from datetime import datetime

PKCS11_CANDIDATES = [
    "eps2003csp11.dll",
    "vnpt_ca_pkcs11.dll",
    "FPT_Token.dll",
    "acospkcs11.dll",
    "BkavCAPKCS11.dll",
    "eTPKCS11.dll",
    "eps2003csp11v2.dll",
    "cvP11.dll",
    "ViettelCA.dll",
    "ViettelPKCS11.dll",
    "viettelca11.dll",
    "viettel-ca_v6.dll",
    "viettel-ca_v6_s.dll",
]

_LAST_PKCS11_ERROR = ""
_VIETNAMESE_FONT_CANDIDATES = [
    "tahoma.ttf",
    "arial.ttf",
    "segoeui.ttf",
    "times.ttf",
]


def _safe_get_pkcs11_attr(obj, attr):
    try:
        return obj[attr]
    except Exception:
        return None


def _extract_tax_code_from_text(text: str) -> str | None:
    import re

    # VN MST commonly has 10 digits, or 10 digits + branch suffix (e.g. 0312345678-001).
    match = re.search(r"\b(\d{10}(?:-\d{3})?)\b", text or "")
    if match:
        return match.group(1)

    # Some certs expose IDs with 13-14 contiguous digits.
    match = re.search(r"\b(\d{13,14})\b", text or "")
    return match.group(1) if match else None


def _strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để tránh lỗi encoding trong môi trường EXE"""
    import unicodedata
    if not text:
        return ""
    # Chuẩn hóa về dạng NFKD để tách ký tự gốc và dấu
    nfkd_form = unicodedata.normalize('NFKD', text)
    # Loại bỏ các ký tự dấu (non-spacing marks)
    only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Thay thế chữ Đ/đ đặc biệt
    return only_ascii.replace('đ', 'd').replace('Đ', 'D').strip()


def _extract_signer_identity_from_der(cert_der: bytes | None) -> dict[str, str] | None:
    if not cert_der:
        return None

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        cert = x509.load_der_x509_certificate(cert_der)
        subject = cert.subject

        common_names = subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if common_names:
            name = common_names[0].value.strip()
        else:
            org_names = subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
            name = org_names[0].value.strip() if org_names else ""

        # Ép tên về dạng không dấu để an toàn tuyệt đối trên mọi môi trường
        safe_name = _strip_accents(name)

        identity = {
            "name": safe_name or "Khong ro",
            "subject": subject.rfc4514_string(),
            "serial_hex": format(cert.serial_number, "X"),
        }

        tax_code = _extract_tax_code_from_text(
            f"{identity['name']} {identity['subject']}"
        )
        if tax_code:
            identity["tax_code"] = tax_code

        return identity
    except Exception:
        return None


def get_last_pkcs11_error() -> str:
    return _LAST_PKCS11_ERROR


def _candidate_paths() -> list[str]:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    dirs = [
        os.path.join(system_root, "System32"),
        os.path.join(system_root, "SysWOW64"),
    ]
    paths = []
    seen = set()
    for dll in PKCS11_CANDIDATES:
        for d in dirs:
            p = os.path.join(d, dll)
            if os.path.exists(p) and p not in seen:
                seen.add(p)
                paths.append(p)
    return paths


def detect_pkcs11_lib() -> str | None:
    global _LAST_PKCS11_ERROR
    _LAST_PKCS11_ERROR = ""
    errors = []

    for path in _candidate_paths():
        try:
            import pkcs11 as p11

            lib = p11.lib(path)
            if any(True for _ in lib.get_tokens()):
                return path
        except Exception as e:
            msg = str(e).lower()
            if "error 126" in msg:
                errors.append(f"{os.path.basename(path)}: lỗi 126 (thiếu DLL phụ thuộc hoặc sai x86/x64)")
            elif "module could not be found" in msg:
                errors.append(f"{os.path.basename(path)}: không tìm thấy module")
            else:
                errors.append(f"{os.path.basename(path)}: {str(e)[:120]}")
            continue

    _LAST_PKCS11_ERROR = (
        "\n".join(errors[:4]) if errors
        else "Không tìm thấy thư viện PKCS#11 phù hợp trong hệ thống."
    )
    return None


def get_token_signer_info(pin: str | None = None) -> dict[str, str] | None:
    lib_path = detect_pkcs11_lib()
    if not lib_path:
        return None

    try:
        import pkcs11 as p11
        from pkcs11.constants import Attribute, ObjectClass

        lib = p11.lib(lib_path)
        token = next(lib.get_tokens(), None)
        if token is None:
            return None

        open_kwargs = {"rw": False}
        if pin:
            open_kwargs["user_pin"] = pin

        with token.open(**open_kwargs) as session:
            certs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
            if not certs:
                return None

            for cert in reversed(certs):
                cert_der = _safe_get_pkcs11_attr(cert, Attribute.VALUE)
                identity = _extract_signer_identity_from_der(cert_der)
                if identity:
                    identity["driver"] = os.path.basename(lib_path)
                    return identity
    except Exception:
        return None

    return None


def _pick_vietnamese_font_path() -> str | None:
    fonts_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts")
    for font_name in _VIETNAMESE_FONT_CANDIDATES:
        candidate = os.path.join(fonts_dir, font_name)
        if os.path.exists(candidate):
            return candidate
    return None


def _build_vietnamese_stamp_style(
    signer_display_name: str,
    *,
    tax_code: str | None = None,
    signed_at: str | None = None,
):
    """Build stable, readable signature stamp without Unicode stream glitches."""
    import re
    import textwrap
    import unicodedata
    from pyhanko.pdf_utils.layout import AxisAlignment, Margins, SimpleBoxLayoutRule
    from pyhanko.pdf_utils.text import TextBoxStyle
    from pyhanko.stamp import TextStampStyle

    def _ascii_fold(text: str) -> str:
        folded = unicodedata.normalize("NFKD", text or "")
        return "".join(ch for ch in folded if not unicodedata.combining(ch))

    raw_name = (signer_display_name or "").strip() or "Khong ro"
    safe_name = _ascii_fold(raw_name)

    # Prefer tax code from certificate metadata. Fall back to extracting from name.
    display_tax_code = tax_code or _extract_tax_code_from_text(safe_name)
    display_name = safe_name

    wrapped = textwrap.wrap(display_name, width=28) or ["Khong ro"]
    wrapped = wrapped[:2]
    signer_lines = "\n".join(
        f"Ky boi: {line}" if idx == 0 else f"       {line}"
        for idx, line in enumerate(wrapped)
    )
    tax_line = f"MST: {display_tax_code}" if display_tax_code else "MST: Khong ro"
    time_line = f"Ky luc: {signed_at}" if signed_at else "Ky luc: Khong ro"
    stamp_text = "DA KY SO\n" + signer_lines + "\n" + tax_line + "\n" + time_line

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


async def sign_pdf(
    input_path: str,
    output_path: str,
    pin: str,
    *,
    signer_name: str = "Khong ro",
    page_number: int = 1,
    box: tuple[float, float, float, float] | None = None,
):
    import pkcs11 as p11
    from pkcs11.constants import Attribute, ObjectClass
    from pyhanko.sign import signers, fields
    from pyhanko.sign.pkcs11 import PKCS11Signer
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign.signers import PdfSignatureMetadata
    import tempfile, shutil

    lib_path = detect_pkcs11_lib()
    if not lib_path:
        raise RuntimeError(
            "Không tìm thấy USB Token!\n"
            "Vui lòng cắm thiết bị chữ ký vào và thử lại.\n\n"
            f"Chi tiết: {get_last_pkcs11_error()}"
        )

    lib = p11.lib(lib_path)
    token = next(lib.get_tokens())
    session = token.open(user_pin=pin, rw=False)

    if box is None:
        box = (50, 50, 300, 100)

    # Ghi ra file tạm trước, tránh ghi đè file gốc đang mở
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()

    try:
        certs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
        if not certs:
            raise RuntimeError("Không tìm thấy certificate trên USB Token!")
        signing_cert = certs[-1]
        cert_id = signing_cert[Attribute.ID]

        cert_identity = _extract_signer_identity_from_der(
            _safe_get_pkcs11_attr(signing_cert, Attribute.VALUE)
        )
        cert_name = cert_identity.get("name") if cert_identity else ""
        cert_tax_code = cert_identity.get("tax_code") if cert_identity else None

        signer = PKCS11Signer(session, cert_id=cert_id)
        signer_display_name = (signer_name or "").strip() or cert_name or "Khong ro"
        signed_at_vn = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        stamp_style = _build_vietnamese_stamp_style(
            signer_display_name,
            tax_code=cert_tax_code,
            signed_at=signed_at_vn,
        )

        with open(input_path, "rb") as f:
            writer = IncrementalPdfFileWriter(f)
            fields.append_signature_field(
                writer,
                sig_field_spec=fields.SigFieldSpec(
                    sig_field_name="Signature1",
                    box=box,
                    on_page=max(0, page_number - 1)
                )
            )
            meta = PdfSignatureMetadata(
                field_name="Signature1",
                name=signer_display_name,
            )
            pdf_signer = signers.PdfSigner(
                signature_meta=meta,
                signer=signer,
                stamp_style=stamp_style,
            )
            with open(tmp_path, "wb") as out:
                await pdf_signer.async_sign_pdf(writer, output=out)

        # Chỉ copy đè khi ký xong thành công
        shutil.copy2(tmp_path, output_path)

    finally:
        session.close()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
