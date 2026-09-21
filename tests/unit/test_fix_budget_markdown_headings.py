"""Regression tests for hard-budget + Markdown-headings selection (closure-aware budgeting).

Covers the bug where select_units_constrained spent the whole budget before
apply_context_closure added parent headings back in, and where per-unit token sums
(ignoring "\\n" separators and BPE join effects) under-counted the true output size --
both of which caused INVARIANT_FAILED even though a valid budget-fitting selection existed.
"""

from __future__ import annotations

import pytest

from contextcull import ContextCompiler, TokenBudget
from contextcull.errors import BudgetUnsafeError
from contextcull.ir.models import CandidateUnit, CompileMode, CompilePolicy
from contextcull.ir.spans import ByteSpan
from contextcull.select.budget import select_units_constrained
from contextcull.tokenize.profile import get_tokenizer

CL100K = get_tokenizer("cl100k_base")


def _markdown_doc(n: int = 40) -> str:
    return "\n\n".join(
        f"# Section {i} heading with some words\n\n"
        f"The service at host {i} returned error code {500 + i} after a long timeout "
        f"of {i * 10} ms during deployment."
        for i in range(n)
    )


@pytest.mark.parametrize("target_budget", list(range(100, 1001, 50)))
def test_markdown_headings_hard_budget_sweep_ok_and_within_budget(target_budget: int):
    """Hard budget + Markdown headings must never INVARIANT_FAILED; OK implies output <= budget."""
    doc = _markdown_doc()
    result = ContextCompiler().compile(doc, budget=TokenBudget(tokens=target_budget))

    assert result.status != "INVARIANT_FAILED", result.diagnostics
    if result.status == "OK":
        assert result.metrics["output_tokens"] <= target_budget


def test_markdown_headings_small_budgets_never_invariant_failed():
    """Finer sweep across small/edge budgets: status is always OK or TARGET_BUDGET_UNSAFE."""
    doc = _markdown_doc()
    for b in range(20, 260, 5):
        result = ContextCompiler().compile(doc, budget=TokenBudget(tokens=b))
        assert result.status in ("OK", "TARGET_BUDGET_UNSAFE"), (b, result.diagnostics)
        if result.status == "OK":
            assert result.metrics["output_tokens"] <= b


def test_selection_is_closure_aware_heading_charged_up_front():
    """A selection that needs a heading must charge that heading's cost during selection,
    not discover it only after apply_context_closure blows the budget."""
    span = ByteSpan("doc1", 0, 10)
    heading = CandidateUnit(
        unit_id="h1",
        block_id="block_heading",
        sources=(span,),
        text="# A Fairly Long Section Heading About Something",
        kind="copy",
        source_order=0,
    )
    body = CandidateUnit(
        unit_id="b1",
        block_id="block_body",
        sources=(span,),
        text="Host 10.0.0.1 failed.",
        kind="copy",
        source_order=1,
    )
    from contextcull.ir.models import Block, BlockKind

    blocks = [
        Block(block_id="block_heading", kind=BlockKind.HEADING, sources=(span,), text=heading.text),
        Block(block_id="block_body", kind=BlockKind.PROSE, sources=(span,), text=body.text),
    ]
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    # Budget fits the body alone but not body + heading together.
    body_only = CL100K.count_tokens(body.text)
    budget_tokens = body_only + 1

    from contextcull.ir.models import TokenBudget as TB

    selected = select_units_constrained(
        [heading, body],
        atoms=(),
        budget=TB(tokens=budget_tokens, hard_budget=True),
        policy=policy,
        tokenizer=CL100K,
        blocks=blocks,
    )
    # Whatever gets selected, the exact joined render must fit the budget -- i.e. the
    # selection must not silently rely on closure to add the heading for free.
    joined = "\n".join(u.text for u in selected)
    assert CL100K.count_tokens(joined) <= budget_tokens


def test_budget_unsafe_missing_atoms_lists_only_unfitting_atoms():
    """missing_atoms should report only the required atoms that don't fit, not all of them."""
    doc = (
        "# Report\n\n"
        "Attacker exploited CVE-2026-0001 on host 10.0.0.1.\n\n"
        "Attacker also exploited CVE-2026-0002 on host 10.0.0.2 during a much longer "
        "and more verbose sentence with extra padding words to inflate token count "
        "significantly beyond the first line.\n"
    )
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    result = ContextCompiler().compile(
        doc, budget=TokenBudget(tokens=25, hard_budget=True), policy=policy
    )
    assert result.status == "TARGET_BUDGET_UNSAFE"
    missing = result.manifest["missing_atoms"]
    assert "CVE-2026-0002" in missing
    assert "10.0.0.2" in missing
    # The cheap first sentence's atoms should fit and NOT be reported as missing.
    assert "CVE-2026-0001" not in missing
    assert "10.0.0.1" not in missing


def test_budget_unsafe_all_atoms_missing_when_nothing_fits():
    doc = "# Report\n\nAttacker exploited CVE-2026-0001 on host 10.0.0.1.\n"
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    with pytest.raises(BudgetUnsafeError) as exc_info:
        from contextcull.detect.atoms import extract_atoms
        from contextcull.ingest.decoder import ingest_document

        ingest, blocks = ingest_document(doc.encode())
        atoms = extract_atoms(ingest, required_terms=(), blocks=blocks)
        compiler = ContextCompiler()
        units = compiler._build_candidate_units(ingest, blocks, atoms, policy)
        select_units_constrained(
            units,
            atoms=atoms,
            budget=TokenBudget(tokens=1, hard_budget=True),
            policy=policy,
            tokenizer=CL100K,
            blocks=blocks,
        )

    err = exc_info.value
    assert "CVE-2026-0001" in err.missing_atoms
    assert "10.0.0.1" in err.missing_atoms
