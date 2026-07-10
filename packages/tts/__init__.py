"""Text-to-speech package — native macOS `say`/`afplay` backend.

Scope: core read-aloud using the OS `say` command (no external deps,
no voice-pack download). Piper voice sync is a separate, larger feature
and is intentionally NOT handled here.
"""
from .engine import (
    Voice,
    is_available,
    list_voices,
    start_speaking,
    stop_speaking,
)

__all__ = [
    "Voice",
    "is_available",
    "list_voices",
    "start_speaking",
    "stop_speaking",
]
