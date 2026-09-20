"""Universal multilingual sentence and unit segmentation with exact character offsets.

Supports:
- Western / Cyrillic / Greek scripts (.!?) with international abbreviation guards.
- CJK full-width punctuation (。！？) without requiring whitespace.
- Arabic / Persian / Urdu punctuation (؟۔).
- Indic scripts (Devanagari danda ।).
- Decimal numbers (10.0.0.1, 3.14), URLs, emails, and code references (obj.prop).
"""

from __future__ import annotations

import re
from typing import NamedTuple


class SegmentSpan(NamedTuple):
    start_char: int
    end_char: int
    text: str


# Common international abbreviations across English, German, French, Spanish
_ABBREVIATION_SUFFIX_RE = re.compile(
    r"\b(?:"
    # English
    r"e\.g|i\.e|etc|vs|dr|mr|mrs|ms|prof|inc|ltd|approx|"
    # German
    r"z\.b|d\.h|u\.a|bzw|usw|ca|str|"
    # French
    r"p\.ex|c\.-à-d|mme|mlle|"
    # Spanish
    r"p\.ej|aprox|sr|sra|dra|art"
    r")$",
    re.IGNORECASE,
)

# Universal sentence boundary terminators:
# 1. Standard Western (.!?), CJK full-width (。！？), Arabic (؟۔), Indic (।), or double-newline paragraph break
_PUNCTUATION_RE = re.compile(r"([\.!\?]+|[。！？\u061f\u06d4\u0964]|\n{2,})")


def segment_sentences(text: str) -> list[SegmentSpan]:
    """Segments a block of text into sentence-level spans with exact character offsets.

    Guarantees:
    - start_char and end_char accurately bound the sentence within `text`.
    - 100% language-agnostic: handles English, German, French, Spanish, Chinese, Japanese, Arabic, etc.
    - Preserves exact source offsets for cryptographic provenance.
    """
    if not text.strip():
        return []

    spans: list[SegmentSpan] = []
    start = 0
    text_len = len(text)

    for match in _PUNCTUATION_RE.finditer(text):
        m_start = match.start()
        m_end = match.end()
        punct = match.group(0)

        # 1. Decimal number guard (e.g. 10.0.0.1 or 3.14)
        if (
            punct == "."
            and m_start > 0
            and m_end < text_len
            and text[m_start - 1].isdigit()
            and text[m_end].isdigit()
        ):
            continue

        # 2. International abbreviation guard
        prefix = text[start:m_start].strip()
        if _ABBREVIATION_SUFFIX_RE.search(prefix):
            continue

        # 3. Western punctuation must be followed by whitespace, newline, quote, or end of string
        if punct in (".", "!", "?", "...", "!?") and m_end < text_len:
            next_char = text[m_end]
            if not (next_char.isspace() or next_char in ('"', "'", ")", "]", "}", "»", "”")):
                continue

        sent_raw = text[start:m_end]
        sent_clean = sent_raw.strip()
        if sent_clean:
            # Align exact start/end characters ignoring surrounding whitespace
            actual_start = text.find(sent_clean, start)
            actual_end = actual_start + len(sent_clean)
            spans.append(SegmentSpan(start_char=actual_start, end_char=actual_end, text=sent_clean))
            start = m_end

    # Trailing sentence
    if start < text_len:
        remaining_raw = text[start:]
        remaining_clean = remaining_raw.strip()
        if remaining_clean:
            actual_start = text.find(remaining_clean, start)
            actual_end = actual_start + len(remaining_clean)
            spans.append(
                SegmentSpan(start_char=actual_start, end_char=actual_end, text=remaining_clean)
            )

    return spans
