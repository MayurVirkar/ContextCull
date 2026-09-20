"""Block router with confidence scoring and opaque fallback."""

from __future__ import annotations

import logging

from tep.ingest.decoder import IngestionResult, clean_char_to_byte_span
from tep.ir.models import Block, BlockKind
from tep.parse.code import is_code_input, parse_code_blocks
from tep.parse.docx import is_docx, parse_docx_blocks
from tep.parse.email import is_email, parse_email_blocks
from tep.parse.html import is_html, parse_html_blocks
from tep.parse.logs import is_test_log, parse_test_log_blocks
from tep.parse.markdown import parse_markdown_blocks
from tep.parse.pdf import is_pdf, parse_pdf_blocks
from tep.parse.structured import is_csv, is_json, parse_csv_blocks, parse_json_blocks
from tep.parse.text import parse_plain_text_blocks
from tep.parse.xml import is_xml, parse_xml_blocks

logger = logging.getLogger(__name__)


def route_and_parse(ingest: IngestionResult) -> list[Block]:
    """Routes an ingested document to appropriate block parsers and returns structured blocks.

    Guarantees:
    - In the event of parser error or empty extraction, falls back safely to an OPAQUE block.
    """
    clean_text = ingest.clean_text.strip()
    if not clean_text:
        return []

    raw_bytes = ingest.source_map.raw_bytes

    try:
        # 1. Binary formats
        if is_pdf(raw_bytes):
            blocks = parse_pdf_blocks(ingest)
            if blocks:
                return blocks

        if is_docx(raw_bytes):
            blocks = parse_docx_blocks(ingest)
            if blocks:
                return blocks

        # 2. Markup and Structured formats
        if is_html(clean_text):
            blocks = parse_html_blocks(ingest)
            if blocks:
                return blocks

        if is_xml(clean_text):
            blocks = parse_xml_blocks(ingest)
            if blocks:
                return blocks

        if is_json(clean_text):
            blocks = parse_json_blocks(ingest)
            if blocks:
                return blocks

        if is_csv(clean_text):
            blocks = parse_csv_blocks(ingest)
            if blocks:
                return blocks

        # 3. Test runner logs
        if is_test_log(clean_text):
            blocks = parse_test_log_blocks(ingest)
            if blocks:
                return blocks

        # 4. Source code / test cases
        if is_code_input(clean_text):
            blocks = parse_code_blocks(ingest)
            if blocks:
                return blocks

        # 5. RFC email
        if is_email(clean_text):
            blocks = parse_email_blocks(ingest)
            if blocks:
                return blocks

        # 6. Markdown
        if "#" in clean_text or "```" in clean_text or "|" in clean_text or "- " in clean_text:
            blocks = parse_markdown_blocks(ingest)
            if blocks:
                return blocks

        # 7. Plain text
        blocks = parse_plain_text_blocks(ingest)
        if blocks:
            return blocks

    except Exception as exc:
        logger.warning("Parser error during block routing: %s", exc)

    # Safe Opaque Fallback
    span = clean_char_to_byte_span(ingest, 0, len(ingest.clean_text))
    return [
        Block(
            block_id="block_0000_opaque",
            kind=BlockKind.OPAQUE,
            sources=(span,),
            text=ingest.clean_text.strip(),
        )
    ]
