"""Icon color mappings for dark and light themes.

Centralizes per-icon accent colors so they can be shared across
toolbar, ribbon, and menu without duplicating dicts in window.py.
"""

# Dark theme icon colors
DARK: dict[str, str] = {
    "folder_open.svg":              "#5b9cf6",
    "history.svg":                  "#5b9cf6",
    "save.svg":                     "#4fc080",
    "print.svg":                    "#9090c8",
    "chevron_left.svg":             "#a0a0c0",
    "chevron_right.svg":            "#a0a0c0",
    "zoom_in.svg":                  "#4fc080",
    "zoom_out.svg":                 "#f07858",
    "fit_page.svg":                 "#b060e0",
    "sidebar.svg":                  "#30b8c8",
    "fullscreen.svg":               "#e09040",
    "sun.svg":                      "#f0c050",
    "moon.svg":                     "#6c63ff",
    "brightness_up.svg":            "#f0c050",
    "brightness_down.svg":          "#8090c8",
    "highlight.svg":                "#f0c050",
    "rotate_cw.svg":                "#50b8f0",
    "rotate_ccw.svg":               "#50b8f0",
    "delete_page.svg":              "#e05050",
    "merge_pdf.svg":                "#4fc080",
    "sign_draw.svg":                "#b060e0",
    "extract.svg":                  "#f07858",
    "pen.svg":                      "#2080e0",
    "toolbarButton-editorSignature.svg": "#4fc080",
    "redact.svg":                   "#e05050",
    "trash.svg":                    "#e05050",
    "save_as.svg":                  "#4fc080",
    "insert_text.svg":              "#5b9cf6",
    "insert_image.svg":             "#4fc080",
    "usb.svg":                      "#b060e0",
    "info.svg":                     "#5b9cf6",
    "language.svg":                 "#5b9cf6",
    "signature_check.svg":          "#4fc080",
    "undo.svg":                     "#9090c8",
    "edit_object.svg":              "#5b9cf6",
    "file_plus.svg":                "#4fc080",
    "object_plus.svg":              "#4fc080",
}

# Light theme icon colors — bolder tones for white background
LIGHT: dict[str, str] = {
    "folder_open.svg":              "#1a5cbf",
    "history.svg":                  "#1a5cbf",
    "save.svg":                     "#1a7a40",
    "print.svg":                    "#4a4a8a",
    "chevron_left.svg":             "#505080",
    "chevron_right.svg":            "#505080",
    "zoom_in.svg":                  "#1a7a40",
    "zoom_out.svg":                 "#c04020",
    "fit_page.svg":                 "#7020b0",
    "sidebar.svg":                  "#107090",
    "fullscreen.svg":               "#a05010",
    "sun.svg":                      "#a07800",
    "moon.svg":                     "#3020c0",
    "brightness_up.svg":            "#a07800",
    "brightness_down.svg":          "#4a4a8a",
    "highlight.svg":                "#b08000",
    "rotate_cw.svg":                "#1060b0",
    "rotate_ccw.svg":               "#1060b0",
    "delete_page.svg":              "#b01010",
    "merge_pdf.svg":                "#1a7a40",
    "sign_draw.svg":                "#7020b0",
    "extract.svg":                  "#c04020",
    "pen.svg":                      "#1050b0",
    "toolbarButton-editorSignature.svg": "#1a7a40",
    "redact.svg":                   "#b01010",
    "trash.svg":                    "#b01010",
    "save_as.svg":                  "#1a7a40",
    "insert_text.svg":              "#1a5cbf",
    "insert_image.svg":             "#1a7a40",
    "usb.svg":                      "#7020b0",
    "info.svg":                     "#1a5cbf",
    "language.svg":                 "#1a5cbf",
    "signature_check.svg":          "#1a7a40",
    "undo.svg":                     "#4a4a8a",
    "edit_object.svg":              "#1a5cbf",
    "file_plus.svg":                "#1a7a40",
    "object_plus.svg":              "#1a7a40",
}

# Default fallback color when icon not found in the map
DEFAULT_DARK = "#a0a0c0"
DEFAULT_LIGHT = "#505080"


def get_icon_color(svg_file: str, *, dark: bool) -> str:
    """Return the accent color for *svg_file* in the current theme."""
    table = DARK if dark else LIGHT
    default = DEFAULT_DARK if dark else DEFAULT_LIGHT
    return table.get(svg_file, default)
