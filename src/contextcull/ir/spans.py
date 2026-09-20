"""Byte-level provenance spans, source references, and coordinate translation."""

from __future__ import annotations

import bisect
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ByteSpan:
    """An immutable byte range [start, end) within a specific source document."""

    document_id: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"ByteSpan start must be non-negative, got {self.start}")
        if self.end < self.start:
            raise ValueError(f"ByteSpan end ({self.end}) cannot be less than start ({self.start})")

    @property
    def byte_len(self) -> int:
        return self.end - self.start

    @property
    def length(self) -> int:
        return self.end - self.start

    def slice_bytes(self, raw: bytes) -> bytes:
        return raw[self.start : self.end]

    def overlaps(self, other: ByteSpan) -> bool:
        if self.document_id != other.document_id:
            return False
        return max(self.start, other.start) < min(self.end, other.end)

    def contains(self, other: ByteSpan) -> bool:
        if self.document_id != other.document_id:
            return False
        return self.start <= other.start and other.end <= self.end

    def to_dict(self) -> dict[str, int | str]:
        return {
            "document_id": self.document_id,
            "start": self.start,
            "end": self.end,
        }


# Type alias representing any valid reference to a source span
SourceRef = ByteSpan


@dataclass(frozen=True, slots=True)
class SourceMap:
    """Bidirectional mapping between raw document bytes and decoded character offsets."""

    document_id: str
    raw_bytes: bytes
    decoded_text: str
    # char_to_byte[i] is the byte offset of character i in raw_bytes.
    # char_to_byte[len(decoded_text)] is the byte offset of the end of the text.
    char_to_byte: tuple[int, ...]

    @classmethod
    def from_bytes(cls, raw: bytes, document_id: str, encoding: str = "utf-8") -> SourceMap:
        """Constructs a SourceMap by decoding raw bytes and recording byte offsets per character."""
        text = raw.decode(encoding, errors="replace")

        # Fast code-point based byte length computation for valid UTF-8
        if encoding.lower() in ("utf-8", "utf8") and text.encode("utf-8") == raw:
            n = len(text)
            char_offsets = [0] * (n + 1)
            byte_pos = 0
            for i, char in enumerate(text):
                char_offsets[i] = byte_pos
                code = ord(char)
                if code <= 0x7F:
                    byte_pos += 1
                elif code <= 0x7FF:
                    byte_pos += 2
                elif code <= 0xFFFF:
                    byte_pos += 3
                else:
                    byte_pos += 4
            char_offsets[n] = byte_pos
        else:
            char_offsets = []
            byte_pos = 0
            for char in text:
                char_offsets.append(byte_pos)
                byte_pos += len(char.encode(encoding))
            char_offsets.append(byte_pos)

        return cls(
            document_id=document_id,
            raw_bytes=raw,
            decoded_text=text,
            char_to_byte=tuple(char_offsets),
        )

    def char_to_byte_span(self, char_start: int, char_end: int) -> ByteSpan:
        """Converts character indices in the decoded text into an exact ByteSpan."""
        if char_start < 0 or char_end > len(self.decoded_text) or char_start > char_end:
            raise ValueError(
                f"Character range [{char_start}, {char_end}) is out of bounds for text of length {len(self.decoded_text)}"
            )

        b_start = self.char_to_byte[char_start]
        b_end = self.char_to_byte[char_end]
        return ByteSpan(document_id=self.document_id, start=b_start, end=b_end)

    def byte_to_char_range(self, byte_start: int, byte_end: int) -> tuple[int, int]:
        """Converts raw byte offsets into character indices in the decoded text."""
        if byte_start < 0 or byte_end > len(self.raw_bytes) or byte_start > byte_end:
            raise ValueError(
                f"Byte range [{byte_start}, {byte_end}) is out of bounds for bytes of length {len(self.raw_bytes)}"
            )

        c_start = bisect.bisect_left(self.char_to_byte, byte_start)
        c_end = bisect.bisect_right(self.char_to_byte, byte_end) - 1
        return (c_start, max(c_start, c_end))

    def slice_source(self, span: ByteSpan) -> str:
        """Returns the decoded string corresponding to a ByteSpan."""
        raw_slice = span.slice_bytes(self.raw_bytes)
        return raw_slice.decode("utf-8", errors="replace")
