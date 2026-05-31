from __future__ import annotations

from app.actions.annotate import _normalize_box_for_page_rotation
from app.language_manager import _normalize_language_pack_payload


def test_normalize_language_pack_payload_rejects_wrong_code():
    payload = {
        "code": "en",
        "strings": {"menu.file": "File"},
    }

    assert _normalize_language_pack_payload(payload, expected_code="vi") == {}


def test_normalize_language_pack_payload_accepts_wrapped_strings():
    payload = {
        "code": "vi",
        "strings": {"menu.file": "Tep"},
    }

    assert _normalize_language_pack_payload(payload, expected_code="vi") == {"menu.file": "Tep"}


def test_normalize_box_for_page_rotation_swaps_coordinates():
    box = (10.0, 20.0, 30.0, 40.0)

    rotated = _normalize_box_for_page_rotation(box, page_w=100.0, page_h=200.0, rotation=90)

    assert rotated == (20.0, 170.0, 40.0, 190.0)
