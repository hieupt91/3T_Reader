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


def test_text_note_annotation_roundtrip(tmp_path):
    import pytest

    pikepdf = pytest.importorskip("pikepdf")
    from app.actions.annotate import add_annotation, load_annotations

    out = tmp_path / "notes.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    note_id = add_annotation(
        pdf,
        page_idx=0,
        subtype="Text",
        rect=(170, 170, 188, 188),
        content="Review this section",
        author="Tester",
    )
    pdf.save(out)
    pdf.close()

    notes = load_annotations(str(out))

    assert len(notes) == 1
    assert notes[0]["id"] == note_id
    assert notes[0]["type"] == "Text"
    assert notes[0]["content"] == "Review this section"
    assert notes[0]["author"] == "Tester"


def test_note_rect_position_presets_and_custom_are_clamped():
    import pytest

    pikepdf = pytest.importorskip("pikepdf")
    from app.actions.annotate import (
        NOTE_POSITION_BOTTOM_LEFT,
        NOTE_POSITION_CUSTOM,
        NOTE_POSITION_TOP_LEFT,
        _note_rect_for_position,
    )

    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(200, 300))
    page = pdf.pages[0]

    assert _note_rect_for_position(page, NOTE_POSITION_TOP_LEFT, 0) == (12.0, 270.0, 30.0, 288.0)
    assert _note_rect_for_position(page, NOTE_POSITION_BOTTOM_LEFT, 0) == (12.0, 12.0, 30.0, 30.0)

    custom = _note_rect_for_position(
        page,
        NOTE_POSITION_CUSTOM,
        0,
        x_percent=100.0,
        y_percent=100.0,
    )

    assert custom == (170.0, 12.0, 188.0, 30.0)
    pdf.close()
