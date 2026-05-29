import os


def test_save_and_find_signature_template_by_code(tmp_path, monkeypatch):
    from packages.qt_compat.QtCore import Qt
    from packages.qt_compat.QtGui import QImage
    from app import signature_templates as st

    monkeypatch.setattr(st, "TEMPLATE_DIR", tmp_path)

    pixmap = QImage(32, 32, QImage.Format.Format_ARGB32)
    pixmap.fill(Qt.GlobalColor.transparent)

    saved = st.save_signature_template("ky_mau_01", pixmap)
    assert os.path.exists(saved)

    found = st.find_signature_template("ky_mau_01")
    assert found is not None
    assert found["code"] == "ky_mau_01"
    assert found["path"] == saved


def test_list_signature_templates_includes_code(tmp_path, monkeypatch):
    from packages.qt_compat.QtCore import Qt
    from packages.qt_compat.QtGui import QImage
    from app import signature_templates as st

    monkeypatch.setattr(st, "TEMPLATE_DIR", tmp_path)

    pixmap = QImage(16, 16, QImage.Format.Format_ARGB32)
    pixmap.fill(Qt.GlobalColor.transparent)
    st.save_signature_template("chu_ky_ban_giam_doc", pixmap)

    items = st.list_signature_templates()
    assert items
    assert items[0]["code"] == items[0]["label"]
