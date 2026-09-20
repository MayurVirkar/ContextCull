"""Verifies that contextcull top-level package and aliases work identically to contextcull."""

import contextcull
from contextcull import CompileMode, ContextCompiler


def test_contextcull_exports():
    assert hasattr(contextcull, "ContextCompiler")
    assert hasattr(contextcull, "summarize")
    assert hasattr(contextcull, "CompileMode")
    assert hasattr(contextcull, "CompilePolicy")
    assert hasattr(contextcull, "TokenBudget")


def test_contextcull_compiler_execution():
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile("Test execution: CVE-2026-1234 on IP 10.0.0.1.")

    assert result.ok
    assert "CVE-2026-1234" in result.text
    assert "10.0.0.1" in result.text
