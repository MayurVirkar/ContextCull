"""Tests for hard invariant validation and tokenizer error handling."""

import pytest

from contextcull.errors import InvariantViolationError
from contextcull.ir.models import Atom, OutputSegment, TokenBudget
from contextcull.ir.spans import ByteSpan
from contextcull.tokenize.profile import TiktokenProfile, get_tokenizer
from contextcull.validate.invariants import validate_invariants


def test_unknown_tokenizer_raises_value_error():
    """Verify B1: unknown tokenizer profile raises ValueError rather than silently bypassing budget."""
    with pytest.raises(ValueError, match="Unknown tokenizer profile"):
        get_tokenizer("gpt4-typo")


def test_unknown_tiktoken_model_raises_value_error():
    """Verify B2: unknown model in TiktokenProfile raises ValueError (catching KeyError internally)."""
    with pytest.raises(ValueError, match="Unsupported tiktoken model"):
        TiktokenProfile("nonexistent-model-xyz")


def test_required_atom_surface_dropping_raises_invariant_violation():
    """Verify B7: dropping a required atom raises InvariantViolationError."""
    source = b"Critical alert on host 10.0.0.1 for CVE-2026-66384."
    atom = Atom(
        atom_id="atom_0001",
        kind="cve",
        surface="CVE-2026-66384",
        canonical="cve-2026-66384",
        sources=(ByteSpan("doc", 36, 50),),
        confidence=1.0,
        required=True,
    )
    # Output that does NOT include the required CVE
    output_text = "Critical alert on host 10.0.0.1."
    segments = [
        OutputSegment(
            output_start=0,
            output_end=len(output_text.encode("utf-8")),
            kind="copy",
            sources=(ByteSpan("doc", 0, 32),),
            text=output_text,
        )
    ]
    tokenizer = get_tokenizer("openai:cl100k_base")

    with pytest.raises(
        InvariantViolationError, match="Atom violation: required atom 'CVE-2026-66384'"
    ):
        validate_invariants(
            output_text=output_text,
            output_segments=segments,
            raw_source_bytes=source,
            required_atoms=[atom],
            tokenizer=tokenizer,
        )


def test_hard_budget_exceeded_raises_invariant_violation():
    """Verify that exceeding hard budget raises InvariantViolationError."""
    source = b"One two three four five six seven eight nine ten."
    output_text = "One two three four five six seven eight nine ten."
    segments = [
        OutputSegment(
            output_start=0,
            output_end=len(output_text.encode("utf-8")),
            kind="copy",
            sources=(ByteSpan("doc", 0, len(source)),),
            text=output_text,
        )
    ]
    tokenizer = get_tokenizer("openai:cl100k_base")
    budget = TokenBudget(tokens=3, profile="openai:cl100k_base", hard_budget=True)

    with pytest.raises(InvariantViolationError, match="Budget violation: output tokens"):
        validate_invariants(
            output_text=output_text,
            output_segments=segments,
            raw_source_bytes=source,
            required_atoms=[],
            tokenizer=tokenizer,
            budget=budget,
        )
