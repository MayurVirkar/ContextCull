"""Tests for multi-turn email thread parsing, CRLF line endings, and inverted header orders."""

from tep.api import ContextCompiler
from tep.ir.models import CompileMode


def test_email_thread_multi_turn():
    raw_thread = """From: alice@acme.corp
Subject: [P1] Cache cluster degradation
Date: Mon, 14 Jul 2026 08:00:00 +0000

Team, we are seeing cache latency spike on cluster redis-prod-01.

--------------------------------------------------------------------------------
From: bob@acme.corp
Subject: Re: [P1] Cache cluster degradation
Date: Mon, 14 Jul 2026 08:05:00 +0000

> Team, we are seeing cache latency spike on cluster redis-prod-01.

I have isolated node redis-prod-01-shard-3 and started failover.
"""
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(raw_thread)

    assert result.ok
    assert "alice@acme.corp" in result.text
    assert "bob@acme.corp" in result.text
    assert "redis-prod-01" in result.text
    assert "redis-prod-01-shard-3" in result.text


def test_email_crlf_and_inverted_headers():
    # CRLF with Subject: appearing before From:
    raw_email = (
        "Subject: Critical CVE alert\r\n"
        "From: sec-ops@acme.corp\r\n"
        "Date: Mon, 14 Jul 2026 09:00:00 +0000\r\n"
        "\r\n"
        "Remediate CVE-2026-9999 immediately across all worker nodes.\r\n"
        "Run `aws iam put-role-policy --policy-document file://sec.json`.\r\n"
    )

    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(raw_email)

    assert result.ok
    assert "sec-ops@acme.corp" in result.text
    assert "Critical CVE alert" in result.text
    assert "CVE-2026-9999" in result.text
    # Verify CLI command is intact without flag corruption
    assert "--policy-document" in result.text


def test_rewrite_engine_preserves_code_fences_and_inline_backticks():
    from tep.ir.models import CandidateUnit, CompileMode, CompilePolicy
    from tep.rewrite.engine import RewriteEngine
    from tep.tokenize.profile import get_tokenizer

    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    tok = get_tokenizer("openai:cl100k_base")

    text_with_fences = """Review this documentation:
```sql
SELECT * FROM orders WHERE status = 'pending';
```
And run `aws iam put-role-policy --policy-document file://sec.json` immediately."""

    unit = CandidateUnit(
        unit_id="unit_test",
        block_id="block_test",
        sources=(),
        text=text_with_fences,
    )

    rewritten, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=tok)
    # Verify code fence is NOT corrupted
    assert "```sql\nSELECT * FROM orders WHERE status = 'pending';\n```" in rewritten
    # Verify CLI flag is NOT mangled
    assert "--policy-document" in rewritten
    assert "`aws iam put-role-policy --policy-document file://sec.json`" in rewritten
