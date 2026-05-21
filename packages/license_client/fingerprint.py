from __future__ import annotations

import hashlib
import platform
import socket
import uuid


def get_device_fingerprint() -> str:
    """Return a stable 32-char hex identifier for this machine."""
    parts = [
        hex(uuid.getnode()),
        socket.gethostname(),
        platform.system(),
        platform.machine(),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
