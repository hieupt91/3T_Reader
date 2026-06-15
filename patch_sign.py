import re
with open('app/actions/sign.py', 'r') as f:
    content = f.read()

content = content.replace("import fitz", "")

target = """    try:
        doc = fitz.open(window.current_path)
        page = doc[page_no - 1]
        page_h = page.rect.height
        left, bottom, right, top_pt = box
        rect = fitz.Rect(left, page_h - top_pt, right, page_h - bottom)
        page.insert_image(rect, filename=sig_img_path, keep_proportion=True)

        tmp_dir2 = _os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
        _os.makedirs(tmp_dir2, exist_ok=True)
        out_path = _os.path.join(tmp_dir2, f"signed_{uuid.uuid4().hex[:8]}.pdf")
        doc.save(out_path)
        doc.close()"""

replacement = """    try:
        tmp_dir2 = _os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
        _os.makedirs(tmp_dir2, exist_ok=True)
        out_path = _os.path.join(tmp_dir2, f"signed_{uuid.uuid4().hex[:8]}.pdf")

        from packages.pdf_engine import get_pdf_engine
        engine = get_pdf_engine()
        ops = [
            {
                "type": "image",
                "page_number": page_no,
                "box": box,
                "image_path": sig_img_path,
            }
        ]
        engine.rebuild_pdf_with_ops(window.current_path, out_path, ops)"""

content = content.replace(target, replacement)

with open('app/actions/sign.py', 'w') as f:
    f.write(content)
