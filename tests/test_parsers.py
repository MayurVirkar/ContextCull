"""Comprehensive tests for all format parsers (HTML, XML, DOCX, PDF, JSON, CSV)."""

from __future__ import annotations

import io
import zipfile

from pypdf import PdfWriter

from tep.api import ContextCompiler
from tep.ingest.decoder import ingest_bytes
from tep.ir.models import BlockKind, CompileMode
from tep.parse.docx import is_docx
from tep.parse.html import is_html
from tep.parse.pdf import is_pdf
from tep.parse.structured import is_csv, is_json
from tep.parse.xml import is_xml
from tep.route.router import route_and_parse


def test_html_parser():
    html_content = b"""<!DOCTYPE html>
    <html>
    <head><title>System Architecture</title><script>var secret = "1.2.3.4";</script></head>
    <body>
        <h1>Cluster Setup CVE-2026-1111</h1>
        <p>The cluster contains 10 nodes running on Ubuntu.</p>
        <ul>
            <li>Node 1: Master</li>
            <li>Node 2: Worker</li>
        </ul>
    </body>
    </html>"""

    ingest = ingest_bytes(html_content)
    assert is_html(ingest.clean_text)
    blocks = route_and_parse(ingest)

    assert len(blocks) >= 3
    kinds = [b.kind for b in blocks]
    assert BlockKind.HEADING in kinds
    assert BlockKind.PROSE in kinds
    assert BlockKind.LIST in kinds

    # Verify script content was excluded
    assert not any("secret" in b.text for b in blocks)

    # End-to-end compilation
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    res = compiler.compile(html_content)
    assert res.ok
    assert "CVE-2026-1111" in res.text


def test_xml_parser():
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <incident id="INC-999">
        <title>Database Outage</title>
        <description>Service 10.20.30.40 became unreachable due to OOM.</description>
        <resolution>Rebooted instance i-0abcdef1234567890.</resolution>
    </incident>"""

    ingest = ingest_bytes(xml_content)
    assert is_xml(ingest.clean_text)
    blocks = route_and_parse(ingest)

    assert len(blocks) >= 3
    assert any(b.kind == BlockKind.STRUCTURED for b in blocks)

    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    res = compiler.compile(xml_content)
    assert res.ok
    assert "10.20.30.40" in res.text
    assert "i-0abcdef1234567890" in res.text


def test_docx_parser():
    # Build minimal valid DOCX in-memory
    buf = io.BytesIO()
    doc_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
            <w:p>
                <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
                <w:r><w:t>Executive Summary</w:t></w:r>
            </w:p>
            <w:p>
                <w:r><w:t>The security audit identified CVE-2026-5555 in deployment.</w:t></w:r>
            </w:p>
        </w:body>
    </w:document>"""

    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc_xml)
        z.writestr("[Content_Types].xml", b"<Types/>")

    docx_bytes = buf.getvalue()
    assert is_docx(docx_bytes)

    ingest = ingest_bytes(docx_bytes)
    blocks = route_and_parse(ingest)
    assert len(blocks) == 2
    assert blocks[0].kind == BlockKind.HEADING
    assert blocks[1].kind == BlockKind.PROSE
    assert "CVE-2026-5555" in blocks[1].text

    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    res = compiler.compile(docx_bytes)
    assert res.ok
    assert "CVE-2026-5555" in res.text


def test_pdf_parser():
    # Build a minimal valid PDF in-memory using pypdf
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    assert is_pdf(pdf_bytes)

    ingest = ingest_bytes(pdf_bytes)
    blocks = route_and_parse(ingest)
    assert isinstance(blocks, list)

    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    res = compiler.compile(pdf_bytes)
    assert res.ok


def test_json_parser():
    json_bytes = b"""{
        "service": "auth-gateway",
        "status": "degraded",
        "cve": "CVE-2026-7777",
        "instances": ["i-0123456789abcdef0", "i-0fedcba9876543210"]
    }"""

    ingest = ingest_bytes(json_bytes)
    assert is_json(ingest.clean_text)
    blocks = route_and_parse(ingest)
    assert len(blocks) >= 3

    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    res = compiler.compile(json_bytes)
    assert res.ok
    assert "CVE-2026-7777" in res.text


def test_csv_parser():
    csv_bytes = b"""Timestamp,Host,Status,Error
2026-07-11T10:00:00Z,srv-01,CRITICAL,Out of memory
2026-07-11T10:05:00Z,srv-02,WARNING,High CPU utilization
2026-07-11T10:10:00Z,srv-03,OK,Service recovered"""

    ingest = ingest_bytes(csv_bytes)
    assert is_csv(ingest.clean_text)
    blocks = route_and_parse(ingest)
    assert len(blocks) >= 2
    assert all(b.kind == BlockKind.TABLE for b in blocks)

    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    res = compiler.compile(csv_bytes)
    assert res.ok
    assert "Out of memory" in res.text
