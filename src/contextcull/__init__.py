"""Deterministic Token-Efficiency Protocol (TEP) Context Compiler."""

from contextcull.api import ContextCompiler, summarize
from contextcull.ir.models import (
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
from contextcull.ir.spans import ByteSpan, SourceMap, SourceRef

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
    "summarize",
]
