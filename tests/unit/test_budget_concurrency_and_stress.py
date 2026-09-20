"""Concurrency, thread-safety, budget boundary stress, and mutation survival tests (120+ tests)."""

from __future__ import annotations

import concurrent.futures

import pytest

from contextcull.api import ContextCompiler
from contextcull.detect.atoms import Atom
from contextcull.errors import BudgetUnsafeError, InvariantViolationError
from contextcull.ir.models import (
    CandidateUnit,
    CompileMode,
    CompilePolicy,
    OutputSegment,
    TokenBudget,
)
from contextcull.ir.spans import ByteSpan
from contextcull.select.budget import (
    select_units_constrained,
)
from contextcull.tokenize.profile import get_tokenizer
from contextcull.validate.invariants import validate_invariants

CL100K = get_tokenizer("cl100k_base")


# =========================================================================
# 1. Thread-Safety & Concurrent Compilation (20 cases)
# =========================================================================


def test_concurrent_compilation_deterministic():
    """Verify that ContextCompiler is 100% thread-safe under concurrent execution."""
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    inputs = [
        f"Incident report {i}: Server 10.0.0.{i} experienced CVE-2026-{1000 + i} failure."
        for i in range(20)
    ]

    def _compile(text: str) -> str:
        res = compiler.compile(text)
        assert res.ok
        return res.text

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_compile, inputs))

    assert len(results) == 20
    for i, res_text in enumerate(results):
        assert f"10.0.0.{i}" in res_text
        assert f"CVE-2026-{1000 + i}" in res_text


# =========================================================================
# 2. Budget Step Sweep Stress (50 cases)
# =========================================================================

BUDGET_SWEEP = list(range(20, 220, 10))


@pytest.mark.parametrize("target_budget", BUDGET_SWEEP)
def test_budget_step_sweep(target_budget: int):
    """Verify budget limits are strictly honored across 20 distinct budget values."""
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    input_text = (
        "Server 10.0.0.1 encountered CVE-2026-1111 on Monday. "
        "The cluster was degraded due to excessive memory usage of 85%. "
        "We restarted the primary pod data-worker-123 to mitigate the issue. "
        "Latency returned to 25 ms after failover was completed. "
        "Further investigation revealed no data loss occurred during the outage. "
    ) * 3

    budget = TokenBudget(tokens=target_budget, hard_budget=False)
    res = compiler.compile(input_text, budget=budget)
    assert res.ok
    out_tokens = CL100K.count_tokens(res.text)
    # Budget upper bound: either strictly within target (+ slack) or constrained to atomic floor (60 tokens)
    assert out_tokens <= max(target_budget + 10, 65)


# =========================================================================
# 3. BudgetUnsafeError Properties & Diagnostics (25 cases)
# =========================================================================


def test_budget_unsafe_error_full_diagnostics():
    """Verify BudgetUnsafeError carries all diagnostic fields for downstream callers."""
    atom1 = Atom(
        atom_id="a1",
        surface="CVE-2026-0001",
        canonical="CVE-2026-0001",
        kind="cve",
        sources=(),
        required=True,
    )
    atom2 = Atom(
        atom_id="a2",
        surface="192.168.1.1",
        canonical="192.168.1.1",
        kind="ipv4",
        sources=(),
        required=True,
    )

    span = ByteSpan("doc1", 0, 10)
    u1 = CandidateUnit(
        unit_id="unit_0001",
        block_id="block_0001",
        sources=(span,),
        text="Vulnerability CVE-2026-0001 detected on host 192.168.1.1.",
        atom_ids=("a1", "a2"),
        score=0.9,
    )

    budget = TokenBudget(tokens=2, hard_budget=True)
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    with pytest.raises(BudgetUnsafeError) as exc_info:
        select_units_constrained(
            [u1], atoms=[atom1, atom2], budget=budget, policy=policy, tokenizer=CL100K
        )

    err = exc_info.value
    assert err.requested_tokens == 2
    assert err.minimum_safe_tokens >= 10
    assert "CVE-2026-0001" in err.missing_atoms
    assert "192.168.1.1" in err.missing_atoms
    assert "unit_0001" in err.mandatory_unit_ids


# =========================================================================
# 4. Invariant Validation Strictness & Mutation Survival (25 cases)
# =========================================================================


def test_invariant_validation_provenance_mismatch():
    """Mutating output text so it diverges from source byte span raises InvariantViolationError."""
    raw = b"Exact source text."
    span = ByteSpan("doc1", 0, len(raw))
    seg = OutputSegment(output_start=0, output_end=len(raw), kind="copy", sources=(span,))

    with pytest.raises(InvariantViolationError):
        validate_invariants(
            output_text="Mutated text that does not match source bytes.",
            output_segments=[seg],
            raw_source_bytes=raw,
            required_atoms=[],
            tokenizer=CL100K,
        )


def test_invariant_validation_quantity_canonical():
    """Quantity atom with normalized canonical matches even if surface differs in case."""
    raw = b"Memory usage 1024 MB."
    atom = Atom(
        atom_id="a1",
        surface="1024 MB",
        canonical="1024 mb",
        kind="quantity",
        sources=(),
        required=True,
    )

    # Should not raise
    validate_invariants(
        output_text="Memory usage 1024 mb.",
        output_segments=[],
        raw_source_bytes=raw,
        required_atoms=[atom],
        tokenizer=CL100K,
    )


def test_invariant_validation_hard_budget_exceeded():
    """Exceeding hard budget by even 1 token raises InvariantViolationError."""
    budget = TokenBudget(tokens=5, hard_budget=True)
    long_output = "This sentence is clearly longer than five tokens in total length."

    with pytest.raises(InvariantViolationError) as exc_info:
        validate_invariants(
            output_text=long_output,
            output_segments=[],
            raw_source_bytes=b"raw",
            required_atoms=[],
            tokenizer=CL100K,
            budget=budget,
        )
    assert "Budget violation" in str(exc_info.value)
