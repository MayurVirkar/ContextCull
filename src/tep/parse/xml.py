"""Secure XML block parser extracting structured elements and text nodes."""

from __future__ import annotations

import re

import defusedxml.ElementTree as ET

from tep.ingest.decoder import IngestionResult, clean_char_to_byte_span
from tep.ir.models import Block, BlockKind

XML_DETECT_RE = re.compile(
    r"^\s*<\?xml\b|^\s*<[a-zA-Z_][a-zA-Z0-9_\-\.:]*(?:\s+[^>]*)?>", re.DOTALL
)


def is_xml(text: str) -> bool:
    """Detects whether text begins with XML declaration or XML root tag."""
    stripped = text[:500].strip()
    return bool(XML_DETECT_RE.match(stripped)) and not stripped.lower().startswith("<!doctype html")


def parse_xml_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses XML into structured blocks, preserving element hierarchy and text."""
    clean_text = ingest.clean_text
    try:
        root = ET.fromstring(clean_text)
    except Exception:
        return []

    blocks: list[Block] = []
    char_pos = 0

    def find_span(content: str) -> tuple[int, int]:
        nonlocal char_pos
        idx = clean_text.find(content, char_pos)
        if idx != -1:
            start_c = idx
            end_c = idx + len(content)
            char_pos = end_c
            return start_c, end_c
        return 0, len(clean_text)

    # Process children
    for elem in root.iter():
        # Tag with text
        text = (elem.text or "").strip()
        if not text:
            continue

        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        start_c, end_c = find_span(text)
        span = clean_char_to_byte_span(ingest, start_c, end_c)

        # Attribute summary if present
        attrs_str = " ".join(f'{k}="{v}"' for k, v in elem.attrib.items())
        block_text = (
            f"<{tag_name} {attrs_str}>{text}</{tag_name}>"
            if attrs_str
            else f"<{tag_name}>{text}</{tag_name}>"
        )

        blocks.append(
            Block(
                block_id=f"block_{len(blocks):04d}_{tag_name}",
                kind=BlockKind.STRUCTURED,
                sources=(span,),
                text=text,
                metadata={"tag": tag_name, "attributes": elem.attrib, "formatted": block_text},
            )
        )

    return blocks
