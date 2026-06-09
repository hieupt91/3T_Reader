from types import SimpleNamespace


def test_pick_signing_certificate_prefers_private_key_leaf(monkeypatch):
    from packages.signing import shared

    class FakePkcs11Object:
        def __init__(self, attrs):
            self._attrs = attrs

        def __getitem__(self, key):
            return self._attrs[key]

    class FakeSession:
        def __init__(self, certs, keys):
            self._certs = certs
            self._keys = keys

        def get_objects(self, query):
            klass = query.get("class")
            if klass == "cert":
                return list(self._certs)
            if klass == "pkey":
                return list(self._keys)
            return []

    attr = SimpleNamespace(CLASS="class", CERTIFICATE="cert", PRIVATE_KEY="pkey", ID="id", VALUE="value")
    obj_class = SimpleNamespace(CERTIFICATE="cert", PRIVATE_KEY="pkey")

    leaf = FakePkcs11Object({"id": b"leaf", "value": b"leaf"})
    intermediate = FakePkcs11Object({"id": b"intermediate", "value": b"intermediate"})
    root = FakePkcs11Object({"id": b"root", "value": b"root"})
    private_key = FakePkcs11Object({"id": b"leaf"})

    details_map = {
        b"leaf": {"subject_name": "Leaf", "subject_raw": "CN=Leaf", "issuer_raw": "CN=VNPT CA"},
        b"intermediate": {"subject_name": "VNPT CA", "subject_raw": "CN=VNPT CA", "issuer_raw": "CN=Root"},
        b"root": {"subject_name": "Root", "subject_raw": "CN=Root", "issuer_raw": "CN=Root"},
    }
    monkeypatch.setattr(shared, "extract_certificate_details_from_der", lambda der: details_map.get(der))

    cert, cert_id, cert_details = shared._pick_signing_certificate(
        FakeSession([leaf, intermediate, root], [private_key]),
        attr,
        obj_class,
    )

    assert cert is leaf
    assert cert_id == b"leaf"
    assert cert_details["subject_name"] == "Leaf"


def test_extract_signature_text_lines_supports_tj_arrays():
    from app.local_server import _extract_signature_text_lines

    class FakeStream:
        def read_bytes(self):
            return b"[(Signed by ) -120 (VNPT-CA) 80 <00410042>] TJ"

    annot = {"/AP": {"/N": FakeStream()}}
    lines = _extract_signature_text_lines(annot)

    assert "Signed by" in lines
    assert "VNPT-CA" in lines
    assert "AB" in lines


def test_signature_overlay_does_not_synthesize_label_for_image_only_widget():
    from app.local_server import _signature_overlay_from_annot

    class FakeStream:
        def read_bytes(self):
            return b"q 100 0 0 40 0 0 cm /Im0 Do Q"

    annot = {
        "/Rect": [10, 20, 110, 60],
        "/AP": {"/N": FakeStream()},
        "/V": object(),
    }

    overlay = _signature_overlay_from_annot(annot)

    assert overlay is not None
    assert overlay["signed"] is True
    assert overlay["lines"] == []


def test_validate_signed_pdf_status_prefers_clicked_field_name(monkeypatch):
    from packages.signing import shared

    class FakeSig:
        def __init__(self, field_name):
            self.field_name = field_name
            self.signer_cert = None
            self.self_reported_timestamp = None
            self.sig_object = {}
            self.signer_info = object()

        def compute_digest(self):
            raise RuntimeError(self.field_name)

    class FakeReader:
        def __init__(self, _stream, strict=False):
            self.embedded_signatures = [FakeSig("sig_a"), FakeSig("sig_b")]

    monkeypatch.setattr("pyhanko.pdf_utils.reader.PdfFileReader", FakeReader)

    report = shared.validate_signed_pdf_status(__file__, field_name="sig_a")

    assert report["selected_field_name"] == "sig_a"
    assert "sig_a" in str(report["validation_error"])


def test_validate_signed_pdf_status_returns_unsigned_field_report_when_no_embedded_match(monkeypatch):
    from packages.signing import shared

    class FakeSig:
        def __init__(self, field_name):
            self.field_name = field_name

    class FakeReader:
        def __init__(self, _stream, strict=False):
            self.embedded_signatures = [FakeSig("sig_a")]

    monkeypatch.setattr("pyhanko.pdf_utils.reader.PdfFileReader", FakeReader)
    monkeypatch.setattr(
        shared,
        "_extract_signature_field_report",
        lambda _path, field_name: {
            "selected_field_name": field_name,
            "display_signer": "Chưa ký",
            "overall_status": "Ô ký này chưa được ký số.",
            "message": "Ô ký này chưa được ký số.",
            "ok": False,
            "integrity_ok": False,
            "intact": False,
            "valid": False,
            "trusted": False,
            "revoked": False,
        },
    )

    report = shared.validate_signed_pdf_status(__file__, field_name="sig_unsigned")

    assert report["selected_field_name"] == "sig_unsigned"
    assert report["display_signer"] == "Chưa ký"
    assert "chưa được ký" in report["overall_status"].lower()


def test_validate_signed_pdf_status_uses_field_report_on_outer_parse_error(monkeypatch):
    from packages.signing import shared

    class BoomReader:
        def __init__(self, _stream, strict=False):
            raise RuntimeError("parse boom")

    monkeypatch.setattr("pyhanko.pdf_utils.reader.PdfFileReader", BoomReader)
    monkeypatch.setattr(
        shared,
        "_extract_signature_field_report",
        lambda _path, field_name: {
            "selected_field_name": field_name,
            "clicked_field": field_name,
            "field_signed": True,
            "display_signer": "USB Signer",
            "issuer_name": "VNPT-CA",
            "serial_hex": "ABC123",
            "valid_from": "01/01/2026 00:00:00",
            "valid_to": "01/01/2027 00:00:00",
            "certificate_status": "Con han",
            "validation_summary_lines": [],
        },
    )

    report = shared.validate_signed_pdf_status(__file__, field_name="usb_sig")

    assert report["clicked_field"] == "usb_sig"
    assert report["display_signer"] == "USB Signer"
    assert report["issuer_name"] == "VNPT-CA"
    assert report["serial_hex"] == "ABC123"
    assert "parse boom" in report["validation_error"]
