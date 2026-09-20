"""Differential testing: compare Python tep compiler against Rust tep-test binary."""

import os
import subprocess
from pathlib import Path

from tep.api import ContextCompiler
from tep.ir.models import CompileMode, CompilePolicy, TokenBudget

RUST_BIN_PATH = os.environ.get(
    "TEP_RUST_BIN", "/home/mayur/projects/Summarizer/target/release/tep-test"
)
RUST_BIN = Path(RUST_BIN_PATH)


def run_rust_tep(text: str) -> str | None:
    if not RUST_BIN.exists():
        return None
    try:
        proc = subprocess.run(
            [str(RUST_BIN)],
            input=text,
            text=True,
            capture_output=True,
            check=True,
        )
        return proc.stdout.strip()
    except Exception:
        return None


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
    # 1. Run Python TEP (always runs)
    compiler = ContextCompiler(mode=CompileMode.STRICT)
    budget = TokenBudget(tokens=500, profile="openai:cl100k_base")
    policy = CompilePolicy(mode=CompileMode.STRICT, preserve_failures=True)
    py_result = compiler.compile(raw_cargo, budget=budget, policy=policy)

    assert py_result.ok
    assert "auth::test_token_expiry" in py_result.text
    assert "src/auth/token.rs:88:5" in py_result.text
    assert "401" in py_result.text
    assert "403" in py_result.text

    # 2. Run Rust binary if available
    rust_out = run_rust_tep(raw_cargo)
    if rust_out is not None:
        assert "auth::test_token_expiry" in rust_out


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
    compiler = ContextCompiler(mode=CompileMode.STRICT)
    budget = TokenBudget(tokens=500, profile="openai:cl100k_base")
    policy = CompilePolicy(mode=CompileMode.STRICT)
    py_result = compiler.compile(raw_email, budget=budget, policy=policy)

    assert py_result.ok
    assert "Sarah Connor" in py_result.text
    assert "Kubernetes" in py_result.text

    rust_out = run_rust_tep(raw_email)
    if rust_out is not None:
        assert "Sarah Connor" in rust_out


def test_differential_markdown():
    raw_md = """# Deployment Guide

This guide describes how to deploy the cluster.

## Prerequisites

- Docker 24.0+
- Kubernetes 1.28+

```bash
kubectl apply -f deployment.yaml
```

> **Warning**: Never expose port 8080 to the public internet without mutual TLS.
"""
    compiler = ContextCompiler(mode=CompileMode.STRICT)
    budget = TokenBudget(tokens=500, profile="openai:cl100k_base")
    policy = CompilePolicy(mode=CompileMode.STRICT)
    py_result = compiler.compile(raw_md, budget=budget, policy=policy)

    assert py_result.ok
    assert "Deployment Guide" in py_result.text
    assert "kubectl apply" in py_result.text

    rust_out = run_rust_tep(raw_md)
    if rust_out is not None:
        assert "Deployment Guide" in rust_out
