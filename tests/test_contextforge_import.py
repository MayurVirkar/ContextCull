"""Verifies that contextforge top-level package and aliases work identically to tep."""

import contextforge
from contextforge import CompileMode, ContextCompiler


def test_contextforge_exports():
    assert hasattr(contextforge, "ContextCompiler")
    assert hasattr(contextforge, "summarize")
    assert hasattr(contextforge, "CompileMode")
    assert hasattr(contextforge, "CompilePolicy")
    assert hasattr(contextforge, "TokenBudget")


def test_contextforge_compiler_execution():
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile("Test execution: CVE-2026-1234 on IP 10.0.0.1.")

    assert result.ok
    assert "CVE-2026-1234" in result.text
    assert "10.0.0.1" in result.text
