"""Main ContextCompiler API and zero-budget summarization interface."""

from __future__ import annotations

import logging
from bisect import bisect_left
from collections.abc import Sequence
from pathlib import Path

from contextcull.closure.context import apply_context_closure
from contextcull.detect.atoms import extract_atoms
from contextcull.errors import BudgetUnsafeError, InvariantViolationError
from contextcull.features.vectorizer import vectorize_units
from contextcull.ingest.decoder import clean_char_to_byte_span, ingest_document
from contextcull.ir.models import (
    Atom,
    Block,
    BlockKind,
    CandidateUnit,
    CompileMode,
    CompilePolicy,
    CompileResult,
    TokenBudget,
)
from contextcull.ir.spans import ByteSpan
from contextcull.rank.pagerank import build_sparse_similarity_graph, deterministic_pagerank
from contextcull.render.manifest import render_and_manifest
from contextcull.rewrite.discourse import is_structural_boilerplate
from contextcull.rewrite.engine import RewriteEngine
from contextcull.segment.sentence import segment_sentences
from contextcull.select.budget import select_units
from contextcull.tokenize.profile import get_tokenizer
from contextcull.validate.invariants import validate_invariants

logger = logging.getLogger(__name__)


class ContextCompiler:
    """Deterministic, source-mapped context compiler with zero-budget optimization."""

    def __init__(self, mode: CompileMode = CompileMode.COMPACT) -> None:
        self.default_mode = mode
        self._rewrite_engine = RewriteEngine()

    @classmethod
    def from_profile(cls, mode: str = "compact") -> ContextCompiler:
        clean_mode = CompileMode(mode.lower())
        return cls(mode=clean_mode)

    def compile_file(
        self,
        path: str | Path,
        budget: TokenBudget | None = None,
        policy: CompilePolicy | None = None,
    ) -> CompileResult:
        with open(path, "rb") as f:
            raw_bytes = f.read()
        return self.compile(raw_bytes, budget=budget, policy=policy)

    def compile(
        self,
        input_data: str | bytes,
        budget: TokenBudget | None = None,
        policy: CompilePolicy | None = None,
    ) -> CompileResult:
        """Compiles raw text or bytes into a source-mapped, optimally compressed context package.

        When budget is None, ContextCull operates in budget-free natural density mode:
        guaranteeing 100% entity and atom coverage while pruning narrative scaffolding
        and stopping at the Pareto marginal entropy elbow.
        """
        raw_bytes = input_data.encode("utf-8") if isinstance(input_data, str) else input_data

        if not raw_bytes.strip():
            return CompileResult(
                status="OK",
                text="",
                manifest={"status": "EMPTY"},
                metrics={"input_tokens": 0, "output_tokens": 0},
            )

        policy = policy or CompilePolicy(mode=self.default_mode)
        profile_name = budget.profile if budget is not None else "openai:cl100k_base"
        tokenizer = get_tokenizer(profile_name)

        # Stage 1: Immutable Ingestion, SourceMap & Block Parsing
        ingest, blocks = ingest_document(raw_bytes)

        # Stage 3: Protected Atom Detection
        atoms = extract_atoms(ingest, required_terms=policy.required_terms, blocks=blocks)

        # Stage 4: Candidate Unit Segmentation
        candidate_units = self._build_candidate_units(ingest, blocks, atoms, policy)

        # Stage 5: Feature Extraction & Sparse Graph Ranking
        if len(candidate_units) > 1:
            tfidf = vectorize_units(candidate_units)
            graph = build_sparse_similarity_graph(tfidf, top_k=policy.max_k_neighbors)
            scores = deterministic_pagerank(graph, damping=policy.pagerank_damping)
        else:
            scores = [1.0] if candidate_units else []

        # Stage 6: Selection (Budget-Free or Constrained)
        try:
            selected_units = select_units(
                units=candidate_units,
                atoms=atoms,
                budget=budget,
                policy=policy,
                tokenizer=tokenizer,
                scores=scores,  # type: ignore
            )
        except BudgetUnsafeError as exc:
            return CompileResult(
                status="TARGET_BUDGET_UNSAFE",
                text="",
                manifest={
                    "schema_version": "1.0",
                    "status": "TARGET_BUDGET_UNSAFE",
                    "source": {"document_id": ingest.document_id},
                    "budget": {
                        "requested_tokens": exc.requested_tokens,
                        "minimum_safe_tokens": exc.minimum_safe_tokens,
                    },
                    "missing_atoms": exc.missing_atoms,
                    "mandatory_unit_ids": exc.mandatory_unit_ids,
                },
                metrics={
                    "requested_tokens": exc.requested_tokens,
                    "minimum_safe_tokens": exc.minimum_safe_tokens,
                },
                diagnostics=(str(exc),),
            )

        # Stage 7: Context Closure
        closed_units = apply_context_closure(
            selected_units=selected_units,
            all_units=candidate_units,
            blocks=blocks,
        )

        # Stage 8: Transactional Rewriting Engine
        rewritten_texts: list[str] = []
        rewritten_segments: list[list] = []

        for u in closed_units:
            text_out, segs = self._rewrite_engine.rewrite_unit(
                unit=u,
                atoms=atoms,
                policy=policy,
                tokenizer=tokenizer,
            )
            rewritten_texts.append(text_out)
            rewritten_segments.append(segs)

        # Stage 9: Invariant Validation
        rendered_preliminary = "\n".join(rewritten_texts)
        flat_segments = [s for sublist in rewritten_segments for s in sublist]

        try:
            validate_invariants(
                output_text=rendered_preliminary,
                output_segments=flat_segments,
                raw_source_bytes=ingest.source_map.raw_bytes,
                required_atoms=[a for a in atoms if a.required],
                tokenizer=tokenizer,
                budget=budget,
            )
        except InvariantViolationError as exc:
            return CompileResult(
                status="INVARIANT_FAILED",
                text="",
                manifest={"status": "INVARIANT_FAILED", "violations": exc.violations},
                metrics={},
                diagnostics=tuple(exc.violations),
            )

        # Stage 10: Render Final Output and Provenance Manifest
        return render_and_manifest(
            ingest=ingest,
            units=closed_units,
            unit_texts=rewritten_texts,
            unit_segments=rewritten_segments,
            atoms=atoms,
            policy=policy,
            tokenizer=tokenizer,
            budget=budget,
        )

    def _build_candidate_units(
        self,
        ingest,
        blocks: Sequence[Block],
        atoms: Sequence[Atom],
        policy: CompilePolicy,
    ) -> list[CandidateUnit]:
        """Segments blocks into fine-grained extractive candidate units and binds protected atoms."""
        units: list[CandidateUnit] = []
        order = 0

        # Build bisect index for atoms by start byte
        valid_atoms = [
            (a.sources[0].start, a.sources[0].end, a.atom_id)
            for a in atoms
            if isinstance(a.sources[0], ByteSpan)
        ]
        valid_atoms.sort(key=lambda x: x[0])
        atom_starts = [x[0] for x in valid_atoms]

        def get_bound_atom_ids(start: int, end: int) -> tuple[str, ...]:
            idx = bisect_left(atom_starts, start)
            bound = []
            while idx < len(valid_atoms) and valid_atoms[idx][0] <= end:
                if valid_atoms[idx][1] <= end:
                    bound.append(valid_atoms[idx][2])
                idx += 1
            return tuple(bound)

        for b in blocks:
            # Optionally filter out structural boilerplate
            if policy.filter_boilerplate and is_structural_boilerplate(b.text):
                continue

            b_kind = b.metadata.get("kind", "copy")
            # Prose and quote blocks get sentence segmentation
            if b.kind in (BlockKind.PROSE, BlockKind.QUOTE):
                sentences = segment_sentences(b.text)
                for s in sentences:
                    st = s.text.strip()
                    b_src = b.sources[0] if b.sources else None
                    b_start_byte = b_src.start if isinstance(b_src, ByteSpan) else 0
                    c_start, _ = ingest.source_map.byte_to_char_range(b_start_byte, b_start_byte)
                    s_char_start = c_start + s.start_char
                    s_char_end = c_start + s.end_char

                    span = clean_char_to_byte_span(
                        ingest, s_char_start, min(s_char_end, len(ingest.clean_text))
                    )
                    bound_atom_ids = get_bound_atom_ids(span.start, span.end)

                    # Preserve short factual lines if they contain bound atoms or numbers
                    if policy.filter_boilerplate:
                        if is_structural_boilerplate(st):
                            continue
                        if len(st) < 10 and not bound_atom_ids and not any(c.isdigit() for c in st):
                            continue

                    units.append(
                        CandidateUnit(
                            unit_id=f"unit_{len(units):04d}",
                            block_id=b.block_id,
                            sources=(span,),
                            text=s.text,
                            kind=b_kind,
                            atom_ids=bound_atom_ids,
                            source_order=order,
                        )
                    )
                    order += 1
            else:
                bt = b.text.strip()
                b_src = b.sources[0] if b.sources else None
                b_start = b_src.start if isinstance(b_src, ByteSpan) else 0
                b_end = b_src.end if isinstance(b_src, ByteSpan) else 0
                bound_atom_ids = get_bound_atom_ids(b_start, b_end)

                if policy.filter_boilerplate:
                    if is_structural_boilerplate(bt):
                        continue
                    if len(bt) < 10 and not bound_atom_ids and not any(c.isdigit() for c in bt):
                        continue

                units.append(
                    CandidateUnit(
                        unit_id=f"unit_{len(units):04d}",
                        block_id=b.block_id,
                        sources=b.sources,
                        text=b.text,
                        kind=b_kind,
                        atom_ids=bound_atom_ids,
                        source_order=order,
                    )
                )
                order += 1

        return units


def summarize(text: str) -> str:
    """Convenience function: compress input text to its natural information density floor.

    Requires NO token budget argument. Automatically prunes narrative scaffolding
    and reaches optimal density with zero external LLM calls.
    """
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    policy = CompilePolicy(
        mode=CompileMode.COMPACT,
        discourse_pruning=True,
        filter_boilerplate=True,
    )
    result = compiler.compile(text, policy=policy)
    return result.text
