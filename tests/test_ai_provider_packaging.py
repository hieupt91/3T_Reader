"""H2: Gemini và HuggingFace không hoạt động trong bản đóng gói dù đã khai
trong hiddenimports - xác nhận thực nghiệm bằng build PyInstaller thật (main.py
đầy đủ) rằng chỉ liệt kê tên string trong hiddenimports KHÔNG đủ để 2 package
này lọt vào dist/*/_internal, nhưng collect_all() (đã dùng sẵn cho
pypdfium2/pikepdf/pyhanko...) thì có. Đây là test tĩnh (đọc source/cấu hình),
không rebuild lại toàn app - việc rebuild+verify thật đã làm thủ công khi sửa."""

import inspect

from packages.ai import provider


def test_spec_uses_collect_all_for_google_genai_and_huggingface_hub():
    with open("3T_Reader.spec", encoding="utf-8") as f:
        spec_src = f.read()
    assert "for _package in ('google.genai', 'huggingface_hub'):" in spec_src
    assert "_merge_collected(_package)" in spec_src


def test_pyproject_declares_huggingface_and_google_genai_as_ai_extras():
    with open("pyproject.toml", encoding="utf-8") as f:
        pyproject_src = f.read()
    assert "huggingface_hub" in pyproject_src
    assert "google-genai" in pyproject_src


def test_provider_module_still_imports_both_sdks_lazily_inside_functions():
    """Không đổi cách provider.py dùng 2 SDK này - chỉ đổi cấu hình đóng gói.
    Vẫn phải là lazy import bên trong hàm (thụt lề, không ở top-level), giữ
    nguyên hành vi degrade nếu SDK thiếu ở máy dev không cài optional
    extras."""
    src = inspect.getsource(provider)
    assert "    from huggingface_hub import" in src
    assert "    from google.genai import" in src
    top_level_lines = [ln for ln in src.splitlines() if not ln.startswith((" ", "\t"))]
    assert not any("huggingface_hub" in ln or "google.genai" in ln for ln in top_level_lines)
