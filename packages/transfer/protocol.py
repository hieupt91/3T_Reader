from __future__ import annotations

"""Giao thức manifest/chunk/hash truyền qua RTCDataChannel — theo đúng thiết
kế trong docs/SPEC_MOBILE_SCANDOC_TRANSFER.md mục 5, để 3TReader desktop và
ScanDoc mobile khớp format với nhau. KHÔNG phụ thuộc aiortc — thuần
serialization, test được độc lập không cần WebRTC thật.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field

CHUNK_SIZE = 64 * 1024  # 64 KiB — khớp SPEC_MOBILE_SCANDOC_TRANSFER.md
_UNSAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def sanitize_file_name(name: str) -> str:
    """Loại ký tự nguy hiểm cho tên file (path traversal, ký tự cấm trên
    Windows/macOS). Không đổi phần mở rộng .pdf."""
    name = name.strip().replace("..", "_")
    name = _UNSAFE_NAME_RE.sub("_", name)
    name = name.lstrip(".")  # tránh file ẩn/tương đối
    return name or "document.pdf"


@dataclass
class Manifest:
    file_name: str
    size: int
    sha256: str
    chunk_size: int = CHUNK_SIZE
    chunk_count: int = 0

    def __post_init__(self) -> None:
        if self.chunk_count == 0 and self.size > 0:
            self.chunk_count = (self.size + self.chunk_size - 1) // self.chunk_size

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": "manifest",
                "file_name": self.file_name,
                "size": self.size,
                "sha256": self.sha256,
                "chunk_size": self.chunk_size,
                "chunk_count": self.chunk_count,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw: str) -> "Manifest":
        data = json.loads(raw)
        if data.get("type") != "manifest":
            raise ValueError("Không phải manifest message.")
        return cls(
            file_name=sanitize_file_name(str(data["file_name"])),
            size=int(data["size"]),
            sha256=str(data["sha256"]).lower(),
            chunk_size=int(data.get("chunk_size", CHUNK_SIZE)),
            chunk_count=int(data.get("chunk_count", 0)),
        )

    @classmethod
    def for_file(cls, file_path: str) -> "Manifest":
        """Tạo manifest từ file thật trên đĩa — tính sha256 + chunk_count."""
        import os

        size = os.path.getsize(file_path)
        digest = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(block)
        return cls(
            file_name=sanitize_file_name(os.path.basename(file_path)),
            size=size,
            sha256=digest.hexdigest(),
        )


def iter_chunks(file_path: str, chunk_size: int = CHUNK_SIZE):
    """Đọc file thành từng chunk nhị phân, mỗi chunk prepend 4-byte
    big-endian index (khớp khuyến nghị SPEC_MOBILE_SCANDOC_TRANSFER.md mục 5.3)."""
    with open(file_path, "rb") as f:
        index = 0
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            yield index.to_bytes(4, "big") + data
            index += 1


def parse_chunk(raw: bytes) -> tuple[int, bytes]:
    if len(raw) < 4:
        raise ValueError("Chunk quá ngắn, thiếu 4-byte index.")
    index = int.from_bytes(raw[:4], "big")
    return index, raw[4:]


@dataclass
class ProgressMessage:
    received_bytes: int
    total_bytes: int

    def to_json(self) -> str:
        return json.dumps(
            {"type": "progress", "received_bytes": self.received_bytes, "total_bytes": self.total_bytes},
            separators=(",", ":"),
        )


@dataclass
class ReceiveAssembler:
    """Ghép các chunk nhận được theo đúng thứ tự index, verify hash cuối cùng."""

    manifest: Manifest
    _buffer: dict[int, bytes] = field(default_factory=dict)
    _received_bytes: int = 0

    def add_chunk(self, raw: bytes) -> None:
        index, data = parse_chunk(raw)
        if index in self._buffer:
            return  # chunk trùng (retransmit hiếm gặp trên reliable channel) — bỏ qua
        self._buffer[index] = data
        self._received_bytes += len(data)

    @property
    def received_bytes(self) -> int:
        return self._received_bytes

    @property
    def is_complete(self) -> bool:
        return len(self._buffer) == self.manifest.chunk_count

    def assemble_and_verify(self) -> bytes:
        if not self.is_complete:
            raise ValueError(
                f"Thiếu chunk: nhận {len(self._buffer)}/{self.manifest.chunk_count}."
            )
        ordered = b"".join(self._buffer[i] for i in range(self.manifest.chunk_count))
        digest = hashlib.sha256(ordered).hexdigest()
        if digest != self.manifest.sha256:
            raise ValueError(f"Sai hash: nhận {digest}, kỳ vọng {self.manifest.sha256}.")
        return ordered
