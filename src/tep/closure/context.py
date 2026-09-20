"""Context closure: resolves structural dependencies and antecedent hierarchy."""

from __future__ import annotations

from collections.abc import Sequence

from tep.ir.models import Block, BlockKind, CandidateUnit


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

    selected_ids = {u.unit_id for u in selected_units}
    closure_ids: set[str] = set(selected_ids)

    # Map unit_id to block
    block_map = {b.block_id: b for b in blocks}
    unit_map = {u.unit_id: u for u in all_units}

    # If any prose is selected, ensure preceding heading in document is included
    heading_units = [u for u in all_units if block_map.get(u.block_id) and block_map[u.block_id].kind == BlockKind.HEADING]

    for u in selected_units:
        # Find nearest preceding heading if not already selected
        preceding_headings = [
            h for h in heading_units if h.source_order < u.source_order
        ]
        if preceding_headings:
            nearest_heading = max(preceding_headings, key=lambda h: h.source_order)
            closure_ids.add(nearest_heading.unit_id)

    # Reassemble closed units sorted by source order
    closed_units = [unit_map[uid] for uid in closure_ids if uid in unit_map]
    closed_units.sort(key=lambda u: u.source_order)
    return closed_units
