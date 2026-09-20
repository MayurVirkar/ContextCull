"""PDF block parser extracting page-level text, headings, and paragraphs."""

from __future__ import annotations

import io

from pypdf import PdfReader

from tep.ingest.decoder import IngestionResult
from tep.ir.models import Block, BlockKind
from tep.ir.spans import ByteSpan


def is_pdf(raw_bytes: bytes) -> bool:
    """Detects whether raw bytes represent a PDF file."""
    return raw_bytes.startswith(b"%PDF-")


def parse_pdf_blocks(ingest: IngestionResult) -> list[Block]:
    """Extracts text blocks from a PDF document page by page."""
    raw_bytes = ingest.source_map.raw_bytes
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
    except Exception:
        return []

    blocks: list[Block] = []
    file_span = ByteSpan(ingest.document_id, 0, len(raw_bytes))

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
                        blocks.append(
                            Block(
                                block_id=f"block_{len(blocks):04d}_{'heading' if is_heading else 'prose'}",
                                kind=BlockKind.HEADING if is_heading else BlockKind.PROSE,
                                sources=(file_span,),
                                text=para,
                                metadata={"kind": "rewrite", "page": page_num + 1},
                            )
                        )
                    curr_paras = []
            else:
                curr_paras.append(line_str)

        if curr_paras:
            para = " ".join(curr_paras)
            if para:
                is_heading = len(para) < 80 and (para.isupper() or para.istitle())
                blocks.append(
                    Block(
                        block_id=f"block_{len(blocks):04d}_{'heading' if is_heading else 'prose'}",
                        kind=BlockKind.HEADING if is_heading else BlockKind.PROSE,
                        sources=(file_span,),
                        text=para,
                        metadata={"kind": "rewrite", "page": page_num + 1},
                    )
                )

    return blocks
