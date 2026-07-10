"""Native macOS text-to-speech using the `say` command.

Kept intentionally small: no third-party deps, no voice-pack download.
`say` renders and plays directly through the audio device, so a single
subprocess covers synth + playback. The caller keeps the Popen handle to
wait for completion (worker thread) or terminate it (Stop button).
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


def is_available() -> bool:
    """TTS via `say` is only available on macOS."""
    return sys.platform == "darwin"


@dataclass
class Voice:
    name: str
    lang: str

    @property
    def label(self) -> str:
        return f"{self.name} ({self.lang})"


def list_voices() -> list[Voice]:
    """Parse `say -v '?'` into Voice(name, lang). Returns [] if unavailable."""
    if not is_available():
        return []
    try:
        out = subprocess.run(
            ["say", "-v", "?"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []

    voices: list[Voice] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # Line format: "Alex                en_US    # Most people ..."
        # Voice name may contain spaces; the locale token (xx_XX) precedes '#'.
        head = line.split("#", 1)[0].split()
        if len(head) < 2:
            continue
        lang = head[-1]
        name = " ".join(head[:-1])
        voices.append(Voice(name=name, lang=lang))
    return voices


def start_speaking(text: str, voice: str | None = None,
                   rate_wpm: int | None = None) -> subprocess.Popen:
    """Start speaking `text` via `say` (non-blocking).

    Returns the Popen so the caller can wait()/terminate() it.
    Raises RuntimeError on non-macOS platforms.
    """
    if not is_available():
        raise RuntimeError("Đọc văn bản chỉ hỗ trợ trên macOS (dùng lệnh `say`).")
    if not text or not text.strip():
        raise ValueError("Không có văn bản để đọc.")

    cmd = ["say"]
    if voice:
        cmd += ["-v", voice]
    if rate_wpm:
        cmd += ["-r", str(int(rate_wpm))]
    # Pass text via stdin to avoid ARG_MAX limits on long pages.
    cmd += ["-f", "-"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    return proc


def stop_speaking(proc: subprocess.Popen | None) -> None:
    """Terminate an in-progress `say` process, if still running."""
    if proc is None:
        return
    if proc.poll() is None:
        try:
            proc.terminate()
        except OSError:
            pass
