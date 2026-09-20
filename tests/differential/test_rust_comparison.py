"""Differential testing: compare Python tep compiler against Rust tep-test binary."""

import subprocess
from pathlib import Path

import pytest

from tep.api import ContextCompiler
from tep.ir.models import CompileMode, CompilePolicy, TokenBudget

RUST_BIN = Path("/home/mayur/projects/Summarizer/target/release/tep-test")


def run_rust_tep(text: str) -> str:
    if not RUST_BIN.exists():
        pytest.skip(f"Rust binary not found at {RUST_BIN}")
    proc = subprocess.run(
        [str(RUST_BIN)],
        input=text,
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


def test_differential_cargo_test_log():
    raw_cargo = """running 12 tests
test auth::test_login ... ok
test auth::test_token_expiry ... FAILED
test auth::test_logout ... ok

failures:

---- auth::test_token_expiry stdout ----
thread 'auth::test_token_expiry' panicked at src/auth/token.rs:88:5:
assertion `left == right` failed
  left: 403
 right: 401

failures:
    auth::test_token_expiry

test result: FAILED. 11 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.04s
"""
    # 1. Run Rust binary
    rust_out = run_rust_tep(raw_cargo)
    assert "auth::test_token_expiry" in rust_out

    # 2. Run Python TEP
    compiler = ContextCompiler(mode=CompileMode.STRICT)
    budget = TokenBudget(tokens=500, profile="openai:cl100k_base")
    policy = CompilePolicy(mode=CompileMode.STRICT, preserve_failures=True)
    py_result = compiler.compile(raw_cargo, budget=budget, policy=policy)

    assert py_result.ok
    assert "auth::test_token_expiry" in py_result.text
    assert "src/auth/token.rs:88:5" in py_result.text
    assert "401" in py_result.text
    assert "403" in py_result.text


def test_differential_email():
    raw_email = """From: Sarah Connor <sarah@skynet.org>
Subject: Security Audit Findings

Hi Mayur,
Following the external security audit conducted on Monday, we have decided to revoke all long-lived API tokens.
Could you please rotate the database production credentials and update the Kubernetes secrets by Thursday November 12th at 5 PM?
Also, do we need to schedule a maintenance window for this migration?

Best regards,
Sarah
"""
    rust_out = run_rust_tep(raw_email)
    assert "Sarah Connor" in rust_out

    compiler = ContextCompiler(mode=CompileMode.STRICT)
    budget = TokenBudget(tokens=500, profile="openai:cl100k_base")
    policy = CompilePolicy(mode=CompileMode.STRICT)
    py_result = compiler.compile(raw_email, budget=budget, policy=policy)

    assert py_result.ok
    assert "Sarah Connor" in py_result.text
    assert "Security Audit Findings" in py_result.text
    assert "Kubernetes" in py_result.text
    assert "revoke" in py_result.text or "tokens" in py_result.text


def test_differential_article_retention():
    article = """# Global Semiconductor Supply Chain Shifts

The global semiconductor manufacturing landscape is undergoing a structural realignment with over $150 billion in government subsidies allocated across the United States and the European Union. In an unexpected policy shift, domestic fabrication investments surged by 42% year-over-year.

Leading chip manufacturers have broken ground on advanced 2nm fabrication facilities in Ohio and Dresden. However, ongoing equipment shortages and skilled labor deficits have pushed projected commercial production dates from late 2025 to mid-2027.

Industry analysts emphasize that while capital expenditure remains historic, geopolitical export controls and supply bottlenecks will continue to restrict leading-edge wafer output through 2028.
"""
    rust_out = run_rust_tep(article)
    assert "$150 billion" in rust_out or "42%" in rust_out

    compiler = ContextCompiler(mode=CompileMode.STRICT)
    budget = TokenBudget(tokens=300, profile="openai:cl100k_base")
    policy = CompilePolicy(mode=CompileMode.STRICT)
    py_result = compiler.compile(article, budget=budget, policy=policy)

    assert py_result.ok
    assert "$150 billion" in py_result.text or "42%" in py_result.text
    assert "Semiconductor" in py_result.text
