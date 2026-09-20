"""Property-based tests for SourceMap byte-level accuracy using Hypothesis."""

from hypothesis import given
from hypothesis import strategies as st

from tep.ir.spans import SourceMap


@given(st.text(min_size=1, max_size=1000))
def test_property_sourcemap_slice_roundtrip(text: str):
    raw = text.encode("utf-8")
    smap = SourceMap.from_bytes(raw, document_id="prop_doc")

    assert smap.decoded_text == text

    # Test random slices within text
    n = len(text)
    for start in range(0, min(n, 20), 5):
        for end in range(start, min(n, start + 30), 7):
            span = smap.char_to_byte_span(start, end)
            expected_slice = text[start:end].encode("utf-8")
            assert span.slice_bytes(raw) == expected_slice
            assert smap.slice_source(span) == text[start:end]
