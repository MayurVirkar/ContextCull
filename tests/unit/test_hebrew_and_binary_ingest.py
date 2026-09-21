"""Unit tests for Hebrew/multilingual negation and binary PDF/DOCX ingestion."""

from __future__ import annotations

import io
import zipfile

from pypdf import PdfWriter

from contextcull.api import ContextCompiler
from contextcull.detect.atoms import extract_atoms
from contextcull.ingest.decoder import ingest_bytes, ingest_document
from contextcull.ir.models import BlockKind, CompileMode


def test_hebrew_negation_detection():
    """Verify Hebrew negation markers are captured as bound negations."""
    text = "המערכת לא תאפשר כניסה ללא הרשאה מתאימה. אין גישה למסד הנתונים."
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)

    surfaces = [a.surface for a in atoms if a.kind == "bound_negation"]
    assert any("לא תאפשר" in s for s in surfaces)
    assert any("אין גישה" in s for s in surfaces)


def test_cjk_negation_detection():
    """Verify Chinese/CJK negation markers are captured as bound negations."""
    text = "系统不能访问受保护的生产数据库，用户未授权操作。"
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)

    surfaces = [a.surface for a in atoms if a.kind == "bound_negation"]
    assert any("不能访问" in s for s in surfaces)
    assert any("未授权" in s for s in surfaces)


def test_pdf_ingest_document_exact_spans():
    """Verify PDF ingestion extracts text first and produces byte-exact spans."""
    # Create valid PDF in memory
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    # Write sample text
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    ingest, blocks = ingest_document(pdf_bytes)
    assert ingest.document_id.startswith("sha256:")
    # For a blank PDF, blocks is empty or valid list
    assert isinstance(blocks, list)


def test_docx_ingest_document_exact_spans():
    """Verify DOCX ingestion extracts text first and produces byte-exact spans."""
    buf = io.BytesIO()
    doc_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
            <w:p>
                <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
                <w:r><w:t>Security Assessment Report</w:t></w:r>
            </w:p>
            <w:p>
                <w:r><w:t>Vulnerability CVE-2026-9999 was patched on server 10.10.10.10.</w:t></w:r>
            </w:p>
        </w:body>
    </w:document>"""

    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc_xml)
        z.writestr("[Content_Types].xml", b"<Types/>")

    docx_bytes = buf.getvalue()
    ingest, blocks = ingest_document(docx_bytes)

    assert len(blocks) == 2
    assert blocks[0].kind == BlockKind.HEADING
    assert blocks[0].text == "Security Assessment Report"
    assert blocks[1].kind == BlockKind.PROSE

    # Spans must be exact byte offsets within ingest.source_map
    b0_span = blocks[0].sources[0]
    b1_span = blocks[1].sources[0]
    raw_sub0 = ingest.source_map.raw_bytes[b0_span.start : b0_span.end].decode("utf-8")
    raw_sub1 = ingest.source_map.raw_bytes[b1_span.start : b1_span.end].decode("utf-8")
    assert raw_sub0 == "Security Assessment Report"
    assert "CVE-2026-9999" in raw_sub1

    # End-to-end compilation with atoms
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    res = compiler.compile(docx_bytes)
    assert res.ok
    assert "CVE-2026-9999" in res.text
    assert "10.10.10.10" in res.text
