"""Intermediate representation (IR) models for ContextCull compiler pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

import orjson

from contextcull.ir.spans import SourceRef


class BlockKind(StrEnum):
    PROSE = "prose"
    HEADING = "heading"
    LIST = "list"
    TABLE = "table"
    CODE = "code"
    LOG = "log"
    EMAIL_HEADER = "email_header"
    QUOTE = "quote"
    STRUCTURED = "structured"
    OPAQUE = "opaque"


class CompileMode(StrEnum):
    VERBATIM = "verbatim"
    STRICT = "strict"
    COMPACT = "compact"
    TASK = "task"


@dataclass(frozen=True, slots=True)
class Block:
    """A routed structural block from the source document."""

    block_id: str
    kind: BlockKind
    sources: tuple[SourceRef, ...]
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Atom:
    """A protected semantic atom (quantity, entity, identifier, path, negation, etc.)."""

    atom_id: str
    kind: str
    surface: str
    canonical: str
    sources: tuple[SourceRef, ...]
    confidence: float = 1.0
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "kind": self.kind,
            "surface": self.surface,
            "canonical": self.canonical,
            "sources": [s.to_dict() for s in self.sources],
            "confidence": self.confidence,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class CandidateUnit:
    """A candidate extractive unit (sentence, log-line, signature, table-row) for ranking and selection."""

    unit_id: str
    block_id: str
    sources: tuple[SourceRef, ...]
    text: str
    kind: Literal["copy", "rewrite", "aggregate", "separator"] = "copy"
    atom_ids: tuple[str, ...] = ()
    dependency_ids: tuple[str, ...] = ()
    source_order: int = 0
    score: float = 0.0


@dataclass(frozen=True, slots=True)
class OutputSegment:
    """A rendered segment in the compiled output context with provenance."""

    output_start: int
    output_end: int
    kind: Literal["copy", "rewrite", "aggregate", "separator"]
    sources: tuple[SourceRef, ...]
    rule_id: str | None = None
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_start": self.output_start,
            "output_end": self.output_end,
            "kind": self.kind,
            "sources": [s.to_dict() for s in self.sources],
            "rule_id": self.rule_id,
        }


@dataclass(frozen=True, slots=True)
class TokenBudget:
    """Budget parameters for context compilation."""

    tokens: int | None = None
    profile: str = "openai:cl100k_base"
    hard_budget: bool = True


@dataclass(frozen=True, slots=True)
class CompilePolicy:
    """Policy governing compiler safety levels and constraints."""

    mode: CompileMode = CompileMode.COMPACT
    required_terms: tuple[str, ...] = ()
    preserve_failures: bool = True
    preserve_negation: bool = True
    preserve_modality: bool = True
    preserve_causality: bool = True
    source_order: bool = True
    with_legend: bool = False
    max_k_neighbors: int = 10
    pagerank_damping: float = 0.85
    min_safe_tokens: int = 0
    discourse_pruning: bool = True
    filter_boilerplate: bool = True
    abbreviations: bool = False


@dataclass(frozen=True, slots=True)
class CompileResult:
    """The final result of context compilation."""

    status: str
    text: str
    manifest: dict[str, Any]
    metrics: dict[str, Any]
    diagnostics: tuple[str, ...] = ()
    decision_trace: tuple[dict[str, Any], ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "OK"

    def write_text(self, path: str) -> None:
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.text)

    def write_manifest(self, path: str) -> None:
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(orjson.dumps(self.manifest, option=orjson.OPT_INDENT_2))
