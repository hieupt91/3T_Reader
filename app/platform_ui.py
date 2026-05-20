"""Platform-specific UI helpers for macOS vs Windows/Linux differences."""

import sys

_MACOS = sys.platform == "darwin"


def shortcut_label(keys: str) -> str:
    """Return a human-readable shortcut string for the current OS.

    On macOS 'Ctrl+O' → '⌘O', 'Ctrl+Shift+F' → '⌘⇧F'.
    On Windows/Linux the string is returned unchanged.
    """
    if not _MACOS:
        return keys
    result = keys
    result = result.replace("Ctrl+Shift+", "⌘⇧")
    result = result.replace("Ctrl+", "⌘")
    result = result.replace("Alt+", "⌥")
    result = result.replace("Shift+", "⇧")
    return result


def use_native_menubar() -> bool:
    """True on macOS — menu bar belongs on the system bar, not inside the window."""
    return _MACOS


def fullscreen_shortcut_hint() -> str:
    """OS-appropriate fullscreen shortcut label."""
    return "Ctrl+⌘F" if _MACOS else "F11"
