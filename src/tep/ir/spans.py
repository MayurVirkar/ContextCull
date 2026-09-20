"""Span and source location representations for exact provenance tracking."""

from __future__ import annotations

import bisect
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class ByteSpan:
    """Inclusive start, exclusive end offset in the original raw bytes."""

    document_id: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"Invalid byte span: [{self.start}, {self.end})")

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


@dataclass(frozen=True, slots=True)
class PageRegion:
    """Bounding box in a paginated document (e.g. PDF)."""

    document_id: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "document_id": self.document_id,
            "page": self.page,
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
        }


SourceRef = ByteSpan | PageRegion


@dataclass(frozen=True, slots=True)
class SourceMap:
    """Bi-directional mapping between decoded text character offsets and raw byte offsets.

    Preserves exact byte provenance across multi-byte UTF-8 sequences,
    CRLF variations, and non-destructive views.
    """

    document_id: str
    raw_bytes: bytes
    decoded_text: str
    # char_to_byte[i] is the byte offset of character i in raw_bytes.
    # char_to_byte[len(decoded_text)] is the byte offset of the end of the text.
    char_to_byte: tuple[int, ...]

    @classmethod
    def from_bytes(cls, raw: bytes, document_id: str, encoding: str = "utf-8") -> SourceMap:
        """Constructs a SourceMap by decoding raw bytes and recording byte offsets per character."""
        # For standard UTF-8 (and other fixed/variable encodings), we map character index to byte offset
        # efficiently by stepping through code points.
        text = raw.decode(encoding, errors="replace")

        # Build character to byte offset table:
        char_offsets: list[int] = []
        byte_pos = 0

        for char in text:
            char_offsets.append(byte_pos)
            byte_pos += len(char.encode(encoding))

        char_offsets.append(byte_pos)  # End sentinel

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
