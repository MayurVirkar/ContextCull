"""Regression tests for the rewrite/atoms bug-fix pass:

1. Word abbreviations are opt-in (CompilePolicy.abbreviations=False by default) and never
   mangle ordinary prose, email headers, or proper nouns.
2. The rewrite commit gate requires a STRICT token decrease (no char-length tie-break).
3. Git-SHA and IPv4 atom detection reject scientific notation / random hex / version numbers
   as "hard invariant" required atoms, while still catching real SHAs and IPs.
4. OTHER_NEGATION uses the correct Persian/Arabic "بدون" (not Hebrew vav/final-nun lookalikes).
5. Discourse pruning only re-capitalizes text when a preamble was actually removed.
"""

from __future__ import annotations

import re

from contextcull.detect.atoms import (
    GIT_SHA_SHORT_CANDIDATE_RE,
    OTHER_NEGATION,
    extract_atoms,
    iter_git_sha_spans,
    iter_ipv4_spans,
)
from contextcull.ingest.decoder import ingest_bytes
from contextcull.ir.models import CandidateUnit, CompileMode, CompilePolicy
from contextcull.ir.spans import ByteSpan
from contextcull.rewrite.discourse import prune_discourse_scaffolding
from contextcull.rewrite.engine import RewriteEngine
from contextcull.tokenize.profile import get_tokenizer

CL100K = get_tokenizer("cl100k_base")


def _make_unit(text: str) -> CandidateUnit:
    span = ByteSpan("doc1", 0, len(text.encode("utf-8")))
    return CandidateUnit(unit_id="u1", block_id="block_1", sources=(span,), text=text, score=0.8)


# =========================================================================
# 1. Abbreviations off by default; prose, headers, and proper nouns protected.
# =========================================================================


def test_abbreviations_off_by_default_preserves_literary_prose():
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT)  # abbreviations defaults to False
    text = (
        "It was on a dreary night of November that I beheld the accomplishment of my "
        "toils, and read the constant letters of my dear connection once more."
    )
    unit = _make_unit(text)
    out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert out_text == text


def test_email_header_lines_never_abbreviated():
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=False, abbreviations=True)
    for header in (
        "References: <msg-id-1@example.com> <msg-id-2@example.com>",
        "From: NOI Administrator <noi-admin@example.com>",
    ):
        unit = _make_unit(header)
        out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
        assert out_text == header


def test_security_service_prose_untouched_even_with_abbreviations_on():
    """'security' was pruned from ABBREVIATIONS (ambiguous), and capitalized mid-sentence
    words ("Security Service") are protected as likely proper nouns regardless."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=False, abbreviations=True)
    text = "Police and security forces rushed to the Federal Security Service building."
    unit = _make_unit(text)
    out_text, _ = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert out_text == text


# =========================================================================
# 2. Strictly-decreasing token gate (no char-length tie-break).
# =========================================================================


def test_commit_gate_requires_strict_token_decrease_not_char_length_tie():
    """'Database' -> 'db' has an equal cl100k token count in this sentence (both 4 tokens)
    even though it is shorter in characters -- the old buggy gate committed on the char-length
    tie; the fixed gate must not."""
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=False, abbreviations=True)
    text = "Database was offline."
    assert CL100K.count_tokens(text) == CL100K.count_tokens("db was offline.")
    unit = _make_unit(text)
    out_text, segs = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert out_text == text
    assert segs[0].kind != "rewrite"


def test_commit_gate_still_allows_genuine_token_savings():
    engine = RewriteEngine()
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=False, abbreviations=True)
    text = "It took 30 kilobytes and 500 megabytes to store the cache."
    before = CL100K.count_tokens(text)
    unit = _make_unit(text)
    out_text, segs = engine.rewrite_unit(unit, atoms=(), policy=policy, tokenizer=CL100K)
    assert CL100K.count_tokens(out_text) < before
    assert segs[0].kind == "rewrite"
    assert "kB" in out_text and "MB" in out_text


# =========================================================================
# 3. Git SHA / IPv4 false-positive hardening.
# =========================================================================


def test_git_sha_rejects_scientific_notation_and_bare_hex_words():
    text = (
        "Growth reached 1e10000 percent. The token 12abcdef was random. "
        "The color deadbee1 appeared in a MIME boundary."
    )
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    sha_surfaces = {a.surface for a in atoms if a.kind == "git_sha"}
    assert "1e10000" not in sha_surfaces
    assert "12abcdef" not in sha_surfaces
    assert "deadbee1" not in sha_surfaces


def test_git_sha_still_detects_context_adjacent_short_hashes():
    for text, expected in (
        ("Short commit 7a3f89b deployed.", "7a3f89b"),
        ("Git ref c0ffee1 deployed.", "c0ffee1"),
        ("Head 9abcdef pushed.", "9abcdef"),
    ):
        ingest = ingest_bytes(text.encode("utf-8"))
        atoms = extract_atoms(ingest)
        sha_surfaces = {a.surface for a in atoms if a.kind == "git_sha"}
        assert expected in sha_surfaces, f"missing {expected} in {sha_surfaces} for {text!r}"


def test_git_sha_full_length_hashes_always_detected():
    sha1 = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    for sha in (sha1, sha256):
        spans = iter_git_sha_spans(f"Commit {sha} merged.")
        assert any(f"Commit {sha} merged."[s:e] == sha for s, e in spans)


def test_ipv4_rejects_version_and_section_numbers():
    text = "Upgrade from 1.2.3.4 to 2.0.0.1. See section 3.1.4.1 for details."
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    ipv4_surfaces = {a.surface for a in atoms if a.kind == "ipv4"}
    assert "1.2.3.4" not in ipv4_surfaces
    assert "3.1.4.1" not in ipv4_surfaces


def test_ipv4_still_detects_real_addresses_in_prose_and_brackets():
    for text, expected in (
        ("Host 10.0.0.1 did not respond.", "10.0.0.1"),
        ("Received: from mail.example.com [10.0.0.1] by relay", "10.0.0.1"),
    ):
        spans = iter_ipv4_spans(text)
        surfaces = {text[s:e] for s, e in spans}
        assert expected in surfaces, f"missing {expected} in {surfaces} for {text!r}"


# =========================================================================
# 4. Hebrew-lookalike typo in OTHER_NEGATION ("بدون" must be Persian/Arabic, U+0628 U+062F
#    U+0648 U+0646, not Hebrew vav (U+05D5) + final-nun (U+05DF)).
# =========================================================================


def test_other_negation_uses_correct_persian_arabic_codepoints():
    assert "ו" not in OTHER_NEGATION, "OTHER_NEGATION must not contain Hebrew vav (U+05D5)"
    assert "ן" not in OTHER_NEGATION, "OTHER_NEGATION must not contain Hebrew final-nun (U+05DF)"
    persian_bidun = "بدون"  # بدون
    assert persian_bidun in OTHER_NEGATION
    assert re.search(rf"\b{persian_bidun}\b", "این کار بدون اجازه انجام شد")


# =========================================================================
# 5. Discourse pruning capitalization only applies when a preamble was removed.
# =========================================================================


def test_discourse_prune_does_not_corrupt_untouched_lowercase_start():
    text = "ps: I'll call you tomorrow."
    assert prune_discourse_scaffolding(text) == text


def test_discourse_prune_recapitalizes_only_when_preamble_removed():
    text = "Additionally, the server was rebooted."
    result = prune_discourse_scaffolding(text)
    assert result == "The server was rebooted."


# =========================================================================
# 6. Git SHA short-candidate regex sanity (7-12 hex, mixed digit+letter).
# =========================================================================


def test_git_sha_short_candidate_regex_shape():
    assert GIT_SHA_SHORT_CANDIDATE_RE.fullmatch("7a3f89b")
    assert not GIT_SHA_SHORT_CANDIDATE_RE.fullmatch("1234567")  # all-digit, not SHA-like
    assert not GIT_SHA_SHORT_CANDIDATE_RE.fullmatch("abcdefg")  # 'g' not hex
