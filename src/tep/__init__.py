"""Deterministic Token-Efficiency Protocol (TEP) Context Compiler."""

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
from tep.ir.spans import ByteSpan, PageRegion, SourceMap, SourceRef

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
    "PageRegion",
    "SourceMap",
    "SourceRef",
    "TokenBudget",
    "summarize",
]
