from app.actions._guard import require_document


@require_document()
def prev_page(window):
    cur = window.viewer.get_current_page()
    if cur > 1:
        window.viewer.goto_page(cur - 1)


@require_document()
def next_page(window):
    cur = window.viewer.get_current_page()
    total = window.viewer.get_page_count()
    if cur < total:
        window.viewer.goto_page(cur + 1)


@require_document()
def jump_to_page(window):
    window.viewer.goto_page(window.page_spin.value())