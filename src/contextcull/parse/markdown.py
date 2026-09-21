"""Markdown block parsing and span extraction using markdown-it-py."""

from __future__ import annotations

from markdown_it import MarkdownIt

from contextcull.ingest.decoder import IngestionResult, clean_char_to_byte_span
from contextcull.ir.models import Block, BlockKind
from contextcull.ir.spans import ByteSpan


def parse_markdown_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses markdown text into structural blocks (headings, prose, code fences, tables, lists)."""
    clean_text = ingest.clean_text
    md = MarkdownIt("gfm-like")
    tokens = md.parse(clean_text)

    blocks: list[Block] = []
    lines = clean_text.splitlines(keepends=True)

    # Precalculate line character start offsets
    line_starts: list[int] = [0]
    for line in lines:
        line_starts.append(line_starts[-1] + len(line))

    def line_range_to_chars(start_line: int, end_line: int) -> tuple[int, int]:
        c_start = line_starts[min(start_line, len(line_starts) - 1)]
        c_end = line_starts[min(end_line, len(line_starts) - 1)]
        return c_start, c_end

    def _trimmed_span_and_text(c_start: int, c_end: int) -> tuple[ByteSpan, str] | None:
        raw_segment = clean_text[c_start:c_end]
        stripped = raw_segment.strip()
        if not stripped:
            return None
        leading_ws = len(raw_segment) - len(raw_segment.lstrip())
        trailing_ws = len(raw_segment) - len(raw_segment.rstrip())
        adj_start = c_start + leading_ws
        adj_end = c_end - trailing_ws
        return clean_char_to_byte_span(ingest, adj_start, adj_end), stripped

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.type == "heading_open":
            level = int(token.tag[1:]) if len(token.tag) > 1 and token.tag[1:].isdigit() else 1
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            text = inline.content if inline else ""
            if token.map:
                c_start, c_end = line_range_to_chars(token.map[0], token.map[1])
            else:
                c_start = clean_text.find(text)
                c_end = c_start + len(text)

            res = _trimmed_span_and_text(c_start, c_end)
            if res:
                span, blk_text = res
                blocks.append(
                    Block(
                        block_id=f"block_{len(blocks):04d}_heading",
                        kind=BlockKind.HEADING,
                        sources=(span,),
                        text=blk_text,
                        metadata={"level": level, "heading": text},
                    )
                )
            while i < len(tokens) and tokens[i].type != "heading_close":
                i += 1

        elif token.type in ("fence", "code_block"):
            info = token.info.strip() if token.info else ""
            if token.map:
                c_start, c_end = line_range_to_chars(token.map[0], token.map[1])
            else:
                c_start = clean_text.find(token.content)
                c_end = c_start + len(token.content)

            res = _trimmed_span_and_text(c_start, c_end)
            if res:
                span, blk_text = res
                blocks.append(
                    Block(
                        block_id=f"block_{len(blocks):04d}_code",
                        kind=BlockKind.CODE,
                        sources=(span,),
                        text=blk_text,
                        metadata={"language": info},
                    )
                )

        elif token.type == "paragraph_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            text = inline.content if inline else ""
            if token.map:
                c_start, c_end = line_range_to_chars(token.map[0], token.map[1])
            else:
                c_start = clean_text.find(text)
                c_end = c_start + len(text)

            res = _trimmed_span_and_text(c_start, c_end)
            if res:
                span, blk_text = res
                blocks.append(
                    Block(
                        block_id=f"block_{len(blocks):04d}_prose",
                        kind=BlockKind.PROSE,
                        sources=(span,),
                        text=blk_text,
                    )
                )
            while i < len(tokens) and tokens[i].type != "paragraph_close":
                i += 1

        elif token.type == "table_open":
            if token.map:
                c_start, c_end = line_range_to_chars(token.map[0], token.map[1])
                res = _trimmed_span_and_text(c_start, c_end)
                if res:
                    span, blk_text = res
                    blocks.append(
                        Block(
                            block_id=f"block_{len(blocks):04d}_table",
                            kind=BlockKind.TABLE,
                            sources=(span,),
                            text=blk_text,
                        )
                    )
            while i < len(tokens) and tokens[i].type != "table_close":
                i += 1

        elif token.type in ("bullet_list_open", "ordered_list_open"):
            if token.map:
                c_start, c_end = line_range_to_chars(token.map[0], token.map[1])
                res = _trimmed_span_and_text(c_start, c_end)
                if res:
                    span, blk_text = res
                    blocks.append(
                        Block(
                            block_id=f"block_{len(blocks):04d}_list",
                            kind=BlockKind.LIST,
                            sources=(span,),
                            text=blk_text,
                        )
                    )
            close_type = (
                "bullet_list_close" if token.type == "bullet_list_open" else "ordered_list_close"
            )
            while i < len(tokens) and tokens[i].type != close_type:
                i += 1

        i += 1

    return blocks
