"""Constraint-aware selection supporting both budget-free natural density and token-budget limits."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

import numpy as np

from tep.errors import BudgetUnsafeError
from tep.ir.models import Atom, CandidateUnit, CompilePolicy, TokenBudget
from tep.tokenize.profile import TokenizerProfile

# Generic regex patterns for critical factual entities (no document-specific terms)
CRITICAL_ENTITY_PATTERNS = [
    re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\s*UTC)?)?\b"),
    re.compile(r"\bi-[0-9a-f]{8,17}\b"),
    re.compile(r"\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}\b"),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    re.compile(r"\b[0-9a-fA-F]{40}\b|\b(?=[0-9a-f]{7,39}\b)(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,39}\b"),
    re.compile(r"\b\d+(?:\.\d+)?(?:\s*(?:MB|GB|TB|KB|kB|ms|µs|ns|s|%|x))\b"),
]


def extract_unit_entities(text: str) -> set[str]:
    """Extracts critical domain entities from a unit text using generic patterns."""
    entities: set[str] = set()
    for pat in CRITICAL_ENTITY_PATTERNS:
        for match in pat.finditer(text):
            entities.add(match.group(0).strip())
    return entities


def select_units_budget_free(
    units: Sequence[CandidateUnit],
    atoms: Sequence[Atom],
    policy: CompilePolicy,
    tokenizer: TokenizerProfile | None = None,
    scores: np.ndarray | Sequence[float] | None = None,
) -> list[CandidateUnit]:
    """Selects candidate units without any user-imposed token budget.

    Algorithm:
    1. Entity Coverage Floor: Guarantees 100% coverage of all detected critical entities and required atoms.
    2. Pareto Elbow Selection: Evaluates marginal information gain (new vocabulary entropy + PageRank centrality)
       and stops when marginal gain drops below the knee threshold (diminishing returns).
    3. Preserves source chronological order.
    """
    if not units:
        return []

    required_atom_ids = {a.atom_id for a in atoms if a.required}

    # Extract all entities across all units
    unit_entities = [extract_unit_entities(u.text) for u in units]
    doc_entities: set[str] = set()
    for ue in unit_entities:
        doc_entities.update(ue)

    # 1. Mandatory units: Any unit with a required atom or critical entity
    mandatory_indices: set[int] = set()
    covered_entities: set[str] = set()
    covered_required_atoms: set[str] = set()

    for i, u in enumerate(units):
        has_required_atom = any(aid in required_atom_ids for aid in u.atom_ids)
        has_critical_entity = bool(unit_entities[i])
        if has_required_atom or has_critical_entity:
            mandatory_indices.add(i)
            covered_entities.update(unit_entities[i])
            covered_required_atoms.update(aid for aid in u.atom_ids if aid in required_atom_ids)

    # Submodular greedy selection for any remaining required atoms/entities
    uncovered_entities = doc_entities - covered_entities
    uncovered_atoms = required_atom_ids - covered_required_atoms

    while uncovered_entities or uncovered_atoms:
        best_idx = -1
        best_gain = 0
        for i, u in enumerate(units):
            if i in mandatory_indices:
                continue
            gain = len(unit_entities[i] & uncovered_entities) + len(set(u.atom_ids) & uncovered_atoms)
            if gain > best_gain:
                best_gain = gain
                best_idx = i

        if best_idx >= 0 and best_gain > 0:
            mandatory_indices.add(best_idx)
            uncovered_entities -= unit_entities[best_idx]
            uncovered_atoms -= set(units[best_idx].atom_ids)
        else:
            break

    # 2. Pareto Elbow Selection for narrative & structural context
    scores_arr = np.array(scores) if scores is not None else np.ones(len(units))
    if len(scores_arr) < len(units):
        scores_arr = np.ones(len(units))

    # Token-level vocabulary set already covered by mandatory units
    selected_indices = set(mandatory_indices)
    covered_vocab: Counter[str] = Counter()
    for idx in selected_indices:
        words = re.findall(r"\b\w{3,}\b", units[idx].text.lower())
        covered_vocab.update(words)

    # Candidate pool for narrative expansion
    remaining_indices = [i for i in range(len(units)) if i not in selected_indices]
    # Sort remaining candidates by PageRank centrality score descending
    remaining_indices.sort(key=lambda i: scores_arr[i], reverse=True)

    # Marginal entropy threshold: stop when new tokens offer minimal new vocabulary
    elbow_threshold = 0.08  # Knee threshold for diminishing marginal returns

    for idx in remaining_indices:
        words = set(re.findall(r"\b\w{3,}\b", units[idx].text.lower()))
        if not words:
            continue
        new_words = words - set(covered_vocab.keys())
        marginal_gain = len(new_words) / len(words)

        # Weight marginal gain by centrality score
        marginal_value = marginal_gain * (0.5 + 0.5 * float(scores_arr[idx]))

        if marginal_value >= elbow_threshold:
            selected_indices.add(idx)
            covered_vocab.update(words)

    # 3. Restore source chronological order
    result = [units[i] for i in sorted(selected_indices)]
    return result


def select_units(
    units: Sequence[CandidateUnit],
    atoms: Sequence[Atom],
    budget: TokenBudget | None,
    policy: CompilePolicy,
    tokenizer: TokenizerProfile,
    scores: np.ndarray | Sequence[float] | None = None,
) -> list[CandidateUnit]:
    """Dispatches to budget-free natural density selection or budget-constrained knapsack selection."""
    if budget is None or budget.tokens is None:
        return select_units_budget_free(units, atoms, policy, tokenizer, scores)

    # Budget-constrained selection
    return select_units_constrained(units, atoms, budget, policy, tokenizer, scores)


def select_units_constrained(
    units: Sequence[CandidateUnit],
    atoms: Sequence[Atom],
    budget: TokenBudget,
    policy: CompilePolicy,
    tokenizer: TokenizerProfile,
    scores: np.ndarray | Sequence[float] | None = None,
) -> list[CandidateUnit]:
    """Constraint-aware selection enforcing target token budget with fail-closed safety."""
    if not units:
        return []

    required_atom_ids = {a.atom_id for a in atoms if a.required}
    unit_entities = [extract_unit_entities(u.text) for u in units]

    # Mandatory units for required atoms and critical entities
    mandatory_indices: set[int] = set()
    for i, u in enumerate(units):
        if any(aid in required_atom_ids for aid in u.atom_ids) or unit_entities[i]:
            mandatory_indices.add(i)

    # Calculate token cost of mandatory units
    mandatory_tokens = sum(tokenizer.count_tokens(units[i].text) for i in mandatory_indices)

    if budget.tokens is not None and mandatory_tokens > budget.tokens and budget.hard_budget:
        missing_atoms = [a.surface for a in atoms if a.required]
        raise BudgetUnsafeError(
                requested_tokens=budget.tokens,
                minimum_safe_tokens=mandatory_tokens,
                missing_atoms=missing_atoms,
                mandatory_unit_ids=[units[i].unit_id for i in mandatory_indices],
            )

    selected_indices = set(mandatory_indices)
    current_tokens = mandatory_tokens

    scores_arr = np.array(scores) if scores is not None else np.ones(len(units))
    remaining = [i for i in range(len(units)) if i not in selected_indices]
    remaining.sort(key=lambda i: scores_arr[i], reverse=True)

    for idx in remaining:
        cost = tokenizer.count_tokens(units[idx].text)
        if budget.tokens is not None and current_tokens + cost <= budget.tokens:
            selected_indices.add(idx)
            current_tokens += cost

    return [units[i] for i in sorted(selected_indices)]
