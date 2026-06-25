import base64
import os
import tempfile
import uuid

from packages.qt_compat.QtWidgets import QDialog

from app.actions._guard import require_document
from app.dialogs import show_warning


@require_document(show_message=True)
def draw_on_pdf(window):
    from app.actions.edit import _ensure_edit_state, _render_edit_state
    from app.actions.sign import _pick_signature_placement
    from app.signature_pad import DrawOnPdfDialog

    dlg = DrawOnPdfDialog(window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    pixmap = dlg.get_pixmap()
    if pixmap is None:
        return

    if hasattr(window, "status"):
        window.status.showMessage("Vừa vẽ xong, giờ chọn vùng chèn trên PDF... (Esc để hủy)", 0)

    edit_dir = os.path.join(tempfile.gettempdir(), "reader_pdf_edit")
    os.makedirs(edit_dir, exist_ok=True)
    img_path = os.path.join(edit_dir, f"draw_{uuid.uuid4().hex[:8]}.png")
    pixmap.save(img_path, "PNG")

    try:
        with open(img_path, "rb") as handle:
            raw = handle.read()
        data_url = f"data:image/png;base64,{base64.b64encode(raw).decode()}"
    except Exception:
        data_url = ""

    placement = _pick_signature_placement(window, sig_image_url=data_url)

    if hasattr(window, "status"):
        window.status.showMessage("", 0)

    if not placement or "box" not in placement or "page_number" not in placement:
        return

    state = _ensure_edit_state(window)
    if not state:
        show_warning(window, "Không thể chỉnh sửa", "Thiếu file làm việc để chèn nội dung vẽ.")
        return

    page_number = int(placement["page_number"])
    left, bottom, right, top = placement["box"]

    op = {
        "id": state["next_id"],
        "type": "image",
        "page_number": page_number,
        "box": (left, bottom, right, top),
        "image_path": img_path,
        "image_data_url": data_url,
    }
    state["next_id"] += 1
    state["ops"].append(op)
    _render_edit_state(window, state, "Đã vẽ lên PDF", focus_page=page_number)
