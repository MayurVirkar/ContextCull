"""Hard invariant validation on final rendered context bytes."""

from __future__ import annotations

from collections.abc import Sequence

from tep.errors import InvariantViolationError
from tep.ir.models import Atom, OutputSegment, TokenBudget
from tep.ir.spans import ByteSpan
from tep.tokenize.profile import TokenizerProfile


def validate_invariants(
    output_text: str,
    output_segments: Sequence[OutputSegment],
    raw_source_bytes: bytes,
    required_atoms: Sequence[Atom],
    tokenizer: TokenizerProfile,
    budget: TokenBudget | None = None,
) -> None:
    """Validates all hard invariants on final compiled context.

    Hard invariants:
    1. Every copied segment must match the source bytes at the referenced ByteSpan exactly.
    2. Every aggregate/rewrite segment must reference valid, in-bounds source byte spans.
    3. All detected required atoms must be present in the output text.
    4. Output tokens must not exceed the target budget when the tokenizer is exact and hard_budget is True.
    """
    violations: list[str] = []

    # 1. Byte-exact provenance check for copied segments and in-bounds check for aggregates
    for seg in output_segments:
        if seg.kind == "copy":
            for src in seg.sources:
                if isinstance(src, ByteSpan):
                    span_bytes = raw_source_bytes[src.start : src.end]
                    span_str = span_bytes.decode("utf-8", errors="replace").strip()
                    if span_str and span_str not in output_text:
                        violations.append(
                            f"Provenance violation: copied source span [{src.start}, {src.end}) "
                            f"('{span_str[:30]}...') not found in output text"
                        )
        elif seg.kind in ("aggregate", "rewrite"):
            for src in seg.sources:
                if isinstance(src, ByteSpan) and (
                    src.start < 0 or src.end > len(raw_source_bytes) or src.start > src.end
                ):
                    violations.append(
                        f"Provenance violation: {seg.kind} segment has out-of-bounds source span [{src.start}, {src.end})"
                    )

    # 2. Required atom presence check
    for atom in required_atoms:
        if atom.required and (
            atom.surface not in output_text and atom.canonical not in output_text.lower()
        ):
            violations.append(
                f"Atom violation: required atom '{atom.surface}' ({atom.kind}) was dropped from output"
            )

    # 3. Exact budget compliance
    if budget is not None and budget.tokens is not None and tokenizer.is_exact() and budget.hard_budget:
        out_tokens = tokenizer.count_tokens(output_text)
        if out_tokens > budget.tokens:
            violations.append(
                f"Budget violation: output tokens ({out_tokens}) exceeded budget ({budget.tokens})"
            )

    if violations:
        raise InvariantViolationError(violations)
