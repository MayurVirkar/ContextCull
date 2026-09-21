"""Context closure: resolves structural dependencies and antecedent hierarchy."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence

from contextcull.ir.models import Block, BlockKind, CandidateUnit


def build_heading_index(
    all_units: Sequence[CandidateUnit], blocks: Sequence[Block]
) -> tuple[list[int], list[str]]:
    """Builds a source-order-sorted index of heading units for O(log h) closure lookups.

    Returns parallel lists (source_orders, unit_ids) of every unit whose block is a HEADING,
    sorted ascending by source_order.
    """
    block_map = {b.block_id: b for b in blocks}
    heading_units = sorted(
        (
            u
            for u in all_units
            if block_map.get(u.block_id) and block_map[u.block_id].kind == BlockKind.HEADING
        ),
        key=lambda u: u.source_order,
    )
    return [u.source_order for u in heading_units], [u.unit_id for u in heading_units]


def nearest_preceding_heading_id(
    heading_orders: Sequence[int], heading_ids: Sequence[str], source_order: int
) -> str | None:
    """Returns the unit_id of the nearest heading strictly preceding source_order, if any."""
    idx = bisect_left(heading_orders, source_order) - 1
    return heading_ids[idx] if idx >= 0 else None


def apply_context_closure(
    selected_units: Sequence[CandidateUnit],
    all_units: Sequence[CandidateUnit],
    blocks: Sequence[Block],
) -> list[CandidateUnit]:
    """Applies structural context closure to selected units.

    Ensures that selected paragraphs include parent section headings,
    and returns a chronologically sorted unit list.
    """
    if not selected_units:
        return []

    closure_ids: set[str] = {u.unit_id for u in selected_units}
    unit_map = {u.unit_id: u for u in all_units}
    heading_orders, heading_ids = build_heading_index(all_units, blocks)

    for u in selected_units:
        h_id = nearest_preceding_heading_id(heading_orders, heading_ids, u.source_order)
        if h_id is not None:
            closure_ids.add(h_id)

    # Reassemble closed units sorted by source order
    closed_units = [unit_map[uid] for uid in closure_ids if uid in unit_map]
    closed_units.sort(key=lambda u: u.source_order)
    return closed_units
