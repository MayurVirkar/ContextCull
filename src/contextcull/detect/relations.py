"""Semantic relation extraction and invariant binding."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from contextcull.ir.models import Atom
from contextcull.ir.spans import SourceRef


@dataclass(frozen=True, slots=True)
class SemanticRelation:
    """A typed semantic relation between source spans."""

    kind: Literal["negation_scope", "causality", "condition", "attribution", "modality_scope"]
    head_span: SourceRef
    tail_span: SourceRef | None = None
    relation_marker: str = ""


def extract_semantic_relations(atoms: Sequence[Atom]) -> list[SemanticRelation]:
    """Extracts typed semantic relations from detected atoms."""
    relations: list[SemanticRelation] = []
    for a in atoms:
        if a.kind == "bound_negation" and a.sources:
            parts = a.surface.split(maxsplit=1)
            marker = parts[0] if parts else ""
            relations.append(
                SemanticRelation(
                    kind="negation_scope",
                    head_span=a.sources[0],
                    relation_marker=marker,
                )
            )
        elif a.kind == "modality" and a.sources:
            relations.append(
                SemanticRelation(
                    kind="modality_scope",
                    head_span=a.sources[0],
                    relation_marker=a.surface,
                )
            )
        elif a.kind == "causality" and a.sources:
            relations.append(
                SemanticRelation(
                    kind="causality",
                    head_span=a.sources[0],
                    relation_marker=a.surface,
                )
            )
        elif a.kind == "condition" and a.sources:
            relations.append(
                SemanticRelation(
                    kind="condition",
                    head_span=a.sources[0],
                    relation_marker=a.surface,
                )
            )
    return relations
