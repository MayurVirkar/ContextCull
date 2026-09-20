"""Immutable raw byte ingestion, hashing, and source mapping."""

from __future__ import annotations

import hashlib
import re
from typing import NamedTuple

from tep.errors import TepError
from tep.ir.spans import ByteSpan, SourceMap

# ANSI escape sequence regex pattern
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class IngestionResult(NamedTuple):
    document_id: str
    source_map: SourceMap
    clean_text: str  # ANSI-free text for scoring and regex matching
    # clean_to_decoded_char[i] maps character index in clean_text to character index in source_map.decoded_text
    clean_to_decoded_char: tuple[int, ...]


def ingest_bytes(
    raw_bytes: bytes,
    document_id: str | None = None,
    encoding: str = "utf-8",
    max_bytes: int = 10_000_000,
) -> IngestionResult:
    """Ingests raw bytes, computes a SHA-256 identifier, and builds a lossless SourceMap.

    Does NOT mutate raw bytes or normalize newlines in-place.
    Builds an ANSI-free clean view with exact index mapping back to canonical decoded characters.
    """
    if len(raw_bytes) > max_bytes:
        raise TepError(
            f"Input size {len(raw_bytes)} bytes exceeds maximum permitted size {max_bytes} bytes"
        )

    if document_id is None:
        digest = hashlib.sha256(raw_bytes).hexdigest()
        document_id = f"sha256:{digest}"

    source_map = SourceMap.from_bytes(raw_bytes, document_id=document_id, encoding=encoding)
    decoded = source_map.decoded_text

    # Fast path: if no ANSI sequences are present, clean text is identical to decoded text
    if not ANSI_ESCAPE_RE.search(decoded):
        return IngestionResult(
            document_id=document_id,
            source_map=source_map,
            clean_text=decoded,
            clean_to_decoded_char=tuple(range(len(decoded) + 1)),
        )

    # ANSI stripped view with slice-based character mapping back to decoded characters
    clean_parts: list[str] = []
    clean_to_decoded: list[int] = []

    last_idx = 0
    for match in ANSI_ESCAPE_RE.finditer(decoded):
        start, end = match.span()
        if start > last_idx:
            clean_parts.append(decoded[last_idx:start])
            clean_to_decoded.extend(range(last_idx, start))
        last_idx = end

    if last_idx < len(decoded):
        clean_parts.append(decoded[last_idx:])
        clean_to_decoded.extend(range(last_idx, len(decoded)))

    # Sentinel for end
    clean_to_decoded.append(len(decoded))
    clean_text = "".join(clean_parts)

    return IngestionResult(
        document_id=document_id,
        source_map=source_map,
        clean_text=clean_text,
        clean_to_decoded_char=tuple(clean_to_decoded),
    )


def clean_char_to_byte_span(
    ingest: IngestionResult, clean_start: int, clean_end: int
) -> ByteSpan:
    """Converts character indices in the clean (ANSI-free) view to an exact ByteSpan in original raw bytes."""
    if clean_start < 0 or clean_end > len(ingest.clean_text) or clean_start > clean_end:
        raise ValueError(f"Clean character range [{clean_start}, {clean_end}) is out of bounds")

    if clean_start == clean_end:
        dec_pos = ingest.clean_to_decoded_char[clean_start]
        return ingest.source_map.char_to_byte_span(dec_pos, dec_pos)

    dec_start = ingest.clean_to_decoded_char[clean_start]
    dec_end = ingest.clean_to_decoded_char[clean_end - 1] + 1
    return ingest.source_map.char_to_byte_span(dec_start, dec_end)
