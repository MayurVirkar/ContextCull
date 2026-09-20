"""Tests for API, invariant validation, PageRank edge cases, and ByteSpan operations."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import scipy.sparse as sp

from contextcull.api import ContextCompiler, summarize
from contextcull.detect.atoms import Atom
from contextcull.detect.language import detect_document_language, detect_sentence_languages
from contextcull.errors import InvariantViolationError
from contextcull.ir.models import CompileMode, OutputSegment, TokenBudget
from contextcull.ir.spans import ByteSpan
from contextcull.rank.pagerank import deterministic_pagerank
from contextcull.tokenize.profile import get_tokenizer
from contextcull.validate.invariants import validate_invariants

CL100K = get_tokenizer("cl100k_base")


# =========================================================================
# 1. Invariant Validation Tests
# =========================================================================


def test_validate_invariants_copied_span_missing():
    """Copy segment referencing source span missing from output raises InvariantViolationError."""
    raw = b"Original text that was supposedly copied."
    span = ByteSpan("doc1", 0, len(raw))
    seg = OutputSegment(output_start=0, output_end=10, kind="copy", sources=(span,))

    with pytest.raises(InvariantViolationError) as exc:
        validate_invariants(
            output_text="Completely different output",
            output_segments=[seg],
            raw_source_bytes=raw,
            required_atoms=[],
            tokenizer=CL100K,
        )
    assert "Provenance violation" in str(exc.value)


def test_validate_invariants_out_of_bounds_span():
    """Rewrite segment with out-of-bounds source span raises InvariantViolationError."""
    raw = b"Short"
    bad_span = ByteSpan("doc1", 0, 100)  # out of bounds (len is 5)
    seg = OutputSegment(output_start=0, output_end=5, kind="rewrite", sources=(bad_span,))

    with pytest.raises(InvariantViolationError) as exc:
        validate_invariants(
            output_text="Short",
            output_segments=[seg],
            raw_source_bytes=raw,
            required_atoms=[],
            tokenizer=CL100K,
        )
    assert "out-of-bounds" in str(exc.value)


def test_validate_invariants_dropped_atom():
    """Required atom missing from output text raises InvariantViolationError."""
    atom = Atom(
        atom_id="a1",
        surface="CVE-2026-0001",
        canonical="CVE-2026-0001",
        kind="cve",
        sources=(),
        required=True,
    )

    with pytest.raises(InvariantViolationError) as exc:
        validate_invariants(
            output_text="No security issues found here.",
            output_segments=[],
            raw_source_bytes=b"raw",
            required_atoms=[atom],
            tokenizer=CL100K,
        )
    assert "Atom violation" in str(exc.value)


def test_validate_invariants_budget_exceeded():
    """Output exceeding hard budget raises InvariantViolationError."""
    budget = TokenBudget(tokens=2, hard_budget=True)
    long_text = "This is definitely more than two tokens."

    with pytest.raises(InvariantViolationError) as exc:
        validate_invariants(
            output_text=long_text,
            output_segments=[],
            raw_source_bytes=b"raw",
            required_atoms=[],
            tokenizer=CL100K,
            budget=budget,
        )
    assert "Budget violation" in str(exc.value)


# =========================================================================
# 2. API & Convenience Functions Tests
# =========================================================================


def test_compiler_from_profile():
    c_strict = ContextCompiler.from_profile("strict")
    assert c_strict.default_mode == CompileMode.STRICT
    c_compact = ContextCompiler.from_profile("compact")
    assert c_compact.default_mode == CompileMode.COMPACT


def test_compiler_compile_file():
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("Server 10.0.0.1 experienced high load on Monday.")
        tmp_path = f.name

    try:
        compiler = ContextCompiler(mode=CompileMode.COMPACT)
        res = compiler.compile_file(tmp_path)
        assert res.ok
        assert "10.0.0.1" in res.text
    finally:
        Path(tmp_path).unlink()


def test_compiler_empty_input():
    compiler = ContextCompiler()
    res = compiler.compile("")
    assert res.ok
    assert res.text == ""
    assert res.manifest["status"] == "EMPTY"


def test_summarize_convenience():
    text = "Incident report: Database cluster 10.0.0.1 failed due to CVE-2026-1111."
    out = summarize(text)
    assert "10.0.0.1" in out
    assert "CVE-2026-1111" in out


def test_compile_result_write_text_and_manifest():
    compiler = ContextCompiler()
    res = compiler.compile("Test content for writing files.")

    with tempfile.TemporaryDirectory() as td:
        out_txt = Path(td) / "out.txt"
        out_json = Path(td) / "out.json"

        res.write_text(str(out_txt))
        res.write_manifest(str(out_json))

        assert out_txt.exists()
        assert out_json.exists()
        assert out_txt.read_text(encoding="utf-8") == res.text


# =========================================================================
# 3. PageRank Edge Cases Tests
# =========================================================================


def test_pagerank_empty():
    ranks = deterministic_pagerank(sp.csr_matrix((0, 0), dtype=np.float64))
    assert len(ranks) == 0


def test_pagerank_single_node():
    ranks = deterministic_pagerank(sp.csr_matrix(np.array([[1.0]])))
    assert len(ranks) == 1
    assert np.isclose(ranks[0], 1.0)


def test_pagerank_disconnected():
    adj = sp.csr_matrix(
        np.array(
            [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ]
        )
    )
    ranks = deterministic_pagerank(adj, damping=0.85)
    assert len(ranks) == 3
    assert np.allclose(ranks, 1.0)


# =========================================================================
# 4. Language Detection Tests
# =========================================================================


def test_detect_language_english():
    lang = detect_document_language("This is a standard English technical report.")
    assert lang == "en"


def test_detect_language_short():
    lang = detect_document_language("Hi")
    assert isinstance(lang, str)
    assert detect_document_language("") == "en"
    res = detect_sentence_languages(["Hi", "This is a much longer English sentence for detection."])
    assert len(res) == 2
    assert res[0] == "en"
    assert res[1] == "en"


# =========================================================================
# 5. ByteSpan Operations Tests
# =========================================================================


def test_bytespan_operations():
    s1 = ByteSpan("doc1", 0, 10)
    s2 = ByteSpan("doc1", 5, 15)
    s3 = ByteSpan("doc1", 20, 30)
    s_other_doc = ByteSpan("doc2", 0, 10)

    # Length
    assert s1.length == 10
    assert s1.byte_len == 10

    # Overlaps
    assert s1.overlaps(s2)
    assert not s1.overlaps(s3)
    assert not s1.overlaps(s_other_doc)

    # Contains
    assert s1.contains(ByteSpan("doc1", 2, 8))
    assert not s1.contains(s2)

    # Slice bytes
    raw = b"0123456789abcdef"
    assert s1.slice_bytes(raw) == b"0123456789"

    # To dict
    d = s1.to_dict()
    assert d["start"] == 0 and d["end"] == 10

    # Error conditions
    with pytest.raises(ValueError):
        ByteSpan("doc1", -1, 10)
    with pytest.raises(ValueError):
        ByteSpan("doc1", 10, 5)
