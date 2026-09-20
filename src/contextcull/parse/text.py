"""Plain text and generic prose block parsing."""

from __future__ import annotations

import re

from contextcull.ingest.decoder import IngestionResult, clean_char_to_byte_span
from contextcull.ir.models import Block, BlockKind

PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


def parse_plain_text_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses plain text into paragraph blocks."""
    clean_text = ingest.clean_text
    blocks: list[Block] = []

    start = 0
    for match in PARAGRAPH_SPLIT_RE.finditer(clean_text):
        end = match.start()
        para = clean_text[start:end].strip()
        if para:
            c_start = clean_text.find(para, start)
            c_end = c_start + len(para)
            span = clean_char_to_byte_span(ingest, c_start, c_end)
            blocks.append(
                Block(
                    block_id=f"block_{len(blocks):04d}_prose",
                    kind=BlockKind.PROSE,
                    sources=(span,),
                    text=para,
                )
            )
        start = match.end()

    if start < len(clean_text):
        para = clean_text[start:].strip()
        if para:
            c_start = clean_text.find(para, start)
            c_end = c_start + len(para)
            span = clean_char_to_byte_span(ingest, c_start, c_end)
            blocks.append(
                Block(
                    block_id=f"block_{len(blocks):04d}_prose",
                    kind=BlockKind.PROSE,
                    sources=(span,),
                    text=para,
                )
            )

    return blocks
