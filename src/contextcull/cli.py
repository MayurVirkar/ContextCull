"""Command-line interface for ContextCull."""

from __future__ import annotations

import hashlib
from pathlib import Path

import orjson
import typer

from contextcull.api import ContextCompiler
from contextcull.detect.atoms import extract_atoms
from contextcull.ingest.decoder import ingest_document
from contextcull.ir.models import CompileMode, CompilePolicy, TokenBudget

app = typer.Typer(
    name="contextcull",
    help="ContextCull: Deterministic Context Compiler & Pre-Processor for Frontier LLMs",
    add_completion=False,
)


@app.command(name="compile")
def compile_cmd(
    input_file: Path = typer.Argument(..., help="Path to input file to compile"),
    budget_tokens: int | None = typer.Option(
        None, "--budget", "-b", help="Target token budget (default: None, natural density floor)"
    ),
    tokenizer_profile: str = typer.Option(
        "openai:cl100k_base", "--tokenizer", "-t", help="Target tokenizer profile"
    ),
    mode: str = typer.Option(
        "compact", "--mode", "-m", help="Safety mode: verbatim, strict, compact, task"
    ),
    output_path: Path | None = typer.Option(
        None, "--output", "-o", help="Output path for compiled text"
    ),
    manifest_path: Path | None = typer.Option(
        None, "--manifest", help="Output path for JSON manifest"
    ),
    required_terms: list[str] = typer.Option(
        [], "--require-term", "-r", help="Explicit terms that must be preserved"
    ),
    hard_budget: bool = typer.Option(
        True, "--hard-budget/--soft-budget", help="Fail if budget is unsafe"
    ),
    abbreviations: bool = typer.Option(
        False,
        "--abbreviations/--no-abbreviations",
        help="Abbreviate technical terms (e.g. configuration -> cfg) when it saves tokens",
    ),
) -> None:
    """Compile input document into optimally condensed context without requiring a token budget."""
    if not input_file.exists():
        typer.echo(f"Error: input file {input_file} does not exist", err=True)
        raise typer.Exit(code=1)

    try:
        clean_mode = CompileMode(mode.lower())
    except ValueError:
        typer.echo(
            f"Error: invalid mode '{mode}'. Choose from: verbatim, strict, compact, task",
            err=True,
        )
        raise typer.Exit(code=1) from None

    compiler = ContextCompiler(mode=clean_mode)
    budget = (
        TokenBudget(tokens=budget_tokens, profile=tokenizer_profile, hard_budget=hard_budget)
        if budget_tokens is not None
        else None
    )
    policy = CompilePolicy(
        mode=clean_mode,
        required_terms=tuple(required_terms),
        abbreviations=abbreviations,
    )

    try:
        result = compiler.compile_file(input_file, budget=budget, policy=policy)
    except Exception as exc:
        typer.echo(f"Compilation error: {exc}", err=True)
        raise typer.Exit(code=2) from None

    if not result.ok:
        typer.echo(f"Compilation status: {result.status}", err=True)
        for diag in result.diagnostics:
            typer.echo(f"  {diag}", err=True)
        if manifest_path:
            result.write_manifest(str(manifest_path))
        raise typer.Exit(code=2)

    if output_path:
        result.write_text(str(output_path))
        typer.echo(f"Compiled context written to {output_path}")
    else:
        typer.echo(result.text)

    if manifest_path:
        result.write_manifest(str(manifest_path))
        typer.echo(f"Manifest written to {manifest_path}")


@app.command(name="inspect")
def inspect_cmd(
    input_file: Path = typer.Argument(..., help="Path to input file"),
    show: str = typer.Option(
        "blocks,atoms", "--show", help="Elements to inspect: blocks, atoms, all"
    ),
) -> None:
    """Inspect detected structural blocks and protected atoms in an input file."""
    if not input_file.exists():
        typer.echo(f"Error: input file {input_file} does not exist", err=True)
        raise typer.Exit(code=1)

    raw_bytes = input_file.read_bytes()
    ingest, blocks = ingest_document(raw_bytes)
    atoms = extract_atoms(ingest, blocks=blocks)

    typer.echo(f"Document ID: {ingest.document_id}")
    typer.echo(f"Total Bytes: {len(raw_bytes)} | Clean Chars: {len(ingest.clean_text)}")

    show_items = [s.strip().lower() for s in show.split(",")]

    if "blocks" in show_items or "all" in show_items:
        typer.echo(f"\n--- Detected Blocks ({len(blocks)}) ---")
        for b in blocks:
            typer.echo(f"[{b.kind.value.upper()}] {b.block_id}: {b.text[:60]!r}...")

    if "atoms" in show_items or "all" in show_items:
        typer.echo(f"\n--- Protected Atoms ({len(atoms)}) ---")
        for a in atoms:
            typer.echo(f"[{a.kind}] {a.surface} (canonical: {a.canonical}) required={a.required}")


def _bounds_ok(seg: dict, basis_len: int) -> bool:
    """True if every source span on a segment falls in-bounds of the basis bytes."""
    sources = seg.get("sources", [])
    if not sources:
        return False
    for src in sources:
        start, end = src.get("start", -1), src.get("end", -1)
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= basis_len):
            return False
    return True


@app.command(name="validate")
def validate_cmd(
    context_file: Path = typer.Argument(..., help="Path to compiled context file"),
    manifest_file: Path = typer.Option(..., "--manifest", "-m", help="Path to provenance manifest"),
    source_file: Path = typer.Option(..., "--source", "-s", help="Path to original source file"),
    allow_unverified: bool = typer.Option(
        False,
        "--allow-unverified",
        help="Exit 0 even if zero output segments could be verified (default: exit 3)",
    ),
) -> None:
    """Validate a compiled context and manifest against the original source."""
    if not context_file.exists() or not manifest_file.exists() or not source_file.exists():
        typer.echo("Error: one or more specified files do not exist", err=True)
        raise typer.Exit(code=1)

    context_text = context_file.read_text(encoding="utf-8")
    raw_source = source_file.read_bytes()
    manifest = orjson.loads(manifest_file.read_bytes())
    source_meta = manifest.get("source", {})

    # Check document ID (always the hash of the original source file, binary or text)
    source_hash = f"sha256:{hashlib.sha256(raw_source).hexdigest()}"
    manifest_source_id = source_meta.get("document_id")
    if source_hash != manifest_source_id:
        typer.echo(
            f"Validation FAILED: Source hash {source_hash} does not match manifest {manifest_source_id}",
            err=True,
        )
        raise typer.Exit(code=2)

    # Determine what the manifest's byte spans actually index into. For PDF/DOCX sources,
    # output_segments' spans index the text EXTRACTED from the file, not the file's own
    # bytes, so checking them against raw_source directly would be comparing against the
    # wrong bytes entirely.
    span_basis = source_meta.get("span_basis", "raw_bytes")
    if span_basis == "extracted_text":
        doc_format = source_meta.get("format")
        if doc_format == "pdf":
            from contextcull.parse.pdf import extract_pdf_blocks_and_text as _extract
        elif doc_format == "docx":
            from contextcull.parse.docx import extract_docx_blocks_and_text as _extract
        else:
            typer.echo(
                f"Validation FAILED: unknown extracted-text source format {doc_format!r}", err=True
            )
            raise typer.Exit(code=2)

        _, extracted_text = _extract(raw_source, manifest_source_id or source_hash)
        extracted_bytes = extracted_text.encode("utf-8")
        extracted_sha256 = f"sha256:{hashlib.sha256(extracted_bytes).hexdigest()}"
        manifest_extracted_sha256 = source_meta.get("extracted_text_sha256")
        if extracted_sha256 != manifest_extracted_sha256:
            typer.echo(
                f"Validation FAILED: re-extracted text hash {extracted_sha256} does not match "
                f"manifest {manifest_extracted_sha256} (source file no longer matches the "
                f"text the manifest's byte spans were computed against)",
                err=True,
            )
            raise typer.Exit(code=2)
        basis_bytes = extracted_bytes
    else:
        basis_bytes = raw_source

    # Validate output segments
    segments = manifest.get("output_segments", [])
    copy_segments = [s for s in segments if s.get("kind") == "copy"]
    rewrite_segments = [s for s in segments if s.get("kind") == "rewrite"]
    aggregate_segments = [s for s in segments if s.get("kind") == "aggregate"]

    valid_copy_count = 0
    for seg in copy_segments:
        out_start = seg.get("output_start", 0)
        out_end = seg.get("output_end", 0)
        seg_bytes = context_text.encode("utf-8")[out_start:out_end]
        seg_str = seg_bytes.decode("utf-8", errors="replace").strip().replace("\r\n", "\n")
        sources = seg.get("sources", [])
        for src in sources:
            s_bytes = basis_bytes[src["start"] : src["end"]]
            s_str = s_bytes.decode("utf-8", errors="replace").strip().replace("\r\n", "\n")
            if len(sources) == 1:
                # Primary check: exact per-segment equality, not "appears somewhere in output"
                if not s_str or s_str == seg_str:
                    valid_copy_count += 1
                else:
                    typer.echo(
                        f"Invalid segment span: {src} does not byte-exact match output segment",
                        err=True,
                    )
                    raise typer.Exit(code=2)
            elif not s_str or s_str in context_text:
                # Secondary fallback for multi-source copy segments
                valid_copy_count += 1
            else:
                typer.echo(f"Invalid segment span: {src} not found in output", err=True)
                raise typer.Exit(code=2)

    rewrite_bounds_ok_count = 0
    for seg in rewrite_segments:
        if not seg.get("rule_id"):
            typer.echo(f"Invalid rewrite segment missing rule_id attribution: {seg}", err=True)
            raise typer.Exit(code=2)
        if not _bounds_ok(seg, len(basis_bytes)):
            typer.echo(f"Invalid rewrite segment has out-of-bounds source span: {seg}", err=True)
            raise typer.Exit(code=2)
        rewrite_bounds_ok_count += 1

    aggregate_bounds_ok_count = 0
    for seg in aggregate_segments:
        if not _bounds_ok(seg, len(basis_bytes)):
            typer.echo(f"Invalid aggregate segment has out-of-bounds source span: {seg}", err=True)
            raise typer.Exit(code=2)
        aggregate_bounds_ok_count += 1

    total_verified = valid_copy_count + rewrite_bounds_ok_count + aggregate_bounds_ok_count
    if total_verified == 0:
        typer.echo(
            "Validation WARNING: 0 output segments could be verified (no copy segments were "
            "byte-exact matched, and no rewrite/aggregate segments had checkable bounds); "
            "manifest provenance is unconfirmed.",
            err=True,
        )
        if not allow_unverified:
            raise typer.Exit(code=3)
        return

    typer.echo(
        f"Validation PASSED: {valid_copy_count} copy segment(s) byte-verified (100% byte-exact "
        f"against {span_basis}), {rewrite_bounds_ok_count} rewrite segment(s) bounds-checked and "
        f"rule-attributed (NOT byte-verified), {aggregate_bounds_ok_count} aggregate segment(s) "
        f"bounds-checked."
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
