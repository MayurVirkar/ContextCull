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

    blocks: list[Block] = []
    header = reader[0]
    header_str = " | ".join(header)
    span = clean_char_to_byte_span(ingest, 0, len(ingest.clean_text))

    # Header block
    blocks.append(
        Block(
            block_id="block_0000_csv_header",
            kind=BlockKind.TABLE,
            sources=(span,),
            text=header_str,
            metadata={"kind": "rewrite", "format": "csv", "role": "header", "columns": header},
        )
    )

    # Chunk rows into logical table blocks of 10 rows
    for chunk_idx, i in enumerate(range(1, len(reader), 10)):
        rows = reader[i : i + 10]
        row_lines = [" | ".join(r) for r in rows]
        blocks.append(
            Block(
                block_id=f"block_{len(blocks):04d}_csv_rows",
                kind=BlockKind.TABLE,
                sources=(span,),
                text="\n".join(row_lines),
                metadata={
                    "kind": "rewrite",
                    "format": "csv",
                    "chunk": chunk_idx,
                    "row_count": len(rows),
                },
            )
        )

    return blocks
