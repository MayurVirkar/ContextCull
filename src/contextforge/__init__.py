"""ContextForge: Deterministic Context Compiler & Pre-Processor for Frontier LLMs.

Powered by the Token-Efficiency Protocol (TEP).
"""

from __future__ import annotations

from tep import (
    api,
    closure,
    detect,
    errors,
    features,
    ingest,
    ir,
    parse,
    rank,
    render,
    rewrite,
    route,
    segment,
    select,
    tokenize,
    validate,
)
from tep.api import ContextCompiler, summarize
from tep.ir.models import (
    Atom,
    Block,
    BlockKind,
    CandidateUnit,
    CompileMode,
    CompilePolicy,
    CompileResult,
    OutputSegment,
    TokenBudget,
)
from tep.ir.spans import ByteSpan, SourceMap, SourceRef

__version__ = "0.1.0"

__all__ = [
    "Atom",
    "Block",
    "BlockKind",
    "ByteSpan",
    "CandidateUnit",
    "CompileMode",
    "CompilePolicy",
    "CompileResult",
    "ContextCompiler",
    "OutputSegment",
    "SourceMap",
    "SourceRef",
    "TokenBudget",
    "api",
    "closure",
    "detect",
    "errors",
    "features",
    "ingest",
    "ir",
    "parse",
    "rank",
    "render",
    "rewrite",
    "route",
    "segment",
    "select",
    "summarize",
    "tokenize",
    "validate",
]
