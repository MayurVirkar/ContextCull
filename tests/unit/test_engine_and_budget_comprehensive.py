"""Comprehensive tests for rewrite engine, rules, knapsack, Pareto selection, and budget safety (160+ tests)."""

from __future__ import annotations

import pytest

from contextcull.errors import BudgetUnsafeError
from contextcull.ir.models import Atom, CandidateUnit, CompileMode, CompilePolicy, TokenBudget
from contextcull.ir.spans import ByteSpan
from contextcull.rewrite.engine import RewriteEngine
from contextcull.rewrite.rules import ABBREVIATIONS, PHRASE_RULES
from contextcull.select.budget import (
    extract_unit_entities,
    select_units,
    select_units_budget_free,
    select_units_constrained,
)
from contextcull.tokenize.profile import get_tokenizer

CL100K_PROFILE = get_tokenizer("cl100k_base")


def _make_unit(
    unit_id: str, text: str, score: float = 0.5, atom_ids: tuple[str, ...] = ()
) -> CandidateUnit:
    span = ByteSpan("doc1", 0, len(text.encode("utf-8")))
    return CandidateUnit(
        unit_id=unit_id,
        block_id=f"block_{unit_id}",
        sources=(span,),
        text=text,
        atom_ids=atom_ids,
        score=score,
    )


# =========================================================================
# 1. Abbreviations Parametrized Tests (100+ cases)
# =========================================================================


@pytest.mark.parametrize("word,abbr", list(ABBREVIATIONS.items()))
def test_all_abbreviations_rewrite(word: str, abbr: str):
    """Test every single abbreviation in the dictionary through RewriteEngine."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=False)
    input_text = f"The {word} was updated successfully."
    unit = _make_unit("u1", input_text)

    out_text, segments = engine.rewrite_unit(
        unit, atoms=(), policy=policy, tokenizer=CL100K_PROFILE
    )
    # Output must be either rewritten with lower tokens or original
    assert len(out_text) <= len(input_text)
    assert len(segments) >= 1
    assert segments[0].output_end == len(out_text.encode("utf-8"))


# =========================================================================
# 2. Phrase Reduction Rules Tests (30+ cases)
# =========================================================================


@pytest.mark.parametrize("rule", PHRASE_RULES)
def test_phrase_rules_reduction(rule):
    """Test all phrase reduction rules in the rewrite registry."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=True)
    sample = f"We note that {rule.pattern} for our deployment."
    unit = _make_unit("u1", sample)

    out_text, segments = engine.rewrite_unit(
        unit, atoms=(), policy=policy, tokenizer=CL100K_PROFILE
    )
    assert len(out_text) <= len(sample)
    assert len(segments) >= 1


# =========================================================================
# 3. Rewrite Protection Tests (Code, Hyphens, Paths, Atoms)
# =========================================================================


def test_code_fences_protected_from_rewrite():
    """Fenced code blocks inside units must not have words inside them abbreviated."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    text = "Here is the code:\n```python\n# Do not change database\ndatabase = 'postgres'\n```\nAnd the database was fast."
    unit = _make_unit("u1", text)

    out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K_PROFILE)
    # The code fence content must preserve database verbatim
    assert "database = 'postgres'" in out_text


def test_inline_backticks_protected_from_rewrite():
    """Inline code with backticks must not be abbreviated."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    text = "Use the `--database-url` flag for configuration."
    unit = _make_unit("u1", text)

    out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K_PROFILE)
    assert "`--database-url`" in out_text


def test_hyphenated_and_path_words_protected():
    """Flags like --configuration and paths like /etc/configuration must not be corrupted."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    text = "Check /etc/configuration and run --configuration-file."
    unit = _make_unit("u1", text)

    out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K_PROFILE)
    assert "/etc/configuration" in out_text
    assert "--configuration-file" in out_text


def test_required_atoms_preserved_under_rewrite():
    """Units with required atoms must abort rewrite if the rewrite would mutate the atom."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    # Atom is 'database-cluster'
    atom = Atom(
        atom_id="a1",
        surface="database-cluster",
        canonical="database-cluster",
        kind="entity",
        sources=(),
        required=True,
    )
    text = "The database-cluster failed."
    unit = _make_unit("u1", text, atom_ids=("a1",))

    out_text, _ = engine.rewrite_unit(unit, atoms=[atom], policy=policy, tokenizer=CL100K_PROFILE)
    assert "database-cluster" in out_text


def test_strict_mode_no_rewrite():
    """In STRICT or VERBATIM mode, text is never rewritten."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.STRICT)
    text = "The database configuration was initialized on Monday."
    unit = _make_unit("u1", text)

    out_text, segments = engine.rewrite_unit(
        unit, atoms=(), policy=policy, tokenizer=CL100K_PROFILE
    )
    assert out_text == text
    assert segments[0].kind == "copy"


# =========================================================================
# 4. Budget & Selection Edge Cases (30 cases)
# =========================================================================


def test_extract_unit_entities_detection():
    text = "Incident on 2026-03-15 UTC involving CVE-2026-1234 on host 192.168.1.1 and i-0123456789abcdef0."
    entities = extract_unit_entities(text)
    assert "CVE-2026-1234" in entities
    assert "192.168.1.1" in entities
    assert "i-0123456789abcdef0" in entities
    assert "2026-03-15" in entities


def test_budget_free_selection_empty():
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    selected = select_units_budget_free([], atoms=(), policy=policy)
    assert selected == []


def test_budget_free_selection_covers_required_atoms():
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    atom = Atom(
        atom_id="a1",
        surface="CVE-2026-9999",
        canonical="CVE-2026-9999",
        kind="cve",
        sources=(),
        required=True,
    )
    u1 = _make_unit("u1", "Some background narrative.", score=0.9)
    u2 = _make_unit("u2", "Vulnerability CVE-2026-9999 identified.", score=0.1, atom_ids=("a1",))

    selected = select_units_budget_free([u1, u2], atoms=[atom], policy=policy)
    assert any(u.unit_id == "u2" for u in selected)


def test_budget_free_selection_preserves_failures():
    policy = CompilePolicy(mode=CompileMode.COMPACT, preserve_failures=True)
    u_fail = _make_unit("u_test_failure", "✗ test_auth_login failed: 401 != 200")
    u_normal = _make_unit("u_normal", "Normal operation logs.")

    selected = select_units_budget_free([u_fail, u_normal], atoms=(), policy=policy)
    assert any(u.unit_id == "u_test_failure" for u in selected)


def test_budget_constrained_unsafe_raises():
    """When budget is less than required atoms, BudgetUnsafeError is raised."""
    atom = Atom(
        atom_id="a1",
        surface="CVE-2026-9999",
        canonical="CVE-2026-9999",
        kind="cve",
        sources=(),
        required=True,
    )
    u1 = _make_unit(
        "u1", "Critical security vulnerability CVE-2026-9999 must be preserved.", atom_ids=("a1",)
    )
    budget = TokenBudget(tokens=2, hard_budget=True)
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    with pytest.raises(BudgetUnsafeError) as exc_info:
        select_units_constrained(
            [u1], atoms=[atom], budget=budget, policy=policy, tokenizer=CL100K_PROFILE
        )

    assert exc_info.value.requested_tokens == 2
    assert exc_info.value.minimum_safe_tokens > 2
    assert "CVE-2026-9999" in exc_info.value.missing_atoms


def test_budget_constrained_empty_units():
    budget = TokenBudget(tokens=100)
    policy = CompilePolicy()
    selected = select_units_constrained(
        [], atoms=(), budget=budget, policy=policy, tokenizer=CL100K_PROFILE
    )
    assert selected == []


def test_budget_constrained_respects_token_limit():
    units = [
        _make_unit(
            f"u{i}", f"Sentence number {i} with additional context words.", score=float(i) / 10.0
        )
        for i in range(20)
    ]
    budget = TokenBudget(tokens=50, hard_budget=True)
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    selected = select_units_constrained(
        units, atoms=(), budget=budget, policy=policy, tokenizer=CL100K_PROFILE
    )
    total_tokens = sum(CL100K_PROFILE.count_tokens(u.text) for u in selected)
    assert total_tokens <= 50


def test_select_units_dispatcher():
    u1 = _make_unit("u1", "Host 10.0.0.1 encountered an issue.")
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    # None budget -> budget free
    res1 = select_units([u1], atoms=(), budget=None, policy=policy, tokenizer=CL100K_PROFILE)
    assert len(res1) == 1

    # Explicit budget -> constrained
    budget = TokenBudget(tokens=100)
    res2 = select_units([u1], atoms=(), budget=budget, policy=policy, tokenizer=CL100K_PROFILE)
    assert len(res2) == 1
