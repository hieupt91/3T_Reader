def build_menubar(window):
    """Build the main menu bar through the window implementation.

    This module is the public menu-construction seam; the large menu body can be
    moved here group-by-group without changing callers.
    """
    return window._build_menubar_impl()
