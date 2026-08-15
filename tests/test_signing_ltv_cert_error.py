"""Ký PFX với chứng thư tự ký (self-signed) khi bật LTV trước đây ném thẳng
pyhanko_certvalidator.errors.InvalidCertificateError (traceback tiếng Anh khó
hiểu lộ ra UI qua QMessageBox.setDetailedText) - phát hiện thật khi tự tay
test ký PFX qua GUI 15/08/2026 (xem packages/signing/shared.py::_run_sign_pdf).
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from packages.signing.shared import sign_pdf_with_pkcs12


def _make_self_signed_pfx(path, *, password: bytes = b"1234"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "QA Self-Signed Test")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b"QA Self-Signed Test", key, cert, None,
            serialization.BestAvailableEncryption(password),
        )
    )


def _make_pdf(path):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawString(100, 750, "LTV cert error test")
    c.showPage()
    c.save()


def test_self_signed_cert_with_ltv_raises_friendly_runtime_error(tmp_path):
    pfx = tmp_path / "self_signed.pfx"
    base = tmp_path / "base.pdf"
    signed = tmp_path / "signed.pdf"
    _make_self_signed_pfx(pfx)
    _make_pdf(base)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            sign_pdf_with_pkcs12(
                str(pfx), "1234", str(base), str(signed),
                signer_name="QA Self-Signed Test", page_number=1, box=(50, 600, 250, 700),
                enable_ltv=True,
            )
        )

    message = str(exc_info.value)
    assert "LTV" in message
    assert "InvalidCertificateError" not in message
    assert "Traceback" not in message
    # Không tạo ra file .pdf đã ký nào khi ký thất bại.
    assert not signed.exists()


def test_self_signed_cert_without_ltv_still_signs_successfully(tmp_path):
    """Regression guard: fix cho lỗi LTV không được làm hỏng luồng ký PFX
    bình thường (enable_ltv=False, mặc định)."""
    pfx = tmp_path / "self_signed.pfx"
    base = tmp_path / "base.pdf"
    signed = tmp_path / "signed.pdf"
    _make_self_signed_pfx(pfx)
    _make_pdf(base)

    asyncio.run(
        sign_pdf_with_pkcs12(
            str(pfx), "1234", str(base), str(signed),
            signer_name="QA Self-Signed Test", page_number=1, box=(50, 600, 250, 700),
        )
    )

    assert signed.exists()
    assert signed.read_bytes().startswith(b"%PDF-")
