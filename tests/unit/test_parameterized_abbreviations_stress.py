"""Exhaustive casing and boundary stress tests for all abbreviation rules (240+ tests)."""

from __future__ import annotations

import pytest

from contextcull.ir.models import CandidateUnit, CompileMode, CompilePolicy
from contextcull.ir.spans import ByteSpan
from contextcull.rewrite.engine import RewriteEngine
from contextcull.rewrite.rules import ABBREVIATIONS
from contextcull.tokenize.profile import get_tokenizer

CL100K = get_tokenizer("cl100k_base")
ENGINE = RewriteEngine()
POLICY = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=False)


def _make_unit(text: str) -> CandidateUnit:
    span = ByteSpan("doc1", 0, len(text.encode("utf-8")))
    return CandidateUnit(
        unit_id="u1",
        block_id="block_1",
        sources=(span,),
        text=text,
        score=0.8,
    )


# 1. Lowercase in sentence context
@pytest.mark.parametrize("word,abbr", list(ABBREVIATIONS.items()))
def test_abbreviation_lowercase_stress(word: str, abbr: str):
    text = f"The {word.lower()} was evaluated by the team."
    unit = _make_unit(text)
    out_text, segments = ENGINE.rewrite_unit(unit, atoms=(), policy=POLICY, tokenizer=CL100K)
    assert len(out_text) <= len(text)
    assert len(segments) >= 1
    assert segments[0].output_end == len(out_text.encode("utf-8"))


# 2. Titlecase in sentence context
@pytest.mark.parametrize("word,abbr", list(ABBREVIATIONS.items()))
def test_abbreviation_titlecase_stress(word: str, abbr: str):
    text = f"{word.capitalize()} was evaluated by the team."
    unit = _make_unit(text)
    out_text, segments = ENGINE.rewrite_unit(unit, atoms=(), policy=POLICY, tokenizer=CL100K)
    assert len(out_text) <= len(text)
    assert len(segments) >= 1
    assert segments[0].output_end == len(out_text.encode("utf-8"))
