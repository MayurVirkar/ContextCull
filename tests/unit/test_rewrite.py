"""Unit tests for transactional rewriting engine."""

from contextcull.api import ContextCompiler
from contextcull.ir.models import CompileMode, CompilePolicy, TokenBudget


def test_strict_mode_no_rewrites():
    doc = "The database configuration failed because of timeout."
    compiler = ContextCompiler(mode=CompileMode.STRICT)
    budget = TokenBudget(tokens=50, profile="openai:cl100k_base")
    policy = CompilePolicy(mode=CompileMode.STRICT)

    result = compiler.compile(doc, budget=budget, policy=policy)
    assert result.ok
    # In strict mode, 'database' must NOT be rewritten to 'db'
    assert "database" in result.text


def test_compact_mode_verified_abbreviations():
    doc = "The database configuration and repository infrastructure were initialized."
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    budget = TokenBudget(tokens=50, profile="openai:cl100k_base")
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    result = compiler.compile(doc, budget=budget, policy=policy)
    assert result.ok
    # In compact mode, abbreviations like db / cfg / repo may be committed if token savings occur
    # The result must be valid and source-mapped
    assert result.manifest["status"] == "OK"
