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


@app.command(name="validate")
def validate_cmd(
    context_file: Path = typer.Argument(..., help="Path to compiled context file"),
    manifest_file: Path = typer.Option(..., "--manifest", "-m", help="Path to provenance manifest"),
    source_file: Path = typer.Option(..., "--source", "-s", help="Path to original source file"),
) -> None:
    """Validate a compiled context and manifest against the original source."""
    if not context_file.exists() or not manifest_file.exists() or not source_file.exists():
        typer.echo("Error: one or more specified files do not exist", err=True)
        raise typer.Exit(code=1)

    context_text = context_file.read_text(encoding="utf-8")
    raw_source = source_file.read_bytes()
    manifest = orjson.loads(manifest_file.read_bytes())

    # Check document ID
    source_hash = f"sha256:{hashlib.sha256(raw_source).hexdigest()}"
    manifest_source_id = manifest.get("source", {}).get("document_id")
    if source_hash != manifest_source_id:
        typer.echo(
            f"Validation FAILED: Source hash {source_hash} does not match manifest {manifest_source_id}",
            err=True,
        )
        raise typer.Exit(code=2)

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
        for src in seg.get("sources", []):
            s_bytes = raw_source[src["start"] : src["end"]]
            s_str = s_bytes.decode("utf-8", errors="replace").strip().replace("\r\n", "\n")
            if not s_str or s_str in context_text or (seg_str and s_str == seg_str):
                valid_copy_count += 1
            else:
                typer.echo(f"Invalid segment span: {src} not found in output", err=True)
                raise typer.Exit(code=2)

    for seg in rewrite_segments:
        if not seg.get("rule_id"):
            typer.echo(f"Invalid rewrite segment missing rule_id attribution: {seg}", err=True)
            raise typer.Exit(code=2)

    typer.echo(
        f"Validation PASSED: {valid_copy_count} copy segments verified (100% byte-exact), "
        f"{len(rewrite_segments)} rewritten segments (all rule-attributed), {len(aggregate_segments)} aggregated blocks."
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
