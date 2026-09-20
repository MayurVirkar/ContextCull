"""Tests for budget selection algorithms (natural density floor & constrained knapsack)."""

import pytest

from contextcull.errors import BudgetUnsafeError
from contextcull.ir.models import Atom, CandidateUnit, CompilePolicy, TokenBudget
from contextcull.ir.spans import ByteSpan
from contextcull.select.budget import select_units, select_units_budget_free
from contextcull.tokenize.profile import get_tokenizer


def test_budget_free_natural_density_floor():
    """Verify that budget-free selection retains units with critical entities and applies Pareto elbow."""
    tokenizer = get_tokenizer("openai:cl100k_base")
    policy = CompilePolicy()

    atoms = [
        Atom(
            "a1",
            "cve",
            "CVE-2026-66384",
            "cve-2026-66384",
            (ByteSpan("d", 0, 14),),
            1.0,
            required=True,
        ),
        Atom(
            "a2",
            "instance_id",
            "i-0622056ec3e996a7c",
            "i-0622056ec3e996a7c",
            (ByteSpan("d", 20, 39),),
            1.0,
            required=True,
        ),
    ]

    units = [
        CandidateUnit(
            "u1",
            "b1",
            (ByteSpan("d", 0, 30),),
            "Attacker exploited CVE-2026-66384 on the server.",
            atom_ids=("a1",),
        ),
        CandidateUnit(
            "u2",
            "b2",
            (ByteSpan("d", 30, 60),),
            "The target instance was i-0622056ec3e996a7c in AWS.",
            atom_ids=("a2",),
        ),
        CandidateUnit(
            "u3", "b3", (ByteSpan("d", 60, 90),), "We reviewed the internal logs thoroughly today."
        ),
        CandidateUnit(
            "u4", "b4", (ByteSpan("d", 90, 120),), "We reviewed the internal logs thoroughly today."
        ),
    ]

    selected = select_units_budget_free(units, atoms, policy, tokenizer=tokenizer)
    selected_ids = {u.unit_id for u in selected}

    # Both mandatory units must be selected
    assert "u1" in selected_ids
    assert "u2" in selected_ids
    # Redundant duplicate unit u4 must be pruned by Pareto elbow
    assert "u4" not in selected_ids


def test_budget_constrained_fail_closed():
    """Verify that budget-constrained selection raises BudgetUnsafeError if budget is too small."""
    tokenizer = get_tokenizer("openai:cl100k_base")
    policy = CompilePolicy()

    atoms = [
        Atom(
            "a1",
            "cve",
            "CVE-2026-66384",
            "cve-2026-66384",
            (ByteSpan("d", 0, 14),),
            1.0,
            required=True,
        ),
    ]

    units = [
        CandidateUnit(
            "u1",
            "b1",
            (ByteSpan("d", 0, 50),),
            "Attacker exploited CVE-2026-66384 on the primary cluster node.",
            atom_ids=("a1",),
        ),
    ]

    # Target budget of 2 tokens cannot hold unit u1 (~10 tokens)
    budget = TokenBudget(tokens=2, profile="openai:cl100k_base", hard_budget=True)

    with pytest.raises(BudgetUnsafeError) as exc_info:
        select_units(units, atoms, budget, policy, tokenizer)

    assert exc_info.value.requested_tokens == 2
    assert exc_info.value.minimum_safe_tokens > 2
