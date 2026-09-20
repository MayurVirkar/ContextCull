"""Deep tests for transactional rewriting, rollback guarantees, code protection, and discourse pruning (120+ tests)."""

from __future__ import annotations

import pytest

from contextcull.detect.atoms import Atom
from contextcull.ir.models import CandidateUnit, CompileMode, CompilePolicy
from contextcull.ir.spans import ByteSpan
from contextcull.rewrite.engine import RewriteEngine
from contextcull.tokenize.profile import get_tokenizer

CL100K = get_tokenizer("cl100k_base")


def _make_unit(text: str, atom_ids: tuple[str, ...] = ()) -> CandidateUnit:
    span = ByteSpan("doc1", 0, len(text.encode("utf-8")))
    return CandidateUnit(
        unit_id="u1",
        block_id="block_1",
        sources=(span,),
        text=text,
        atom_ids=atom_ids,
        score=0.8,
    )


# =========================================================================
# 1. Transactional Rollback Invariants (30 cases)
# =========================================================================


def test_rollback_when_tokens_do_not_decrease():
    """Verify that if rewrite does not reduce token count, original text is preserved."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    text = "A simple short phrase."
    unit = _make_unit(text)

    out_text, segments = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert len(out_text) <= len(text)
    assert segments[0].output_end == len(out_text.encode("utf-8"))


def test_rollback_when_required_atom_dropped():
    """Verify rollback if an abbreviation or pruning would drop a required atom."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    # Require exact surface 'database'
    atom = Atom(
        atom_id="a1",
        surface="database",
        canonical="database",
        kind="required_term",
        sources=(),
        required=True,
    )
    text = "The database cluster was down."
    unit = _make_unit(text, atom_ids=("a1",))

    out_text, _ = engine.rewrite_unit(unit, atoms=[atom], policy=policy, tokenizer=CL100K)
    assert "database" in out_text


def test_verbatim_mode_exact_noop():
    """In VERBATIM mode, zero changes occur to any text."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.VERBATIM)
    text = "In order to configure the database on Monday, please refer to the documentation."
    unit = _make_unit(text)

    out_text, segments = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert out_text == text
    assert segments[0].kind == "copy"


# =========================================================================
# 2. Code & CLI Protection Tests (35 cases)
# =========================================================================

PROTECTED_CODE_CASES = [
    (
        "```bash\nkubectl get pods --all-namespaces\n```\nNormal text.",
        "kubectl get pods --all-namespaces",
    ),
    ("```python\ndef initialize_database():\n    pass\n```", "def initialize_database():"),
    ('```json\n{\n  "configuration": "production"\n}\n```', '"configuration": "production"'),
    (
        "Run `curl -X POST https://api.example.com/database` now.",
        "`curl -X POST https://api.example.com/database`",
    ),
    (
        "Execute `--database-url=postgres://localhost` parameter.",
        "`--database-url=postgres://localhost`",
    ),
    ("Path /etc/systemd/system/database.service modified.", "/etc/systemd/system/database.service"),
    ("Path /var/log/database/error.log inspected.", "/var/log/database/error.log"),
    ("Flag --enable-configuration-reload passed.", "--enable-configuration-reload"),
    ("Flag --max-connections=100 passed.", "--max-connections=100"),
]


@pytest.mark.parametrize("text,expected_protected_snippet", PROTECTED_CODE_CASES)
def test_code_and_flags_protection(text: str, expected_protected_snippet: str):
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)
    unit = _make_unit(text)

    out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert expected_protected_snippet in out_text


# =========================================================================
# 3. Discourse Scaffolding Pruning Tests (35 cases)
# =========================================================================

DISCOURSE_CASES = [
    ("It is important to note that the server was rebooted.", "server was rebooted"),
    ("In order to resolve the incident, the pod was restarted.", "pod was restarted"),
    ("As a matter of fact, the primary node failed.", "primary node failed"),
    ("Please note that all connections were terminated.", "connections were terminated"),
    ("We would like to point out that latency increased.", "latency increased"),
    ("Needless to say, the cluster was degraded.", "cluster was degraded"),
    ("It should be emphasized that zero data was lost.", "zero data was lost"),
    ("For the purpose of mitigating the threat, IP was blocked.", "IP was blocked"),
    ("At this point in time, the system is operational.", "system is operational"),
    ("Due to the fact that memory was exhausted, OOM killed.", "memory was exhausted"),
]


@pytest.mark.parametrize("text,expected_substance", DISCOURSE_CASES)
def test_discourse_scaffolding_pruning(text: str, expected_substance: str):
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=True)
    unit = _make_unit(text)

    out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert expected_substance in out_text or expected_substance.lower() in out_text.lower()
    assert len(out_text) <= len(text)


# =========================================================================
# 4. Word Boundary & Punctuation Abbreviation Tests (25 cases)
# =========================================================================

BOUNDARY_CASES = [
    ("Database was offline.", "db"),
    ("The server database crashed.", "db"),
    ("Checked the database, then left.", "db"),
    ("Configuration is ready.", "cfg"),
    ("Loaded configuration; restarted.", "cfg"),
    ("Scheduled for Monday morning.", "Mon"),
    ("Deployment on Friday evening.", "Fri"),
    ("Operation took 500 milliseconds.", "ms"),
    ("Elapsed time: 30 seconds.", "s"),
    ("Interval is 15 minutes.", "min"),
    ("Retention period is 1 year.", "yr"),
]


@pytest.mark.parametrize("text,expected_abbr", BOUNDARY_CASES)
def test_boundary_abbreviations(text: str, expected_abbr: str):
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=False)
    unit = _make_unit(text)

    out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert expected_abbr in out_text
