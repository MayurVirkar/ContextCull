"""Constraint-aware selection supporting both budget-free natural density and token-budget limits."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

import numpy as np

from tep.errors import BudgetUnsafeError
from tep.ir.models import Atom, CandidateUnit, CompileMode, CompilePolicy, TokenBudget
from tep.tokenize.profile import TokenizerProfile

# Generic regex patterns for critical factual entities (no document-specific terms)
CRITICAL_ENTITY_PATTERNS = [
    re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\s*UTC)?)?\b"),
    re.compile(r"\bi-[0-9a-f]{8,17}\b"),
    re.compile(r"\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}\b"),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    re.compile(r"\b[0-9a-fA-F]{40}\b|\b(?=[0-9a-f]{7,39}\b)(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,39}\b"),
    re.compile(r"\b\d+(?:\.\d+)?(?:\s*(?:MB|GB|TB|KB|kB|ms|µs|ns|s|%|x|min|mins|minutes?|hours?|hrs?|days?|weeks?))\b", re.IGNORECASE),
    re.compile(r"\b[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)+\b"),
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
        if has_required or is_failure:
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

    # In COMPACT mode with discourse pruning, 100% entity and atom coverage is guaranteed
    # at the minimal information-theoretic floor. Return the optimal entity floor directly.
    if policy.mode == CompileMode.COMPACT and policy.discourse_pruning:
        return [units[i] for i in sorted(mandatory_indices)]

    # 2. Dynamic Pareto Knee Selection for narrative context
    scores_arr = np.array(scores) if scores is not None else np.ones(len(units))
    if len(scores_arr) < len(units):
        scores_arr = np.ones(len(units))

    # Tokenizer for token cost estimation
    from tep.tokenize.profile import get_tokenizer

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
        selected_narrative = chosen_order[:knee_idx]
    else:
        selected_narrative = chosen_order

    selected_indices = set(mandatory_indices) | set(selected_narrative)

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

    # Mandatory units: required atoms and test failures (if policy.preserve_failures)
    mandatory_indices: set[int] = set()
    for i, u in enumerate(units):
        has_required = any(aid in required_atom_ids for aid in u.atom_ids)
        is_failure = policy.preserve_failures and "test_failure" in u.block_id
        if has_required or is_failure:
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
