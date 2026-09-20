"""Unit tests for budget constraints and fail-closed safety."""

from tep.api import ContextCompiler
from tep.ir.models import CompileMode, CompilePolicy, TokenBudget


def test_budget_unsafe_fail_closed():
    doc = """
    CRITICAL INCIDENT REPORT:
    The service experienced a fatal crash due to ReferenceFileSystem corruption.
    Privilege escalation compromised /etc/sudoers.d.
    The database credentials were stolen using forged JWT tokens.
    """
    compiler = ContextCompiler(mode=CompileMode.STRICT)

    # Impose an impossibly small budget of 5 tokens when mandatory terms are required
    budget = TokenBudget(tokens=5, profile="openai:cl100k_base", hard_budget=True)
    policy = CompilePolicy(
        mode=CompileMode.STRICT,
        required_terms=("ReferenceFileSystem", "/etc/sudoers.d", "JWT"),
    )

    result = compiler.compile(doc, budget=budget, policy=policy)
    assert not result.ok
    assert result.status == "TARGET_BUDGET_UNSAFE"
    assert result.metrics["minimum_safe_tokens"] > 5
    assert len(result.diagnostics) > 0


def test_adequate_budget_success():
    doc = """
    # System Overview
    The primary database runs on PostgreSQL.
    Cache layer uses Redis cluster with 3 replicas.
    All HTTP endpoints require valid JWT authentication.
    """
    compiler = ContextCompiler(mode=CompileMode.STRICT)
    budget = TokenBudget(tokens=100, profile="openai:cl100k_base", hard_budget=True)
    policy = CompilePolicy(
        mode=CompileMode.STRICT,
        required_terms=("JWT", "PostgreSQL"),
    )

    result = compiler.compile(doc, budget=budget, policy=policy)
    assert result.ok
    assert result.status == "OK"
    assert "JWT" in result.text
    assert "PostgreSQL" in result.text
