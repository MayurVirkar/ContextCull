"""Regression tests for: UTF-16/encoding-aware provenance, honest PDF/DOCX manifest
provenance, zip-bomb/PDF extraction guards, and exact (not substring-anywhere) copy
segment verification.

See task PROBLEMS 1, 2, 3, 5. Item 4 (compile() returning a status instead of raising
on oversize input) lives in api.py, which is owned by another agent; this file covers
what the API needs (InputTooLargeError/UndecodableInputError) without editing api.py.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from typer.testing import CliRunner

from contextcull.cli import app
from contextcull.errors import InputTooLargeError, UndecodableInputError
from contextcull.ingest.decoder import _detect_bomless_utf16, ingest_bytes
from contextcull.ir.models import OutputSegment
from contextcull.ir.spans import ByteSpan
from contextcull.parse import pdf as pdf_mod
from contextcull.tokenize.profile import get_tokenizer
from contextcull.validate.invariants import validate_invariants

runner = CliRunner()

SAMPLE_TEXT = (
    "Hello World. This is a test sentence with CVE-2026-1234 in it for testing purposes today."
)

# =========================================================================
# Problem 1: UTF-16 (and other) encoding-aware ingestion + provenance
# =========================================================================


@pytest.mark.parametrize(
    "codec,make_bytes",
    [
        ("utf-8", lambda t: t.encode("utf-8")),
        ("utf-8-sig", lambda t: t.encode("utf-8-sig")),
        ("utf-16-le-bom", lambda t: t.encode("utf-16")),  # little-endian BOM on this platform
        ("utf-16-be-bom", lambda t: b"\xfe\xff" + t.encode("utf-16-be")),
        ("latin-1", lambda t: t.encode("latin-1")),
    ],
)
def test_copy_segment_source_bytes_decode_to_emitted_text_exactly(codec, make_bytes):
    """Every copy segment's source bytes, decoded with the DOCUMENT's own encoding, must
    equal the emitted text exactly -- for utf-8, utf-8-sig, utf-16 (both BOMs), latin-1."""
    text = "Cafe report" if codec == "latin-1" else SAMPLE_TEXT
    raw = make_bytes(text)

    ingest = ingest_bytes(raw)
    span = ingest.source_map.char_to_byte_span(0, len(ingest.source_map.decoded_text))

    # Sanity: decoding the full raw span with the document's own encoding reproduces
    # the exact text (this is the "silent total loss"/wrong-codec bug surface).
    decoded = ingest.source_map.raw_bytes[span.start : span.end].decode(
        ingest.source_map.encoding, errors="strict"
    )
    assert decoded == text

    seg = OutputSegment(
        output_start=0,
        output_end=len(text.encode("utf-8")),
        kind="copy",
        sources=(span,),
        text=text,
    )
    tokenizer = get_tokenizer("openai:cl100k_base")

    # Must NOT raise: this is exactly the INVARIANT_FAILED bug for UTF-16 BOM input,
    # caused by validate_invariants previously hardcoding a UTF-8 decode of the span.
    validate_invariants(
        output_text=text,
        output_segments=[seg],
        raw_source_bytes=ingest.source_map.raw_bytes,
        required_atoms=[],
        tokenizer=tokenizer,
        source_encoding=ingest.source_map.encoding,
    )


def test_utf16_bom_sourcemap_stores_concrete_codec_not_bom_sniffing_alias():
    ingest_le = ingest_bytes(SAMPLE_TEXT.encode("utf-16"))
    assert ingest_le.source_map.encoding == "utf-16-le"

    ingest_be = ingest_bytes(b"\xfe\xff" + SAMPLE_TEXT.encode("utf-16-be"))
    assert ingest_be.source_map.encoding == "utf-16-be"


def test_bomless_utf16_detected_instead_of_silently_emptied():
    """Previously: BOM-less UTF-16 decoded as UTF-8 with errors='replace' silently
    "succeeded" but produced text so mangled that the pipeline dropped everything,
    yielding status OK with EMPTY output -- silent total data loss."""
    raw_le = SAMPLE_TEXT.encode("utf-16-le")
    ingest_le = ingest_bytes(raw_le)
    assert ingest_le.clean_text == SAMPLE_TEXT
    assert ingest_le.source_map.encoding == "utf-16-le"

    raw_be = SAMPLE_TEXT.encode("utf-16-be")
    ingest_be = ingest_bytes(raw_be)
    assert ingest_be.clean_text == SAMPLE_TEXT
    assert ingest_be.source_map.encoding == "utf-16-be"


def test_bomless_utf16_ambiguous_endianness_raises_clear_error():
    """When the byte stream is NUL-heavy like UTF-16 but LE vs BE can't be told apart,
    ingest must fail loudly rather than silently guess and risk mangled/empty output."""
    # Alternating non-zero bytes on BOTH channels with heavy NULs interspersed evenly:
    # neither the even nor the odd byte-position is dominantly zero.
    raw = bytes([0x41, 0x00, 0x00, 0x42] * 50)
    assert _detect_bomless_utf16(raw) == "ambiguous"

    with pytest.raises(UndecodableInputError):
        ingest_bytes(raw)


def test_oversize_input_raises_input_too_large_error_not_generic():
    with pytest.raises(InputTooLargeError) as exc_info:
        ingest_bytes(b"X" * 100, max_bytes=10)
    assert exc_info.value.status == "INPUT_TOO_LARGE"


# =========================================================================
# Problem 5: exact per-segment equality is the primary copy-provenance check
# =========================================================================


def test_invariants_catch_wrong_span_even_when_text_appears_elsewhere():
    """A segment whose declared source span does NOT match its own text must be flagged,
    even if that (wrong) text happens to also appear elsewhere in the output -- the old
    'span_str not in clean_output' anywhere-substring check could miss this."""
    source = b"AAA BBB AAA"
    output_text = "AAA BBB AAA"
    # Segment claims text "AAA" came from span [4:7) which is actually "BBB".
    seg = OutputSegment(
        output_start=0,
        output_end=3,
        kind="copy",
        sources=(ByteSpan("doc", 4, 7),),
        text="AAA",
    )
    tokenizer = get_tokenizer("openai:cl100k_base")

    with pytest.raises(Exception, match="Provenance violation"):
        validate_invariants(
            output_text=output_text,
            output_segments=[seg],
            raw_source_bytes=source,
            required_atoms=[],
            tokenizer=tokenizer,
        )


# =========================================================================
# Problem 2: honest PDF/DOCX manifest provenance
# =========================================================================

DOCX_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    b"<w:body><w:p><w:r><w:t>Vulnerability CVE-2026-9999 was patched on server "
    b"10.10.10.10 during the scheduled maintenance window.</w:t></w:r></w:p></w:body>"
    b"</w:document>"
)


def _make_docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", DOCX_XML)
        z.writestr("[Content_Types].xml", b"<Types/>")
    return buf.getvalue()


def test_manifest_records_honest_span_basis_for_docx():
    from contextcull.api import ContextCompiler

    docx_bytes = _make_docx_bytes()
    result = ContextCompiler().compile(docx_bytes)
    assert result.ok
    source = result.manifest["source"]
    assert source["format"] == "docx"
    assert source["span_basis"] == "extracted_text"
    assert source["extracted_text_sha256"].startswith("sha256:")


def test_manifest_records_raw_bytes_basis_for_plain_text():
    from contextcull.api import ContextCompiler

    result = ContextCompiler().compile(SAMPLE_TEXT.encode("utf-8"))
    assert result.ok
    source = result.manifest["source"]
    assert source["format"] == "text"
    assert source["span_basis"] == "raw_bytes"
    assert "extracted_text_sha256" not in source


def test_cli_validate_docx_reports_honest_bounds_checked_message(tmp_path):
    from contextcull.api import ContextCompiler

    docx_bytes = _make_docx_bytes()
    docx_path = tmp_path / "sample.docx"
    docx_path.write_bytes(docx_bytes)

    result = ContextCompiler().compile(docx_bytes)
    assert result.ok
    out_path = tmp_path / "out.txt"
    manifest_path = tmp_path / "manifest.json"
    result.write_text(str(out_path))
    result.write_manifest(str(manifest_path))

    cli_result = runner.invoke(
        app,
        ["validate", str(out_path), "--manifest", str(manifest_path), "--source", str(docx_path)],
    )
    assert cli_result.exit_code == 0, cli_result.output
    # Must NOT claim byte-exact provenance it never checked, and must say bounds-checked
    # rewrite segments were NOT byte-verified.
    assert "NOT byte-verified" in cli_result.output
    assert "0 copy segment(s) byte-verified" in cli_result.output
    assert "bounds-checked" in cli_result.output


def test_cli_validate_zero_verified_segments_warns_and_exits_nonzero(tmp_path):
    import hashlib

    import orjson

    source_path = tmp_path / "src.txt"
    source_path.write_bytes(b"hello")
    context_path = tmp_path / "out.txt"
    context_path.write_text("hello")
    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "source": {
            "document_id": f"sha256:{hashlib.sha256(b'hello').hexdigest()}",
            "span_basis": "raw_bytes",
        },
        "output_segments": [],
    }
    manifest_path.write_bytes(orjson.dumps(manifest))

    cli_result = runner.invoke(
        app,
        [
            "validate",
            str(context_path),
            "--manifest",
            str(manifest_path),
            "--source",
            str(source_path),
        ],
    )
    assert cli_result.exit_code == 3
    assert "WARNING" in cli_result.output

    cli_result_allowed = runner.invoke(
        app,
        [
            "validate",
            str(context_path),
            "--manifest",
            str(manifest_path),
            "--source",
            str(source_path),
            "--allow-unverified",
        ],
    )
    assert cli_result_allowed.exit_code == 0


# =========================================================================
# Problem 3: DOCX zip-bomb guard and PDF page/char caps
# =========================================================================


def test_docx_zip_bomb_rejected_without_reading_full_payload():
    from contextcull.parse.docx import extract_docx_blocks_and_text

    # ~55MB decompressed from a small paragraph repeated many times (highly compressible).
    paragraph = b"<w:p><w:r><w:t>AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA</w:t></w:r></w:p>"
    big_xml = (
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b"<w:body>" + paragraph * 900_000 + b"</w:body></w:document>"
    )
    assert len(big_xml) > 50_000_000

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", big_xml)
        z.writestr("[Content_Types].xml", b"<Types/>")

    blocks, text = extract_docx_blocks_and_text(buf.getvalue(), "doc1")
    assert blocks == []
    assert text == ""


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    """Stand-in for pypdf.PdfReader so the page/char cap logic can be tested without
    needing to synthesize a real multi-page PDF with extractable text."""

    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages


def test_pdf_extraction_respects_page_cap(monkeypatch):
    from contextcull.parse.pdf import extract_pdf_blocks_and_text

    fake_pages = [_FakePage(f"Page {i} body text.") for i in range(5)]
    monkeypatch.setattr(pdf_mod, "PdfReader", lambda _stream: _FakeReader(fake_pages))
    monkeypatch.setattr(pdf_mod, "MAX_PDF_PAGES", 2)

    blocks, _ = extract_pdf_blocks_and_text(b"dummy-pdf-bytes", "doc1")
    pages_seen = {b.metadata.get("page") for b in blocks}
    assert pages_seen == {1, 2}  # only the first MAX_PDF_PAGES (1-indexed) were processed


def test_pdf_extraction_respects_char_cap(monkeypatch):
    from contextcull.parse.pdf import extract_pdf_blocks_and_text

    # Each page is well under the cap alone, but 3 of them together exceed a small cap.
    fake_pages = [_FakePage("X" * 40) for _ in range(3)]
    monkeypatch.setattr(pdf_mod, "PdfReader", lambda _stream: _FakeReader(fake_pages))
    monkeypatch.setattr(pdf_mod, "MAX_PDF_PAGES", 100)
    monkeypatch.setattr(pdf_mod, "MAX_PDF_EXTRACTED_CHARS", 50)

    blocks, text = extract_pdf_blocks_and_text(b"dummy-pdf-bytes", "doc1")
    assert len(text) <= 50
    assert len(blocks) < 3
