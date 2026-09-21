"""Constraint-aware selection supporting both budget-free natural density and token-budget limits."""

from __future__ import annotations

import heapq
import re
from collections.abc import Sequence

import numpy as np

from contextcull.closure.context import build_heading_index, nearest_preceding_heading_id
from contextcull.detect.atoms import extract_unit_entities
from contextcull.errors import BudgetUnsafeError
from contextcull.ir.models import Atom, Block, CandidateUnit, CompilePolicy, TokenBudget
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
    1. Entity & Required-Atom Floor: Guarantees coverage of every detected critical entity
       (via greedy submodular set-cover) and every required (mandatory) atom. Other,
       non-required atoms are not individually guaranteed -- they are retained only if the
       unit carrying them survives step 2 below.
    2. Greedy Vocabulary-Coverage Curve, cut at the Kneedle Knee:
       - Greedily grows a narrative unit set by marginal new-vocabulary density per token.
       - Traces cumulative vocabulary coverage versus cumulative token expenditure and cuts
         at the point of maximum curvature (the Kneedle knee), eliminating redundant
         narrative scaffolding on a best-effort basis.
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

    # 2. Greedy vocabulary-coverage curve for narrative context
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

    # Greedily build the vocabulary-coverage curve by information density using Minoux lazy greedy
    chosen_order: list[int] = []
    cum_tokens_list: list[int] = [sum(unit_costs[i] for i in mandatory_indices)]
    cum_gain_list: list[float] = [float(len(covered_vocab))]

    curr_vocab = set(covered_vocab)
    curr_tokens = cum_tokens_list[0]

    # Max-heap storing upper bounds on marginal density: (-density, index, step_evaluated)
    heap: list[tuple[float, int, int]] = []
    for i in remaining_pool:
        new_words = unit_words[i] - curr_vocab
        if new_words:
            dens = (len(new_words) * (0.5 + 0.5 * float(scores_arr[i]))) / unit_costs[i]
            if dens > 0.005:
                heap.append((-dens, i, 0))
    heapq.heapify(heap)

    current_step = 0
    while heap:
        neg_dens, i, step_eval = heapq.heappop(heap)
        dens = -neg_dens
        if dens <= 0.005:
            break

        if step_eval == current_step:
            # By submodularity, upper bounds of all other elements <= dens. Optimal choice.
            chosen_order.append(i)
            curr_tokens += unit_costs[i]
            curr_vocab.update(unit_words[i])
            cum_tokens_list.append(curr_tokens)
            cum_gain_list.append(float(len(curr_vocab)))
            current_step += 1
        else:
            # Recompute marginal density against current vocabulary
            new_words = unit_words[i] - curr_vocab
            if new_words:
                new_dens = (len(new_words) * (0.5 + 0.5 * float(scores_arr[i]))) / unit_costs[i]
                if new_dens > 0.005:
                    heapq.heappush(heap, (-new_dens, i, current_step))

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
    blocks: Sequence[Block] = (),
) -> list[CandidateUnit]:
    """Dispatches to budget-free natural density selection or budget-constrained knapsack selection."""
    if budget is None or budget.tokens is None:
        return select_units_budget_free(units, atoms, policy, tokenizer, scores)

    # Budget-constrained selection
    return select_units_constrained(units, atoms, budget, policy, tokenizer, scores, blocks)


def select_units_constrained(
    units: Sequence[CandidateUnit],
    atoms: Sequence[Atom],
    budget: TokenBudget,
    policy: CompilePolicy,
    tokenizer: TokenizerProfile,
    scores: np.ndarray | Sequence[float] | None = None,
    blocks: Sequence[Block] = (),
) -> list[CandidateUnit]:
    """Constraint-aware selection enforcing target token budget with fail-closed safety.

    Closure-aware: adding a unit also (approximately) charges the cost of its nearest
    not-yet-selected preceding heading -- apply_context_closure will pull that heading in
    downstream regardless of budget -- plus one token per "\\n" separator joining units in
    the final render. After the greedy passes, if the *exact* tokenized cost of the joined
    unit texts still exceeds the budget (BPE can merge/tokenize a join differently than the
    sum of per-unit counts), lowest-priority non-mandatory units are dropped until it fits.
    This is safe because the rewrite stage (Stage 8) only ever shortens text, so a fit
    achieved here survives to the final render.
    """
    if not units:
        return []

    required_atom_ids = {a.atom_id for a in atoms if a.required}
    unit_entities = [extract_unit_entities(u.text) for u in units]

    # Precompute per-unit token costs once (avoids O(candidates x rounds) tokenizer calls).
    unit_costs = [tokenizer.count_tokens(u.text) for u in units]

    heading_orders, heading_ids = build_heading_index(units, blocks)
    id_to_index = {u.unit_id: i for i, u in enumerate(units)}

    def closure_heading_index(i: int) -> int | None:
        h_id = nearest_preceding_heading_id(heading_orders, heading_ids, units[i].source_order)
        return id_to_index.get(h_id) if h_id is not None else None

    def heading_ancestor_chain(i: int, selected: set[int]) -> set[int]:
        """Not-yet-selected preceding headings pulled in once unit i is included.

        apply_context_closure (Stage 7) adds, for *every* unit in the final selected set
        (headings included), its own single nearest preceding heading. Since a selected
        heading is itself part of that final set, a run of consecutive headings each need
        their own preceding heading too -- so this walks the whole ancestor chain, not just
        one hop, to match the fixed point apply_context_closure will actually reach.
        """
        chain: set[int] = set()
        cur = i
        while True:
            h = closure_heading_index(cur)
            if h is None or h in selected or h in chain:
                break
            chain.add(h)
            cur = h
        return chain

    def cost_to_add(i: int, selected: set[int]) -> tuple[int, set[int]]:
        """Marginal (tokens, unit-indices) needed to add unit i -- including its not-yet-selected
        closure heading chain and the "\\n" separator(s) that will join the new unit(s) into
        the text."""
        if i in selected:
            return 0, set()
        extra = {i} | heading_ancestor_chain(i, selected)
        sep_delta = len(extra) if selected else max(0, len(extra) - 1)
        return sum(unit_costs[j] for j in extra) + sep_delta, extra

    def joined_cost(indices: set[int]) -> int:
        if not indices:
            return 0
        return sum(unit_costs[i] for i in indices) + (len(indices) - 1)

    # Mandatory units: required atoms, test failures, and explicit decisions/requests
    mandatory_indices: set[int] = set()
    for i, u in enumerate(units):
        has_required = any(aid in required_atom_ids for aid in u.atom_ids)
        is_failure = policy.preserve_failures and "test_failure" in u.block_id
        is_action = "_decision" in u.block_id or "_request" in u.block_id
        if has_required or is_failure or is_action:
            mandatory_indices.add(i)

    # Mandatory units drag in their closure heading chains too, since apply_context_closure
    # will add those downstream regardless of budget.
    closure_extra: set[int] = set()
    for i in mandatory_indices:
        closure_extra |= heading_ancestor_chain(i, mandatory_indices | closure_extra)
    mandatory_indices |= closure_extra

    # Token cost of mandatory units, including closure headings and inter-unit separators.
    mandatory_tokens = joined_cost(mandatory_indices)

    if budget.tokens is not None and mandatory_tokens > budget.tokens and budget.hard_budget:
        missing_atoms = _missing_required_atoms(
            units, atoms, mandatory_indices, unit_costs, cost_to_add, budget.tokens
        )
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
        best_delta = 0
        best_extra: set[int] = set()
        for i in candidates:
            if i in selected_indices:
                continue
            delta, extra = cost_to_add(i, selected_indices)
            if budget.tokens is not None and current_tokens + delta > budget.tokens:
                continue
            gain = len(unit_entities[i] & uncovered_entities)
            if gain > best_gain:
                best_gain = gain
                best_idx = i
                best_delta = delta
                best_extra = extra

        if best_idx >= 0 and best_gain > 0:
            selected_indices |= best_extra
            current_tokens += best_delta
            uncovered_entities -= unit_entities[best_idx]
        else:
            break

    # Priority 2: Centrality-ranked narrative expansion
    remaining = [i for i in range(len(units)) if i not in selected_indices]
    remaining.sort(key=lambda i: scores_arr[i], reverse=True)

    for idx in remaining:
        if idx in selected_indices:
            continue
        delta, extra = cost_to_add(idx, selected_indices)
        if budget.tokens is not None and current_tokens + delta <= budget.tokens:
            selected_indices |= extra
            current_tokens += delta

    # Final exact fit: BPE tokenization of the actual joined text can diverge from the
    # approximate per-unit + separator accounting above. Drop lowest-priority non-mandatory
    # units (by score) until the exact joined token count fits the hard budget.
    if budget.tokens is not None and budget.hard_budget:

        def exact_joined_tokens(indices: set[int]) -> int:
            texts = [units[i].text for i in sorted(indices)]
            return tokenizer.count_tokens("\n".join(texts))

        exact_tokens = exact_joined_tokens(selected_indices)
        if exact_tokens > budget.tokens:
            # Never drop a heading here: apply_context_closure (Stage 7) will unconditionally
            # re-add it if any remaining selected unit still needs it as its nearest preceding
            # heading, which would silently undo the trim. Only content units are droppable.
            heading_index_set = {id_to_index[hid] for hid in heading_ids if hid in id_to_index}
            droppable = sorted(
                selected_indices - mandatory_indices - heading_index_set,
                key=lambda i: (scores_arr[i], -unit_costs[i]),
            )
            ptr = 0
            while exact_tokens > budget.tokens and ptr < len(droppable):
                deficit = exact_tokens - budget.tokens
                drop_batch: list[int] = []
                removed_estimate = 0
                while ptr < len(droppable) and removed_estimate < deficit:
                    i = droppable[ptr]
                    ptr += 1
                    drop_batch.append(i)
                    removed_estimate += unit_costs[i] + 1
                if not drop_batch:
                    break
                selected_indices -= set(drop_batch)
                exact_tokens = exact_joined_tokens(selected_indices)

    return [units[i] for i in sorted(selected_indices)]


def _missing_required_atoms(
    units: Sequence[CandidateUnit],
    atoms: Sequence[Atom],
    mandatory_indices: set[int],
    unit_costs: list[int],
    cost_to_add,
    budget_tokens: int,
) -> list[str]:
    """Determines which required atom surfaces would have to be dropped at budget_tokens.

    Greedily fits the cheapest mandatory units first (maximizing how many survive), then
    reports the required atoms bound only to units that could not fit -- i.e. the atoms that
    would actually be dropped at the requested budget. If nothing fits, this naturally
    reports every mandatory required atom.
    """
    ordered = sorted(mandatory_indices, key=lambda i: unit_costs[i])
    fitted: set[int] = set()
    current = 0
    for i in ordered:
        delta, extra = cost_to_add(i, fitted)
        if current + delta <= budget_tokens:
            fitted |= extra
            current += delta

    fitted_atom_ids = {aid for i in fitted for aid in units[i].atom_ids}
    mandatory_atom_ids = {aid for i in mandatory_indices for aid in units[i].atom_ids}
    return [
        a.surface
        for a in atoms
        if a.required and a.atom_id in mandatory_atom_ids and a.atom_id not in fitted_atom_ids
    ]
