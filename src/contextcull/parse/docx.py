"""DOCX (Microsoft Word) block parser extracting paragraphs, headings, and tables from OpenXML."""

from __future__ import annotations

import io
import zipfile

import defusedxml.ElementTree as ET

from contextcull.ingest.decoder import IngestionResult
from contextcull.ir.models import Block, BlockKind
from contextcull.ir.spans import ByteSpan

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_MAP = {"w": W_NS}


def is_docx(raw_bytes: bytes) -> bool:
    """Detects whether raw bytes represent a valid DOCX zip archive."""
    if not raw_bytes.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            return "word/document.xml" in z.namelist()
    except Exception:
        return False


def extract_docx_blocks_and_text(raw_bytes: bytes, document_id: str) -> tuple[list[Block], str]:
    """Extracts paragraphs, headings, and tables from a DOCX document."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            doc_xml = z.read("word/document.xml")
        root = ET.fromstring(doc_xml)
    except Exception:
        return [], ""

    blocks: list[Block] = []
    text_chunks: list[str] = []
    current_byte_offset = 0

    body = root.find("w:body", NS_MAP)
    if body is None:
        return [], ""

    for elem in body:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag == "p":
            text_nodes = elem.findall(".//w:t", NS_MAP)
            text = "".join(t.text or "" for t in text_nodes).strip()
            if not text:
                continue

            p_style = elem.find(".//w:pStyle", NS_MAP)
            style_val = p_style.get(f"{{{W_NS}}}val", "") if p_style is not None else ""
            is_heading = "heading" in style_val.lower() or "title" in style_val.lower()

            text_bytes = text.encode("utf-8")
            span = ByteSpan(
                document_id,
                current_byte_offset,
                current_byte_offset + len(text_bytes),
            )
            blocks.append(
                Block(
                    block_id=f"block_{len(blocks):04d}_{'heading' if is_heading else 'prose'}",
                    kind=BlockKind.HEADING if is_heading else BlockKind.PROSE,
                    sources=(span,),
                    text=text,
                    metadata={"kind": "rewrite", "style": style_val},
                )
            )
            text_chunks.append(text)
            current_byte_offset += len(text_bytes) + 2

        elif tag == "tbl":
            rows: list[list[str]] = []
            for row in elem.findall(".//w:tr", NS_MAP):
                cells: list[str] = []
                for cell in row.findall(".//w:tc", NS_MAP):
                    c_text = "".join(t.text or "" for t in cell.findall(".//w:t", NS_MAP)).strip()
                    cells.append(c_text)
                if any(cells):
                    rows.append(cells)

            if rows:
                table_lines = [" | ".join(r) for r in rows]
                table_text = "\n".join(table_lines)
                tbl_bytes = table_text.encode("utf-8")
                span = ByteSpan(
                    document_id,
                    current_byte_offset,
                    current_byte_offset + len(tbl_bytes),
                )
                blocks.append(
                    Block(
                        block_id=f"block_{len(blocks):04d}_table",
                        kind=BlockKind.TABLE,
                        sources=(span,),
                        text=table_text,
                        metadata={"kind": "rewrite", "rows": len(rows)},
                    )
                )
                text_chunks.append(table_text)
                current_byte_offset += len(tbl_bytes) + 2

    extracted_text = "\n\n".join(text_chunks)
    return blocks, extracted_text


def parse_docx_blocks(ingest: IngestionResult) -> list[Block]:
    """Extracts paragraphs, headings, and tables from a DOCX document."""
    raw_bytes = (
        ingest.raw_file_bytes if ingest.raw_file_bytes is not None else ingest.source_map.raw_bytes
    )
    blocks, _ = extract_docx_blocks_and_text(raw_bytes, ingest.document_id)
    return blocks
