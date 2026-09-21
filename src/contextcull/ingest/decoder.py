"""Immutable raw byte ingestion, hashing, and source mapping."""

from __future__ import annotations

import hashlib
import re
from typing import NamedTuple

from contextcull.errors import InputTooLargeError, UndecodableInputError
from contextcull.ir.spans import ByteSpan, SourceMap

# ANSI escape sequence regex pattern
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# ponytail: heuristic thresholds for BOM-less UTF-16 sniffing, tuned against the
# adversarial fixture corpus. Upgrade to a real charset detector (e.g. charset-normalizer)
# if a real-world corpus starts producing false positives/negatives.
_UTF16_SNIFF_SAMPLE_BYTES = 8000
_UTF16_NUL_RATIO_MIN = 0.15
_UTF16_DOMINANT_RATIO_MIN = 0.6
_UTF16_MINORITY_RATIO_MAX = 0.15


def _detect_bomless_utf16(raw: bytes) -> str | None:
    """Heuristically detects byte-order-mark-less UTF-16 text from the raw byte pattern.

    Plain UTF-8 (and ASCII/Latin-1) text essentially never contains NUL bytes, while
    text that is actually UTF-16 with mostly-BMP content is roughly half NUL bytes,
    concentrated in every other byte position (the high byte of each 16-bit unit for
    ASCII-range characters). Returns "utf-16-le" / "utf-16-be" when confident, the
    sentinel "ambiguous" when the stream looks NUL-heavy but endianness can't be told
    apart, or None when it doesn't look like UTF-16 at all.
    """
    sample = raw[:_UTF16_SNIFF_SAMPLE_BYTES]
    if len(sample) % 2:
        sample = sample[:-1]
    n = len(sample)
    if n < 4:
        return None

    nul_ratio = sample.count(0) / n
    if nul_ratio < _UTF16_NUL_RATIO_MIN:
        return None

    zeros_even = sum(1 for i in range(0, n, 2) if sample[i] == 0)
    zeros_odd = sum(1 for i in range(1, n, 2) if sample[i] == 0)
    even_ratio = zeros_even / max(1, (n + 1) // 2)
    odd_ratio = zeros_odd / max(1, n // 2)

    if even_ratio > _UTF16_DOMINANT_RATIO_MIN and odd_ratio < _UTF16_MINORITY_RATIO_MAX:
        return "utf-16-be"
    if odd_ratio > _UTF16_DOMINANT_RATIO_MIN and even_ratio < _UTF16_MINORITY_RATIO_MAX:
        return "utf-16-le"
    return "ambiguous"


class IngestionResult(NamedTuple):
    document_id: str
    source_map: SourceMap
    clean_text: str  # ANSI-free text for scoring and regex matching
    # clean_to_decoded_char[i] maps character index in clean_text to character index in source_map.decoded_text
    clean_to_decoded_char: tuple[int, ...]
    raw_file_bytes: bytes | None = None


def ingest_bytes(
    raw_bytes: bytes,
    document_id: str | None = None,
    encoding: str = "utf-8",
    max_bytes: int = 10_000_000,
    raw_file_bytes: bytes | None = None,
) -> IngestionResult:
    """Ingests raw bytes, computes a SHA-256 identifier, and builds a lossless SourceMap.

    Does NOT mutate raw bytes or normalize newlines in-place.
    Builds an ANSI-free clean view with exact index mapping back to canonical decoded characters.
    """
    if len(raw_bytes) > max_bytes:
        raise InputTooLargeError(
            f"Input size {len(raw_bytes)} bytes exceeds maximum permitted size {max_bytes} bytes"
        )

    if document_id is None:
        digest = hashlib.sha256(raw_bytes).hexdigest()
        document_id = f"sha256:{digest}"

    if encoding.lower() in ("utf-8", "utf8"):
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            encoding = "utf-8-sig"
        elif raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
            encoding = "utf-16"
        else:
            bomless_utf16 = _detect_bomless_utf16(raw_bytes)
            if bomless_utf16 == "ambiguous":
                raise UndecodableInputError(
                    "Input looks like UTF-16 text without a byte-order mark (heavy, "
                    "evenly-spread NUL bytes), but endianness (LE vs BE) could not be "
                    "determined reliably; refusing to silently mis-decode it as UTF-8"
                )
            elif bomless_utf16 is not None:
                encoding = bomless_utf16
            else:
                try:
                    raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        raw_bytes.decode("latin-1")
                        encoding = "latin-1"
                    except Exception:
                        pass

    source_map = SourceMap.from_bytes(raw_bytes, document_id=document_id, encoding=encoding)
    decoded = source_map.decoded_text

    # Fast path: if no ANSI sequences are present, clean text is identical to decoded text
    if not ANSI_ESCAPE_RE.search(decoded):
        return IngestionResult(
            document_id=document_id,
            source_map=source_map,
            clean_text=decoded,
            clean_to_decoded_char=tuple(range(len(decoded) + 1)),
            raw_file_bytes=raw_file_bytes,
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
        raw_file_bytes=raw_file_bytes,
    )


def clean_char_to_byte_span(ingest: IngestionResult, clean_start: int, clean_end: int) -> ByteSpan:
    """Converts character indices in the clean (ANSI-free) view to an exact ByteSpan in original raw bytes."""
    if clean_start < 0 or clean_end > len(ingest.clean_text) or clean_start > clean_end:
        raise ValueError(f"Clean character range [{clean_start}, {clean_end}) is out of bounds")

    if clean_start == clean_end:
        dec_pos = ingest.clean_to_decoded_char[clean_start]
        return ingest.source_map.char_to_byte_span(dec_pos, dec_pos)

    dec_start = ingest.clean_to_decoded_char[clean_start]
    dec_end = ingest.clean_to_decoded_char[clean_end - 1] + 1
    return ingest.source_map.char_to_byte_span(dec_start, dec_end)


def ingest_document(
    raw_bytes: bytes,
    document_id: str | None = None,
    encoding: str = "utf-8",
    max_bytes: int = 10_000_000,
) -> tuple[IngestionResult, list]:
    """Ingests raw bytes or binary documents (PDF, DOCX) into clean text, SourceMap, and structured blocks."""
    from contextcull.parse.docx import extract_docx_blocks_and_text, is_docx
    from contextcull.parse.pdf import extract_pdf_blocks_and_text, is_pdf
    from contextcull.route.router import route_and_parse

    doc_id = document_id or f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"

    if is_pdf(raw_bytes):
        blocks, extracted_text = extract_pdf_blocks_and_text(raw_bytes, doc_id)
        if extracted_text:
            ingest = ingest_bytes(
                extracted_text.encode("utf-8"),
                document_id=doc_id,
                max_bytes=max_bytes,
                raw_file_bytes=raw_bytes,
            )
            return ingest, blocks

    if is_docx(raw_bytes):
        blocks, extracted_text = extract_docx_blocks_and_text(raw_bytes, doc_id)
        if extracted_text:
            ingest = ingest_bytes(
                extracted_text.encode("utf-8"),
                document_id=doc_id,
                max_bytes=max_bytes,
                raw_file_bytes=raw_bytes,
            )
            return ingest, blocks

    ingest = ingest_bytes(raw_bytes, document_id=doc_id, encoding=encoding, max_bytes=max_bytes)
    blocks = route_and_parse(ingest)
    return ingest, blocks
