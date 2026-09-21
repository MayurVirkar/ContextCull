"""Manifest generation and output rendering."""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Sequence

from contextcull.ingest.decoder import IngestionResult
from contextcull.ir.models import (
    Atom,
    CandidateUnit,
    CompilePolicy,
    CompileResult,
    OutputSegment,
    TokenBudget,
)
from contextcull.tokenize.profile import TokenizerProfile


def _source_manifest(ingest: IngestionResult, extracted_byte_length: int) -> dict[str, object]:
    """Builds the manifest `source` block, honestly declaring what byte spans index into.

    For binary formats (PDF/DOCX), `ingest.raw_file_bytes` holds the original file and
    `ingest.source_map.raw_bytes` holds the UTF-8 bytes of the text EXTRACTED from it —
    output_segments' byte spans index the latter, not the former. Recording
    `span_basis: "extracted_text"` (vs "raw_bytes" for plain-text sources) plus a hash of
    the extracted text lets `contextcull validate` re-extract and check spans honestly,
    instead of silently comparing them against the wrong bytes.
    """
    if ingest.raw_file_bytes is None:
        return {
            "document_id": ingest.document_id,
            "byte_length": extracted_byte_length,
            "format": "text",
            "span_basis": "raw_bytes",
        }

    from contextcull.parse.docx import is_docx
    from contextcull.parse.pdf import is_pdf

    if is_pdf(ingest.raw_file_bytes):
        fmt = "pdf"
    elif is_docx(ingest.raw_file_bytes):
        fmt = "docx"
    else:
        fmt = "binary"

    return {
        "document_id": ingest.document_id,
        "byte_length": extracted_byte_length,
        "format": fmt,
        "span_basis": "extracted_text",
        "extracted_text_sha256": f"sha256:{hashlib.sha256(ingest.source_map.raw_bytes).hexdigest()}",
    }


def render_and_manifest(
    ingest: IngestionResult,
    units: Sequence[CandidateUnit],
    unit_texts: Sequence[str],
    unit_segments: Sequence[Sequence[OutputSegment]],
    atoms: Sequence[Atom],
    policy: CompilePolicy,
    tokenizer: TokenizerProfile,
    budget: TokenBudget | None = None,
    diagnostics: Sequence[str] = (),
) -> CompileResult:
    """Renders final context string and builds the versioned provenance manifest."""
    rendered_parts: list[str] = []
    final_segments: list[OutputSegment] = []

    current_byte_offset = 0

    for idx, (_unit, text, segments) in enumerate(zip(units, unit_texts, unit_segments)):
        if idx > 0:
            rendered_parts.append("\n")
            current_byte_offset += 1

        part_bytes = text.encode("utf-8")
        part_len = len(part_bytes)

        # Re-offset segment boundaries relative to rendered output
        for seg in segments:
            seg_len = seg.output_end - seg.output_start
            final_segments.append(
                OutputSegment(
                    output_start=current_byte_offset,
                    output_end=current_byte_offset + seg_len,
                    kind=seg.kind,
                    sources=seg.sources,
                    rule_id=seg.rule_id,
                    text=seg.text or text,
                )
            )

        rendered_parts.append(text)
        current_byte_offset += part_len

    rendered_text = "".join(rendered_parts)

    # Metrics
    input_bytes = len(ingest.source_map.raw_bytes)
    output_bytes = len(rendered_text.encode("utf-8"))
    input_tokens = tokenizer.count_tokens(ingest.clean_text)
    output_tokens = tokenizer.count_tokens(rendered_text)

    compression = 1.0 - (output_tokens / max(1, input_tokens))

    # Required atoms (hard invariants: CVEs, IPs, UUIDs, SHAs, user required terms)
    required_atoms = [a for a in atoms if a.required]
    retained_required = [
        a
        for a in required_atoms
        if a.surface in rendered_text
        or (a.kind == "quantity" and a.canonical and a.canonical in rendered_text.lower())
    ]
    required_coverage = (
        len(retained_required) / max(1, len(required_atoms)) if required_atoms else 1.0
    )

    # Total syntactic/modal atoms
    retained_atoms = [
        a for a in atoms if a.surface in rendered_text or a.canonical in rendered_text.lower()
    ]
    total_atom_coverage = len(retained_atoms) / max(1, len(atoms))

    copy_count = sum(1 for s in final_segments if s.kind == "copy")
    rewrite_count = sum(1 for s in final_segments if s.kind == "rewrite")
    aggregate_count = sum(1 for s in final_segments if s.kind == "aggregate")

    source_manifest = _source_manifest(ingest, input_bytes)

    manifest = {
        "schema_version": "1.0",
        "status": "OK",
        "source": source_manifest,
        "environment": {
            "contextcull_version": "1.0.0",
            "tep_version": "1.0.0",
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "mode": policy.mode.value,
        },
        "tokenizer": {
            "profile": tokenizer.profile_name,
            "exact": tokenizer.is_exact(),
        },
        "metrics": {
            "input_bytes": input_bytes,
            "output_bytes": output_bytes,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "compression_ratio": round(compression, 4),
            "required_atom_coverage": round(required_coverage, 4),
            "retained_required_atoms_count": len(retained_required),
            "total_required_atoms_count": len(required_atoms),
            "total_atom_coverage": round(total_atom_coverage, 4),
            "retained_atoms_count": len(retained_atoms),
            "total_atoms_count": len(atoms),
            "copy_segments_count": copy_count,
            "rewrite_segments_count": rewrite_count,
            "aggregate_segments_count": aggregate_count,
        },
        "output_segments": [s.to_dict() for s in final_segments],
        "atoms": [a.to_dict() for a in retained_required],
        "diagnostics": list(diagnostics),
    }

    return CompileResult(
        status="OK",
        text=rendered_text,
        manifest=manifest,
        metrics=manifest["metrics"],
        diagnostics=tuple(diagnostics),
    )
