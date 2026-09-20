"""Constraint-aware selection supporting both budget-free natural density and token-budget limits."""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

from contextcull.detect.atoms import extract_unit_entities
from contextcull.errors import BudgetUnsafeError
from contextcull.ir.models import Atom, CandidateUnit, CompilePolicy, TokenBudget
from contextcull.tokenize.profile import TokenizerProfile


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
       Uses greedy submodular set-cover to select the minimal set of units covering all distinct entities.
    2. Dynamic Pareto Knee (Kneedle Algorithm):
       - Traces the cumulative information gain curve versus cumulative token expenditure.
       - Automatically computes the optimal dynamic token budget at the point of maximum curvature (knee),
         maximizing information density while eliminating redundant narrative scaffolding.
    3. Preserves source chronological order.
    """
    if not units:
        return []

    required_atom_ids = {a.atom_id for a in atoms if a.required}
    unit_entities = [extract_unit_entities(u.text) for u in units]
    doc_entities: set[str] = set()
    for ue in unit_entities:
        doc_entities.update(ue)

    # 1. Mandatory units: Required atoms and test failures
    mandatory_indices: set[int] = set()
    covered_entities: set[str] = set()

    for i, u in enumerate(units):
        has_required = any(aid in required_atom_ids for aid in u.atom_ids)
        is_failure = policy.preserve_failures and "test_failure" in u.block_id
        is_action = "_decision" in u.block_id or "_request" in u.block_id
        if has_required or is_failure or is_action:
            mandatory_indices.add(i)
            covered_entities.update(unit_entities[i])

    # Greedy submodular set-cover for remaining critical entities
    uncovered_entities = doc_entities - covered_entities
    candidates = [i for i in range(len(units)) if i not in mandatory_indices]

    while uncovered_entities:
        best_idx = -1
        best_gain = 0
        for i in candidates:
            if i in mandatory_indices:
                continue
            gain = len(unit_entities[i] & uncovered_entities)
            if gain > best_gain:
                best_gain = gain
                best_idx = i

        if best_idx >= 0 and best_gain > 0:
            mandatory_indices.add(best_idx)
            uncovered_entities -= unit_entities[best_idx]
        else:
            break

    # 2. Dynamic Pareto Knee Selection for narrative context
    scores_arr = np.array(scores) if scores is not None else np.ones(len(units))
    if len(scores_arr) < len(units):
        scores_arr = np.ones(len(units))

    # Tokenizer for token cost estimation
    from contextcull.tokenize.profile import get_tokenizer

    tok = tokenizer or get_tokenizer("openai:cl100k_base")

    # Vocabulary covered by mandatory base units
    covered_vocab: set[str] = set()
    for idx in mandatory_indices:
        words = re.findall(r"\b\w{3,}\b", units[idx].text.lower())
        covered_vocab.update(words)

    remaining_pool = [i for i in range(len(units)) if i not in mandatory_indices]
    if not remaining_pool:
        return [units[i] for i in sorted(mandatory_indices)]

    # Compute initial information density for all remaining candidates
    unit_words = [set(re.findall(r"\b\w{3,}\b", units[i].text.lower())) for i in range(len(units))]
    unit_costs = [max(1, tok.count_tokens(units[i].text)) for i in range(len(units))]

    # Greedily build the Pareto curve by information density
    chosen_order: list[int] = []
    cum_tokens_list: list[int] = [sum(unit_costs[i] for i in mandatory_indices)]
    cum_gain_list: list[float] = [float(len(covered_vocab))]

    curr_vocab = set(covered_vocab)
    curr_tokens = cum_tokens_list[0]
    pool = set(remaining_pool)

    # Greedily select next candidate by marginal efficiency
    while pool:
        best_i = -1
        best_density = 0.0
        best_new_words: set[str] = set()

        for i in pool:
            new_words = unit_words[i] - curr_vocab
            if not new_words:
                continue
            dens = (len(new_words) * (0.5 + 0.5 * float(scores_arr[i]))) / unit_costs[i]
            if dens > best_density:
                best_density = dens
                best_i = i
                best_new_words = new_words

        if best_i >= 0 and best_density > 0.005:
            pool.remove(best_i)
            chosen_order.append(best_i)
            curr_tokens += unit_costs[best_i]
            curr_vocab.update(best_new_words)
            cum_tokens_list.append(curr_tokens)
            cum_gain_list.append(float(len(curr_vocab)))
        else:
            break

    if len(chosen_order) <= 2:
        selected_indices = set(mandatory_indices) | set(chosen_order)
        return [units[i] for i in sorted(selected_indices)]

    # Calculate optimal knee using Kneedle algorithm (maximum distance from chord)
    x = np.array(cum_tokens_list, dtype=float)
    y = np.array(cum_gain_list, dtype=float)

    x_range = x[-1] - x[0]
    y_range = y[-1] - y[0]

    if x_range > 0 and y_range > 0:
        x_norm = (x - x[0]) / x_range
        y_norm = (y - y[0]) / y_range
        # Perpendicular distance from normalized chord y = x
        distances = y_norm - x_norm
        knee_idx = int(np.argmax(distances))
        if knee_idx <= 0 or distances[knee_idx] <= 0:
            selected_narrative = chosen_order
        else:
            selected_narrative = chosen_order[:knee_idx]
    else:
        selected_narrative = chosen_order

    selected_indices = set(mandatory_indices) | set(selected_narrative)
    if not selected_indices and units:
        selected_indices = {0}

    # 3. Restore source chronological order
    return [units[i] for i in sorted(selected_indices)]


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

    # Mandatory units: required atoms, test failures, and explicit decisions/requests
    mandatory_indices: set[int] = set()
    for i, u in enumerate(units):
        has_required = any(aid in required_atom_ids for aid in u.atom_ids)
        is_failure = policy.preserve_failures and "test_failure" in u.block_id
        is_action = "_decision" in u.block_id or "_request" in u.block_id
        if has_required or is_failure or is_action:
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

    # Priority 1: Greedy submodular cover for critical entities within remaining budget
    doc_entities: set[str] = set()
    for ue in unit_entities:
        doc_entities.update(ue)
    covered_entities: set[str] = set()
    for idx in selected_indices:
        covered_entities.update(unit_entities[idx])

    uncovered_entities = doc_entities - covered_entities
    candidates = [i for i in range(len(units)) if i not in selected_indices]

    while uncovered_entities:
        best_idx = -1
        best_gain = 0
        for i in candidates:
            if i in selected_indices:
                continue
            cost = tokenizer.count_tokens(units[i].text)
            if budget.tokens is not None and current_tokens + cost > budget.tokens:
                continue
            gain = len(unit_entities[i] & uncovered_entities)
            if gain > best_gain:
                best_gain = gain
                best_idx = i

        if best_idx >= 0 and best_gain > 0:
            selected_indices.add(best_idx)
            current_tokens += tokenizer.count_tokens(units[best_idx].text)
            uncovered_entities -= unit_entities[best_idx]
        else:
            break

    # Priority 2: Centrality-ranked narrative expansion
    remaining = [i for i in range(len(units)) if i not in selected_indices]
    remaining.sort(key=lambda i: scores_arr[i], reverse=True)

    for idx in remaining:
        cost = tokenizer.count_tokens(units[idx].text)
        if budget.tokens is not None and current_tokens + cost <= budget.tokens:
            selected_indices.add(idx)
            current_tokens += cost

    return [units[i] for i in sorted(selected_indices)]
