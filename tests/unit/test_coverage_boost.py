"""Targeted tests to push test coverage above 95% across all modules."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from contextcull.detect.atoms import extract_atoms
from contextcull.ingest.decoder import clean_char_to_byte_span, ingest_bytes
from contextcull.ir.models import BlockKind, CandidateUnit, CompileMode, CompilePolicy, TokenBudget
from contextcull.ir.spans import ByteSpan
from contextcull.parse.pdf import parse_pdf_blocks
from contextcull.parse.structured import parse_csv_blocks, parse_json_blocks
from contextcull.route.router import route_and_parse
from contextcull.select.budget import select_units_budget_free, select_units_constrained
from contextcull.tokenize.profile import get_tokenizer

CL100K = get_tokenizer("cl100k_base")


# =========================================================================
# 1. PDF Text Extraction & Paragraph Parser
# =========================================================================


def test_pdf_with_text_extraction():
    """Mock PdfReader to test PDF paragraph and heading extraction logic."""
    sample_text = (
        "SECTION TITLE\n"
        "\n"
        "This is the first paragraph.\n"
        "It spans multiple lines.\n"
        "\n"
        "This is the second paragraph with details.\n"
    )
    mock_page = MagicMock()
    mock_page.extract_text.return_value = sample_text

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("contextcull.parse.pdf.PdfReader", return_value=mock_reader):
        ingest = ingest_bytes(b"%PDF-1.4 mock pdf data")
        blocks = parse_pdf_blocks(ingest)

        assert len(blocks) == 3
        assert blocks[0].kind == BlockKind.HEADING
        assert blocks[0].text == "SECTION TITLE"
        assert blocks[1].kind == BlockKind.PROSE
        assert "first paragraph" in blocks[1].text


def test_pdf_page_exception_handled():
    """Verify exceptions during page text extraction are gracefully skipped."""
    mock_page = MagicMock()
    mock_page.extract_text.side_effect = RuntimeError("Corrupt font")

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("contextcull.parse.pdf.PdfReader", return_value=mock_reader):
        ingest = ingest_bytes(b"%PDF-1.4 mock pdf data")
        blocks = parse_pdf_blocks(ingest)
        assert blocks == []


# =========================================================================
# 2. Pareto Knee (Kneedle) & Selection Coverage
# =========================================================================


def test_budget_free_kneedle_curve():
    """Test Kneedle Pareto selection in STRICT mode with rich vocabulary."""
    policy = CompilePolicy(mode=CompileMode.STRICT, discourse_pruning=False)

    # Create 10 units with distinct informative words
    units = []
    vocab_words = [
        "alpha apple avocado amber atlas",
        "beta banana bronze beacon breeze",
        "gamma gorilla granite garden glacier",
        "delta dragon diamond desert dolphin",
        "epsilon eagle emerald eclipse echo",
        "zeta zebra zinc zenith zero",
        "eta elephant ember engine echo",
        "theta tiger topaz timber tempest",
        "iota iguana iron island ivory",
        "kappa kangaroo kinetic kernel knight",
    ]
    for i, words in enumerate(vocab_words):
        span = ByteSpan("doc1", 0, len(words.encode("utf-8")))
        u = CandidateUnit(
            unit_id=f"unit_{i:04d}",
            block_id=f"block_{i:04d}",
            sources=(span,),
            text=f"Report section {i}: {words} happened here.",
            score=1.0 - (i * 0.05),
        )
        units.append(u)

    selected = select_units_budget_free(units, atoms=(), policy=policy, tokenizer=CL100K)
    assert len(selected) > 0
    assert len(selected) <= len(units)


def test_budget_constrained_entity_break():
    """Test constrained selection when candidate entities cannot fit in budget."""
    span = ByteSpan("doc1", 0, 10)
    u1 = CandidateUnit(
        unit_id="u1",
        block_id="block_1",
        sources=(span,),
        text="Host 10.0.0.1 and CVE-2026-0001 failed.",
        score=0.9,
    )
    u2 = CandidateUnit(
        unit_id="u2",
        block_id="block_2",
        sources=(span,),
        text="Host 10.0.0.2 with an extraordinarily long narrative explanation that cannot fit into any modest remaining budget.",
        score=0.8,
    )
    budget = TokenBudget(tokens=25, hard_budget=False)
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    selected = select_units_constrained(
        [u1, u2], atoms=(), budget=budget, policy=policy, tokenizer=CL100K
    )
    assert len(selected) == 1
    assert selected[0].unit_id == "u1"


# =========================================================================
# 3. Flexible Required Terms in Atom Detection
# =========================================================================


def test_atoms_flexible_required_terms():
    """Test flexible matching for quantities like '5 minutes' -> '5 seconds'."""
    text = "The failover took 5 seconds to complete."
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest, required_terms=("5 minutes", "", "nonexistent"))

    req_atoms = [a for a in atoms if a.required]
    assert len(req_atoms) >= 1
    assert "5 seconds" in req_atoms[0].surface


# =========================================================================
# 4. Structured Parser Error Handling
# =========================================================================


def test_structured_invalid_json():
    ingest = ingest_bytes(b"invalid json data {")
    blocks = parse_json_blocks(ingest)
    assert blocks == []


def test_structured_empty_csv():
    ingest = ingest_bytes(b"")
    blocks = parse_csv_blocks(ingest)
    assert blocks == []


# =========================================================================
# 5. Router Code & Fallback Handling
# =========================================================================


def test_router_code_routing():
    code_text = "def calculate_metric(data: list) -> int:\n    return len(data)\n"
    ingest = ingest_bytes(code_text.encode("utf-8"))
    blocks = route_and_parse(ingest)
    assert len(blocks) >= 1
    assert blocks[0].kind == BlockKind.CODE


def test_router_empty_text():
    ingest = ingest_bytes(b"   \n\t  ")
    blocks = route_and_parse(ingest)
    assert blocks == []


def test_router_exception_fallback():
    ingest = ingest_bytes(b"plain text input")
    with patch(
        "contextcull.route.router.parse_plain_text_blocks", side_effect=ValueError("Test error")
    ):
        blocks = route_and_parse(ingest)
        assert len(blocks) == 1
        assert blocks[0].kind == BlockKind.OPAQUE


# =========================================================================
# 6. Decoder Coordinate Translation Bounds
# =========================================================================


def test_decoder_bounds():
    ingest = ingest_bytes(b"Short text")
    # char bounds beyond length raises ValueError
    with pytest.raises(ValueError):
        clean_char_to_byte_span(ingest, 0, 999)

    # byte bounds beyond length raises ValueError
    with pytest.raises(ValueError):
        ingest.source_map.byte_to_char_range(0, 999)
