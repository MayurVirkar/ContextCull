"""Deterministic ContextCull Context Compiler."""

from contextcull.api import ContextCompiler, summarize
from contextcull.errors import (
    BudgetUnsafeError,
    ContextCullError,
    InvariantViolationError,
    ParseError,
    SourceMapError,
    TepError,
)
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

__version__ = "1.0.0"

__all__ = [
    "Atom",
    "Block",
    "BlockKind",
    "BudgetUnsafeError",
    "ByteSpan",
    "CandidateUnit",
    "CompileMode",
    "CompilePolicy",
    "CompileResult",
    "ContextCompiler",
    "ContextCullError",
    "InvariantViolationError",
    "OutputSegment",
    "ParseError",
    "SourceMap",
    "SourceMapError",
    "SourceRef",
    "TepError",
    "TokenBudget",
    "summarize",
]
