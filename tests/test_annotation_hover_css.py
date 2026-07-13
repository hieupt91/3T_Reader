from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pdfjs_note_hover_does_not_apply_to_text_mark_annotations():
    css = (ROOT / "assets/css/pdfjs_overrides.css").read_text(encoding="utf-8")

    assert ".annotationLayer section[data-annotation-id]:not(.signatureWidgetAnnotation):hover" not in css
    assert ".annotationLayer .textAnnotation:hover" in css

    for class_name in (
        ".highlightAnnotation",
        ".underlineAnnotation",
        ".strikeoutAnnotation",
        ".squigglyAnnotation",
    ):
        assert class_name in css

    assert ".popupTriggerArea" in css
    assert "pointer-events: none !important;" in css
