"""Structured data parsers for JSON and CSV formats."""

from __future__ import annotations

import csv
import io
import json

import orjson

from contextcull.ingest.decoder import IngestionResult, clean_char_to_byte_span
from contextcull.ir.models import Block, BlockKind


def is_json(text: str) -> bool:
    """Detects whether text is valid JSON."""
    s = text.strip()
    if not (s.startswith("{") and s.endswith("}")) and not (s.startswith("[") and s.endswith("]")):
        return False
    try:
        orjson.loads(s)
        return True
    except Exception:
        return False


def parse_json_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses JSON data into structured key-value and record blocks."""
    clean_text = ingest.clean_text.strip()
    try:
        data = orjson.loads(clean_text)
    except Exception:
        return []

    blocks: list[Block] = []

    def add_block(text: str, tag: str) -> None:
        idx = ingest.clean_text.find(text)
        if idx != -1:
            span = clean_char_to_byte_span(ingest, idx, idx + len(text))
        else:
            span = clean_char_to_byte_span(ingest, 0, len(ingest.clean_text))
        blocks.append(
            Block(
                block_id=f"block_{len(blocks):04d}_{tag}",
                kind=BlockKind.STRUCTURED,
                sources=(span,),
                text=text,
                metadata={"kind": "rewrite", "format": "json", "tag": tag},
            )
        )

    if isinstance(data, dict):
        for k, v in data.items():
            val_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            add_block(f"{k}: {val_str}", "field")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            val_str = (
                json.dumps(item, ensure_ascii=False)
                if isinstance(item, (dict, list))
                else str(item)
            )
            add_block(f"[{i}] {val_str}", "item")

    return blocks


def is_csv(text: str) -> bool:
    """Detects whether text is a CSV table with multiple consistent rows."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    sample = "\n".join(lines[:10])
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",;\t|")
        reader = csv.reader(io.StringIO(sample), dialect)
        cols = [len(row) for row in reader if row]
        return len(cols) >= 2 and all(c == cols[0] and c > 1 for c in cols)
    except Exception:
        return False


def parse_csv_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses CSV text into table blocks."""
    clean_text = ingest.clean_text.strip()
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(clean_text[:4000], delimiters=",;\t|")
        reader = list(csv.reader(io.StringIO(clean_text), dialect))
    except Exception:
        return []

    if not reader:
        return []

    # Emit verbatim source slices (kind "copy") so rows keep their original bytes and
    # compiled output is never longer than the input.
    text = ingest.clean_text
    line_spans: list[tuple[int, int]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        if body.strip():
            line_spans.append((pos, pos + len(body)))
        pos += len(line)
    if not line_spans:
        return []

    def _block(block_id: str, first: int, last: int, meta: dict) -> Block:
        c_start, c_end = line_spans[first][0], line_spans[last][1]
        return Block(
            block_id=block_id,
            kind=BlockKind.TABLE,
            sources=(clean_char_to_byte_span(ingest, c_start, c_end),),
            text=text[c_start:c_end],
            metadata={"kind": "copy", "format": "csv", **meta},
        )

    blocks: list[Block] = [
        _block("block_0000_csv_header", 0, 0, {"role": "header", "columns": reader[0]})
    ]
    # Chunk data lines into logical table blocks of 10 rows
    for chunk_idx, i in enumerate(range(1, len(line_spans), 10)):
        last = min(i + 9, len(line_spans) - 1)
        blocks.append(
            _block(
                f"block_{len(blocks):04d}_csv_rows",
                i,
                last,
                {"chunk": chunk_idx, "row_count": last - i + 1},
            )
        )

    return blocks
