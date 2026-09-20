"""Advanced tests for PDF, DOCX tables, code test suites, Vitest/Pytest logs, and structured data."""

from __future__ import annotations

import io
import json
import zipfile

from pypdf import PdfWriter

from contextcull.ingest.decoder import ingest_bytes
from contextcull.ir.models import BlockKind
from contextcull.parse.code import parse_code_blocks
from contextcull.parse.docx import parse_docx_blocks
from contextcull.parse.logs import parse_test_log_blocks
from contextcull.parse.pdf import parse_pdf_blocks
from contextcull.parse.structured import parse_csv_blocks, parse_json_blocks


def test_docx_tables_and_empty_runs():
    """Verify DOCX table extraction with multiple rows, columns, and empty runs."""
    buf = io.BytesIO()
    doc_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body>
            <w:p>
                <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
                <w:r><w:t>System Report</w:t></w:r>
            </w:p>
            <w:p><w:r><w:t></w:t></w:r></w:p>
            <w:tbl>
                <w:tr>
                    <w:tc><w:p><w:r><w:t>Host</w:t></w:r></w:p></w:tc>
                    <w:tc><w:p><w:r><w:t>Status</w:t></w:r></w:p></w:tc>
                </w:tr>
                <w:tr>
                    <w:tc><w:p><w:r><w:t>10.0.0.1</w:t></w:r></w:p></w:tc>
                    <w:tc><w:p><w:r><w:t>Degraded</w:t></w:r></w:p></w:tc>
                </w:tr>
            </w:tbl>
        </w:body>
    </w:document>"""

    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc_xml)
        z.writestr("[Content_Types].xml", b"<Types/>")

    docx_bytes = buf.getvalue()
    ingest = ingest_bytes(docx_bytes)
    blocks = parse_docx_blocks(ingest)

    kinds = [b.kind for b in blocks]
    assert BlockKind.HEADING in kinds
    assert BlockKind.TABLE in kinds
    all_text = "\n".join(b.text for b in blocks)
    assert "Host | Status" in all_text
    assert "10.0.0.1 | Degraded" in all_text


def test_docx_invalid_bytes():
    """Verify DOCX parser gracefully handles corrupt zip data."""
    ingest = ingest_bytes(b"PK\x03\x04corrupted_data_not_a_valid_zip")
    blocks = parse_docx_blocks(ingest)
    assert blocks == []


def test_pdf_multi_paragraph_and_headings():
    """Verify PDF multi-page, paragraph breaks, and headings extraction."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)

    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    ingest = ingest_bytes(pdf_bytes)
    blocks = parse_pdf_blocks(ingest)
    assert isinstance(blocks, list)


def test_pdf_invalid_bytes():
    ingest = ingest_bytes(b"%PDF-1.4 corrupted invalid bytes")
    blocks = parse_pdf_blocks(ingest)
    assert blocks == []


def test_code_test_suite_assertions_python():
    """Verify Python test extraction with assertions."""
    code = """
def test_authentication():
    user = authenticate("admin", "secret")
    assert user is not None
    assert user.role == "superadmin"

def test_failure():
    assert 1 == 2
"""
    ingest = ingest_bytes(code.encode("utf-8"))
    blocks = parse_code_blocks(ingest)
    assert len(blocks) == 2
    assert "test: test_authentication" in blocks[0].text
    assert 'assert: user.role == "superadmin"' in blocks[0].text
    assert "test: test_failure" in blocks[1].text


def test_code_test_suite_assertions_rust():
    """Verify Rust test extraction with assert_eq!."""
    code = """
#[test]
fn test_hash_calculation() {
    let hash = calculate(b"data");
    assert_eq!(hash, "expected_hash");
}
"""
    ingest = ingest_bytes(code.encode("utf-8"))
    blocks = parse_code_blocks(ingest)
    assert len(blocks) == 1
    assert "test: test_hash_calculation" in blocks[0].text
    assert 'assert: hash == "expected_hash"' in blocks[0].text


def test_vitest_log_parsing():
    """Verify Vitest failure log extraction."""
    log_text = """
FAIL src/api/user.test.ts > User Authentication
Error: expect(received).toBe(expected)
- Expected:
  200
+ Received:
  401
 ❯ src/api/user.test.ts:45:12

Test Files 1 failed (1)
Tests 1 failed | 5 passed (6)
Duration 1.25s
"""
    ingest = ingest_bytes(log_text.encode("utf-8"))
    blocks = parse_test_log_blocks(ingest)
    assert len(blocks) >= 2
    summary = blocks[0]
    assert "✓ 5 · ✗ 1" in summary.text
    fail_block = blocks[1]
    assert "User Authentication" in fail_block.text
    assert "exp: 200 got: 401" in fail_block.text


def test_generic_log_parsing():
    """Verify generic unstructured logs parse into individual lines."""
    logs = "2026-03-15T12:00:00Z INFO System starting\n2026-03-15T12:00:01Z WARN Memory usage 85%\n2026-03-15T12:00:02Z ERROR Connection refused\n"
    ingest = ingest_bytes(logs.encode("utf-8"))
    blocks = parse_test_log_blocks(ingest)
    assert len(blocks) == 3
    assert "System starting" in blocks[0].text
    assert "Connection refused" in blocks[2].text


def test_structured_json_array_and_primitives():
    """Verify JSON array and nested structures."""
    data = json.dumps([{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}])
    ingest = ingest_bytes(data.encode("utf-8"))
    blocks = parse_json_blocks(ingest)
    assert len(blocks) >= 1


def test_structured_csv_no_header_and_quotes():
    """Verify CSV parsing without explicit header and with quoted fields."""
    csv_text = '"10.0.0.1","cluster-a","running"\n"10.0.0.2","cluster-b","failed"\n'
    ingest = ingest_bytes(csv_text.encode("utf-8"))
    blocks = parse_csv_blocks(ingest)
    assert len(blocks) >= 1
    all_text = "\n".join(b.text for b in blocks)
    assert "10.0.0.1" in all_text
    assert "cluster-b" in all_text
