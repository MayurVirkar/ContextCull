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

# Cap decompressed word/document.xml size: matches ingest_bytes' default max_bytes ceiling.
# A malicious DOCX can declare a small file but decompress to hundreds of MB (zip bomb);
# check the declared size AND read in bounded chunks so a lying header can't blow memory.
MAX_DOCX_XML_BYTES = 10_000_000
_ZIP_READ_CHUNK = 65_536


def _read_zip_member_bounded(z: zipfile.ZipFile, name: str, max_bytes: int) -> bytes | None:
    """Reads a zip member in bounded chunks, refusing anything over max_bytes.

    Checks the declared (central directory) size first as a cheap rejection, then still
    enforces the cap while streaming, since a crafted zip's declared size can't be trusted.
    """
    info = z.getinfo(name)
    if info.file_size > max_bytes:
        return None

    chunks: list[bytes] = []
    total = 0
    with z.open(name) as f:
        while True:
            chunk = f.read(_ZIP_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                return None
            chunks.append(chunk)
    return b"".join(chunks)


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
            doc_xml = _read_zip_member_bounded(z, "word/document.xml", MAX_DOCX_XML_BYTES)
        if doc_xml is None:
            return [], ""
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
