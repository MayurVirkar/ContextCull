"""Unit tests for SourceMap and ByteSpan exact provenance mapping."""

from contextcull.ingest.decoder import clean_char_to_byte_span, ingest_bytes
from contextcull.ir.spans import ByteSpan, SourceMap


def test_sourcemap_ascii():
    raw = b"Hello, world! 12345"
    smap = SourceMap.from_bytes(raw, document_id="doc1")
    assert smap.decoded_text == "Hello, world! 12345"

    span = smap.char_to_byte_span(0, 5)
    assert span.start == 0
    assert span.end == 5
    assert span.slice_bytes(raw) == b"Hello"
    assert smap.slice_source(span) == "Hello"


def test_sourcemap_multibyte_utf8():
    # '∵' is 3 bytes: e2 88 b5
    # '¬' is 2 bytes: c2 ac
    # '🚀' is 4 bytes: f0 9f 9a 80
    raw = "Logic: ∵ test ¬ valid 🚀 done".encode()
    smap = SourceMap.from_bytes(raw, document_id="doc2")

    # Locate '∵'
    char_idx = smap.decoded_text.index("∵")
    span = smap.char_to_byte_span(char_idx, char_idx + 1)
    assert span.length == 3
    assert span.slice_bytes(raw) == "∵".encode()
    assert smap.slice_source(span) == "∵"

    # Locate '🚀'
    rocket_idx = smap.decoded_text.index("🚀")
    span_rocket = smap.char_to_byte_span(rocket_idx, rocket_idx + 1)
    assert span_rocket.length == 4
    assert span_rocket.slice_bytes(raw) == "🚀".encode()
    assert smap.slice_source(span_rocket) == "🚀"


def test_sourcemap_ansi_escapes():
    raw = b"Running \x1b[32mtests\x1b[0m ... \x1b[31mFAILED\x1b[0m"
    ingest = ingest_bytes(raw)

    assert ingest.clean_text == "Running tests ... FAILED"

    # Map 'FAILED' from clean text back to raw bytes
    start_c = ingest.clean_text.index("FAILED")
    end_c = start_c + len("FAILED")

    byte_span = clean_char_to_byte_span(ingest, start_c, end_c)
    assert byte_span.slice_bytes(raw) == b"FAILED"


def test_bytespan_overlap_and_contains():
    span1 = ByteSpan(document_id="doc1", start=10, end=20)
    span2 = ByteSpan(document_id="doc1", start=15, end=25)
    span3 = ByteSpan(document_id="doc1", start=12, end=18)
    span4 = ByteSpan(document_id="doc1", start=30, end=40)

    assert span1.overlaps(span2)
    assert span1.contains(span3)
    assert not span1.overlaps(span4)
