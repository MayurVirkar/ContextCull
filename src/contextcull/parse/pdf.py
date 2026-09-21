"""PDF block parser extracting page-level text, headings, and paragraphs."""

from __future__ import annotations

import io

from pypdf import PdfReader

from contextcull.ingest.decoder import IngestionResult
from contextcull.ir.models import Block, BlockKind
from contextcull.ir.spans import ByteSpan


def is_pdf(raw_bytes: bytes) -> bool:
    """Detects whether raw bytes represent a PDF file."""
    return raw_bytes.startswith(b"%PDF-")


def extract_pdf_blocks_and_text(raw_bytes: bytes, document_id: str) -> tuple[list[Block], str]:
    """Extracts structured blocks and continuous text from a PDF document."""
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
    except Exception:
        return [], ""

    blocks: list[Block] = []
    text_chunks: list[str] = []
    current_byte_offset = 0

    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            continue

        lines = page_text.splitlines()
        curr_paras: list[str] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                if curr_paras:
                    para = " ".join(curr_paras)
                    if para:
                        is_heading = len(para) < 80 and (para.isupper() or para.istitle())
                        para_bytes = para.encode("utf-8")
                        span = ByteSpan(
                            document_id,
                            current_byte_offset,
                            current_byte_offset + len(para_bytes),
                        )
                        blocks.append(
                            Block(
                                block_id=f"block_{len(blocks):04d}_{'heading' if is_heading else 'prose'}",
                                kind=BlockKind.HEADING if is_heading else BlockKind.PROSE,
                                sources=(span,),
                                text=para,
                                metadata={"kind": "rewrite", "page": page_num + 1},
                            )
                        )
                        text_chunks.append(para)
                        current_byte_offset += len(para_bytes) + 2  # for "\n\n"
                    curr_paras = []
            else:
                curr_paras.append(line_str)

        if curr_paras:
            para = " ".join(curr_paras)
            if para:
                is_heading = len(para) < 80 and (para.isupper() or para.istitle())
                para_bytes = para.encode("utf-8")
                span = ByteSpan(
                    document_id,
                    current_byte_offset,
                    current_byte_offset + len(para_bytes),
                )
                blocks.append(
                    Block(
                        block_id=f"block_{len(blocks):04d}_{'heading' if is_heading else 'prose'}",
                        kind=BlockKind.HEADING if is_heading else BlockKind.PROSE,
                        sources=(span,),
                        text=para,
                        metadata={"kind": "rewrite", "page": page_num + 1},
                    )
                )
                text_chunks.append(para)
                current_byte_offset += len(para_bytes) + 2

    extracted_text = "\n\n".join(text_chunks)
    return blocks, extracted_text


def parse_pdf_blocks(ingest: IngestionResult) -> list[Block]:
    """Extracts text blocks from a PDF document page by page."""
    raw_bytes = (
        ingest.raw_file_bytes if ingest.raw_file_bytes is not None else ingest.source_map.raw_bytes
    )
    blocks, _ = extract_pdf_blocks_and_text(raw_bytes, ingest.document_id)
    return blocks
