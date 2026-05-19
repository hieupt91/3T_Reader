from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateManifest:
    product: str
    platform: str
    channel: str
    version: str
    url: str
    sha256: str
    signature: str
    filename: str = ""
    changelog: str = ""
