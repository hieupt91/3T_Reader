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


def test_note_rect_drag_result_is_clamped_to_page():
    import pytest

    pikepdf = pytest.importorskip("pikepdf")
    from app.actions.annotate import _clamp_note_rect_to_page

    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(200, 300))
    page = pdf.pages[0]

    assert _clamp_note_rect_to_page(page, (-50, -50, -32, -32)) == (12.0, 12.0, 30.0, 30.0)
    assert _clamp_note_rect_to_page(page, (240, 340, 258, 358)) == (170.0, 270.0, 188.0, 288.0)
    pdf.close()


def test_update_text_note_rect_by_id(tmp_path):
    import pytest

    pikepdf = pytest.importorskip("pikepdf")
    from app.actions.annotate import add_annotation, load_annotations, _update_note_rect_by_id

    out = tmp_path / "move-note.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    note_id = add_annotation(
        pdf,
        page_idx=0,
        subtype="Text",
        rect=(170, 170, 188, 188),
        content="Move me",
    )

    assert _update_note_rect_by_id(
        pdf,
        page_idx=0,
        note_id=note_id,
        new_rect=(20, 30, 38, 48),
    )
    pdf.save(out)
    pdf.close()

    notes = load_annotations(str(out))
    assert notes[0]["rect"] == (20.0, 30.0, 38.0, 48.0)


def test_edit_and_delete_text_note_by_id(tmp_path):
    import pytest

    pikepdf = pytest.importorskip("pikepdf")
    from app.actions.annotate import (
        add_annotation,
        load_annotations,
        _delete_note_by_id,
        _update_note_content_by_id,
    )

    out = tmp_path / "edit-delete-note.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    note_id = add_annotation(
        pdf,
        page_idx=0,
        subtype="Text",
        rect=(170, 170, 188, 188),
        content="Original",
    )

    assert _update_note_content_by_id(pdf, note_id=note_id, content="Updated")
    pdf.save(out)
    pdf.close()
    assert load_annotations(str(out))[0]["content"] == "Updated"

    pdf = pikepdf.open(out)
    assert _delete_note_by_id(pdf, note_id=note_id)
    deleted = tmp_path / "edit-delete-note-deleted.pdf"
    pdf.save(deleted)
    pdf.close()
    assert load_annotations(str(deleted)) == []


def test_merge_rects_by_line_normalizes_fragmented_marks():
    from app.actions.annotate import _merge_rects_by_line

    rects = [
        (10.0, 100.0, 25.0, 112.0),
        (26.0, 99.0, 40.0, 113.5),
        (11.0, 80.0, 22.0, 92.0),
    ]

    merged = _merge_rects_by_line(rects)

    assert len(merged) == 2
    assert merged[0][0] == 10.0
    assert merged[0][2] == 40.0
    assert merged[1][0] == 11.0
    assert merged[1][2] == 22.0


def test_delete_mark_annotations_by_ids(tmp_path):
    import pytest

    pikepdf = pytest.importorskip("pikepdf")
    from app.actions.annotate import _add_pdf_annotation, _delete_annotations_by_ids

    out = tmp_path / "marks.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    _add_pdf_annotation(
        pdf,
        page_idx=0,
        subtype="Highlight",
        rects=[(10, 100, 40, 112), (10, 80, 40, 92)],
        color=[1.0, 1.0, 0.0],
        annot_ids=["mark-1", "mark-2"],
    )

    assert _delete_annotations_by_ids(pdf, ["mark-1"]) == 1
    pdf.save(out)
    pdf.close()

    pdf = pikepdf.open(out)
    annots = pdf.pages[0].get("/Annots", [])
    assert len(annots) == 1
    assert str(annots[0].get("/NM")) == "mark-2"
    pdf.close()
