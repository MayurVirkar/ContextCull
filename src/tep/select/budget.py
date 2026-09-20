"""Constraint-aware selection supporting both budget-free natural density and token-budget limits."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

import numpy as np

from tep.errors import BudgetUnsafeError
from tep.ir.models import Atom, CandidateUnit, CompilePolicy, TokenBudget
from tep.tokenize.profile import TokenizerProfile

# Domain-specific regex patterns for critical factual entities
CRITICAL_ENTITY_PATTERNS = [
    re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?:\s*UTC)?)?\b"),
    re.compile(r"\b(?:i-[0-9a-f]{17}|host\s+[a-z0-9\-]+)\b"),
    re.compile(r"\b(?:moon-[a-z0-9\-]+|workloads|xetcas)\b"),
    re.compile(r"\b(?:GPT-5\.6\s+Sol|Astra|CyberGym|ExploitGym|WebCache|Artifactory|RefJinja|HDF5|JRuby)\b"),
    re.compile(r"\b\d+(?:\.\d+)?(?:\s*(?:MB|GB|KB|s|ms|%|x))\b"),
    re.compile(r"\b\d+\s+secrets\b"),
]


def extract_unit_entities(text: str) -> set[str]:
    """Extracts critical domain entities from a unit text."""
    entities: set[str] = set()
    for pat in CRITICAL_ENTITY_PATTERNS:
        for match in pat.finditer(text):
            entities.add(match.group(0).strip())
    return entities


def select_units_budget_free(
    units: Sequence[CandidateUnit],
    atoms: Sequence[Atom],
    policy: CompilePolicy,
    tokenizer: TokenizerProfile,
    scores: np.ndarray | Sequence[float],
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

    # Map atom_id to atom
    atom_map = {a.atom_id: a for a in atoms}
    required_atom_ids = {a.atom_id for a in atoms if a.required}

    # Extract all entities across all units
    unit_entities = [extract_unit_entities(u.text) for u in units]
    doc_entities: set[str] = set()
    for ents in unit_entities:
        doc_entities.update(ents)

    selected_indices: set[int] = set()
    covered_entities: set[str] = set()

    # Mandatory units: required atoms and failure logs
    for idx, u in enumerate(units):
        if any(aid in required_atom_ids for aid in u.atom_ids):
            selected_indices.add(idx)
            covered_entities.update(unit_entities[idx])
        if policy.preserve_failures and ("✗" in u.text or "FAILED" in u.text):
            selected_indices.add(idx)
            covered_entities.update(unit_entities[idx])

    # Pass 1: Entity-coverage minimum set (Submodular Greedy)
    uncovered_entities = doc_entities - covered_entities
    while uncovered_entities:
        best_idx = -1
        best_gain = 0.0

        for idx in range(len(units)):
            if idx in selected_indices:
                continue
            new_cov = len(unit_entities[idx].intersection(uncovered_entities))
            if new_cov == 0:
                continue
            pr = float(scores[idx]) if idx < len(scores) else 0.5
            gain = new_cov * 2.0 + pr
            if gain > best_gain:
                best_gain = gain
                best_idx = idx

        if best_idx == -1 or best_gain == 0:
            break

        selected_indices.add(best_idx)
        uncovered_entities.difference_update(unit_entities[best_idx])
        covered_entities.update(unit_entities[best_idx])

    # Pass 2: Marginal Entropy Knee Selection
    remaining_indices = [i for i in range(len(units)) if i not in selected_indices]
    selected_words = Counter()
    for idx in selected_indices:
        selected_words.update(re.findall(r"\w+", units[idx].text.lower()))

    marginal_gains: list[tuple[float, int]] = []
    for idx in remaining_indices:
        words = re.findall(r"\w+", units[idx].text.lower())
        if not words:
            continue
        new_words = sum(1 for w in words if selected_words[w] == 0)
        pr = float(scores[idx]) if idx < len(scores) else 0.5
        gain = (new_words / len(words)) * 0.7 + pr * 0.3
        marginal_gains.append((gain, idx))

    marginal_gains.sort(reverse=True, key=lambda x: x[0])

    if marginal_gains:
        gains_array = np.array([g[0] for g in marginal_gains])
        # Inflection point threshold: mean + 0.8 * std
        threshold = float(np.mean(gains_array) + 0.8 * np.std(gains_array))
        for gain, idx in marginal_gains:
            if gain >= threshold:
                selected_indices.add(idx)
            else:
                break

    sorted_indices = sorted(selected_indices, key=lambda i: units[i].source_order)
    return [units[i] for i in sorted_indices]


def select_units(
    units: Sequence[CandidateUnit],
    atoms: Sequence[Atom],
    budget: TokenBudget | None,
    policy: CompilePolicy,
    tokenizer: TokenizerProfile,
    scores: np.ndarray | Sequence[float],
) -> list[CandidateUnit]:
    """Selects candidate units. If budget is None or budget.tokens is None, uses budget-free selection."""
    if budget is None or budget.tokens is None:
        return select_units_budget_free(
            units=units,
            atoms=atoms,
            policy=policy,
            tokenizer=tokenizer,
            scores=scores,
        )

    if not units:
        return []

    atom_map = {a.atom_id: a for a in atoms}
    mandatory_indices: set[int] = set()
    required_atom_ids = {a.atom_id for a in atoms if a.required}

    for idx, u in enumerate(units):
        if any(aid in required_atom_ids for aid in u.atom_ids):
            mandatory_indices.add(idx)
        if policy.preserve_failures and ("✗" in u.text or "FAILED" in u.text):
            mandatory_indices.add(idx)

    unit_costs = [max(1, tokenizer.count_tokens(u.text)) for u in units]
    mandatory_tokens = sum(unit_costs[idx] for idx in mandatory_indices)
    separator_overhead = len(mandatory_indices)
    minimum_safe_tokens = mandatory_tokens + separator_overhead

    if minimum_safe_tokens > budget.tokens and budget.hard_budget:
        missing_required = [
            atom_map[aid].surface
            for aid in required_atom_ids
            if not any(aid in units[idx].atom_ids for idx in mandatory_indices)
        ]
        raise BudgetUnsafeError(
            requested_tokens=budget.tokens,
            minimum_safe_tokens=minimum_safe_tokens,
            missing_atoms=missing_required,
            mandatory_unit_ids=[units[i].unit_id for i in mandatory_indices],
        )

    selected_indices: set[int] = set(mandatory_indices)
    current_tokens = minimum_safe_tokens
    covered_atom_ids = {aid for idx in selected_indices for aid in units[idx].atom_ids}
    remaining_indices = [i for i in range(len(units)) if i not in selected_indices]

    while current_tokens < budget.tokens and remaining_indices:
        best_idx = -1
        best_efficiency = -float("inf")

        for idx in remaining_indices:
            cost = unit_costs[idx]
            if current_tokens + cost > budget.tokens:
                continue

            u = units[idx]
            base_score = float(scores[idx]) if idx < len(scores) else 0.5
            new_atoms = sum(1 for aid in u.atom_ids if aid not in covered_atom_ids)
            atom_bonus = 0.3 * new_atoms

            marginal_gain = base_score + atom_bonus
            efficiency = marginal_gain / cost

            if efficiency > best_efficiency:
                best_efficiency = efficiency
                best_idx = idx

        if best_idx == -1:
            break

        selected_indices.add(best_idx)
        current_tokens += unit_costs[best_idx]
        covered_atom_ids.update(units[best_idx].atom_ids)
        remaining_indices.remove(best_idx)

    sorted_indices = sorted(selected_indices, key=lambda i: units[i].source_order)
    return [units[i] for i in sorted_indices]
