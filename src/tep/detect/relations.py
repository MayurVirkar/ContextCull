"""Semantic relation extraction and invariant binding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tep.ir.spans import SourceRef


@dataclass(frozen=True, slots=True)
class SemanticRelation:
    """A typed semantic relation between source spans."""

    kind: Literal["negation_scope", "causality", "condition", "attribution", "modality_scope"]
    head_span: SourceRef
    tail_span: SourceRef | None = None
    relation_marker: str = ""
