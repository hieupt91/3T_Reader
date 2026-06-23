"""PDF existing text/image editor.
Detect existing content in PDF pages for selection and editing.
"""
import fitz  # PyMuPDF

def get_text_spans_on_page(pdf_path: str, page_number: int) -> list[dict]:
    """Return list of text spans with bbox for a page (1-indexed)."""
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    blocks = page.get_text("dict")["blocks"]
    spans = []
    for b in blocks:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                x0, y0, x1, y1 = span["bbox"]
                spans.append({
                    "text": span["text"],
                    "bbox": (x0, y0, x1, y1),  # PDF coords
                    "font": span.get("font", ""),
                    "size": span.get("size", 12),
                    "color": span.get("color", 0),
                })
    doc.close()
    return spans

def get_images_on_page(pdf_path: str, page_number: int) -> list[dict]:
    """Return list of image XObject bboxes."""
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    images = []
    for item in page.get_images(full=True):
        xref = item[0]
        rects = page.get_image_rects(xref)
        for rect in rects:
            images.append({"xref": xref, "bbox": tuple(rect)})
    doc.close()
    return images

def true_redact_area(pdf_path: str, output_path: str, page_number: int, bbox: tuple):
    """Permanently remove content in bbox using PyMuPDF redaction."""
    import os
    import tempfile
    
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    rect = fitz.Rect(*bbox)
    # Expand slightly to guarantee intersection with the text
    rect = rect + (-2, -2, 2, 2)
    page.add_redact_annot(rect, fill=(1,1,1))
    page.apply_redactions(images=2, graphics=2)
    
    if pdf_path == output_path:
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            doc.save(temp_path, garbage=4, deflate=True)
            doc.close()
            os.replace(temp_path, output_path)
        except Exception:
            doc.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
    else:
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
