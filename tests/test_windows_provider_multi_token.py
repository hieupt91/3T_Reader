"""Lỗi số X (ghi chú cũ): ký thất bại với token thứ 2 khi cắm 2 USB token
song song - báo pkcs11.exceptions.PinIncorrect dù PIN đúng. Nguyên nhân:
_get_token_by_info() chỉ khớp theo serial phần cứng, rồi rơi thẳng xuống
token_index nếu serial trống/không khớp - thứ tự liệt kê token không đảm
bảo ổn định giữa các lần p11.lib() khởi tạo riêng biệt (chọn token và ký
thật chạy 2 tiến trình con khác nhau) khi 2 token giống hệt nhau về phần
cứng, khiến PIN đúng của người dùng bị áp nhầm sang token khác."""
from __future__ import annotations

from packages.signing import windows_provider as wp
from packages.signing.provider import TokenInfo


class _FakeSession:
    def __init__(self, certs):
        self._certs = certs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_objects(self, _query):
        return self._certs


class _FakeToken:
    def __init__(self, *, serial: str, cert_marker: str, name: str):
        self.serial = serial
        self._cert_marker = cert_marker
        self.name = name  # test-only, not read by production code

    def open(self, rw=False):
        return _FakeSession([self._cert_marker])

    def __repr__(self):
        return f"<FakeToken {self.name}>"


class _FakeLib:
    def __init__(self, tokens):
        self._tokens = tokens

    def get_tokens(self):
        return list(self._tokens)


def _patch_cert_reading(monkeypatch, marker_to_cert_serial: dict[str, str]):
    monkeypatch.setattr(wp, "_safe_get_pkcs11_attr", lambda cert, _attr: cert)
    monkeypatch.setattr(
        wp, "extract_signer_identity_from_der",
        lambda marker: {"serial_hex": marker_to_cert_serial[marker]} if marker in marker_to_cert_serial else None,
    )


def test_matches_by_hardware_serial_when_available(monkeypatch):
    token_a = _FakeToken(serial="AAA", cert_marker="cert-a", name="A")
    token_b = _FakeToken(serial="BBB", cert_marker="cert-b", name="B")
    lib = _FakeLib([token_a, token_b])
    wanted = TokenInfo(
        driver="d.dll", signer_name="", tax_code="", driver_path="d.dll",
        token_index=0, token_label="", serial="BBB", manufacturer="", model="",
        issuer_name="", cert_serial="",
    )

    result = wp._get_token_by_info(lib, wanted)

    assert result is token_b


def test_two_identical_tokens_with_blank_serial_match_by_cert_serial_not_stale_index(monkeypatch):
    """Kịch bản đúng lỗi thật: 2 token CÙNG MODEL, driver không trả serial
    phần cứng (rỗng cho cả 2) - thứ tự liệt kê ("index") đã đảo ngược giữa
    lần chọn token (token_index=0 lúc đó trỏ đúng token B) và lần ký thật
    (token B giờ ở vị trí 1 trong lib.get_tokens() mới). Phải khớp đúng
    theo cert_serial (định danh thật của người dùng), không được đoán mò
    theo index đã lỗi thời."""
    _patch_cert_reading(monkeypatch, {"cert-a": "SERIAL-A", "cert-b": "SERIAL-B"})
    # Thứ tự ĐẢO NGƯỢC so với lúc chọn token (mô phỏng enumeration không ổn định).
    token_b_now_first = _FakeToken(serial="", cert_marker="cert-b", name="B")
    token_a_now_second = _FakeToken(serial="", cert_marker="cert-a", name="A")
    lib = _FakeLib([token_b_now_first, token_a_now_second])

    wanted = TokenInfo(
        driver="d.dll", signer_name="", tax_code="", driver_path="d.dll",
        token_index=0,  # lỗi thời - lúc chọn, index 0 là token A, giờ index 0 lại là B
        token_label="", serial="", manufacturer="", model="",
        issuer_name="", cert_serial="SERIAL-A",
    )

    result = wp._get_token_by_info(lib, wanted)

    assert result is token_a_now_second, (
        "phải khớp đúng token A theo cert_serial dù token_index đã lỗi thời trỏ nhầm sang B"
    )


def test_falls_back_to_index_only_when_no_serial_info_at_all(monkeypatch):
    _patch_cert_reading(monkeypatch, {})
    token_a = _FakeToken(serial="", cert_marker="cert-a", name="A")
    token_b = _FakeToken(serial="", cert_marker="cert-b", name="B")
    lib = _FakeLib([token_a, token_b])
    wanted = TokenInfo(
        driver="d.dll", signer_name="", tax_code="", driver_path="d.dll",
        token_index=1, token_label="", serial="", manufacturer="", model="",
        issuer_name="", cert_serial="",
    )

    result = wp._get_token_by_info(lib, wanted)

    assert result is token_b
