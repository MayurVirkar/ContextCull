"""Honest multilingual test suite for Bengali (bn).

Real, hand-authored native-language sentences (not templated placeholders
or English carrier text with a foreign word pasted in). See
scripts/generate_multilingual_tests.py for how this file is generated and why.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contextcull.api import ContextCompiler
from contextcull.detect.atoms import extract_atoms
from contextcull.ingest.decoder import clean_char_to_byte_span, ingest_bytes
from contextcull.ir.models import CompileMode, CompilePolicy
from contextcull.segment.sentence import segment_sentences

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_FILE = REPO_ROOT / "examples/eval/multilingual" / "08_bn_gitanjali.txt"


# ---------------------------------------------------------------------------
# 1. Native sentence segmentation
# ---------------------------------------------------------------------------

SEGMENTATION_CASES_BN = [
    ("ডাটাবেস সফলভাবে পুনরায় চালু হয়েছে। পুনরায় চালুর সময় কোনো ত্রুটি রেকর্ড হয়নি।", 2),
    (
        "সকাল নয়টায় ট্রাফিক শীর্ষে পৌঁছেছিল। দল ক্লাস্টার বড় করেছে। কয়েক মিনিটের মধ্যে বিলম্বতা স্বাভাবিক হয়ে গেছে।",
        3,
    ),
    ("ব্যাকআপ কি সম্পূর্ণ হয়েছে? ড্যাশবোর্ড এখনও দেখাচ্ছে এটি চলছে।", 2),
    ("এখনই প্যাচ স্থাপন করুন! এরপর স্বাস্থ্য পরীক্ষা যাচাই করুন।", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_BN)
def test_bn_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# ---------------------------------------------------------------------------
# 2. Atom extraction: CVE, IPv4 AND metric must all be detected
# ---------------------------------------------------------------------------

ATOM_CASES_BN = [
    (
        "উৎপাদন সার্ভার 10.0.4.12 -এ CPU ব্যবহার 45 ms -এ পৌঁছানোর পর সতর্কতা জারি হয়েছে, দল এটি CVE-2026-10432 -এর অধীনে ট্র্যাক করছে।",
        "CVE-2026-10432",
        "10.0.4.12",
        "45 ms",
    ),
    (
        "প্রকৌশলীরা হোস্ট 10.0.9.31 -এ 120 ms বিলম্বতা বৃদ্ধিকে দুর্বলতা CVE-2026-20981 -এর সঙ্গে যুক্ত করেছেন।",
        "CVE-2026-20981",
        "10.0.9.31",
        "120 ms",
    ),
    (
        "CVE-2026-31207 -এর জন্য একটি প্যাচ 10.1.2.44 -এ স্থাপন করা হয়েছে, থ্রুপুট 78 ms -এর উপরে পুনরুদ্ধার হয়েছে।",
        "CVE-2026-31207",
        "10.1.2.44",
        "78 ms",
    ),
    (
        "উৎপাদন সার্ভার 10.1.7.19 -এ CPU ব্যবহার 212 ms -এ পৌঁছানোর পর সতর্কতা জারি হয়েছে, দল এটি CVE-2026-40556 -এর অধীনে ট্র্যাক করছে।",
        "CVE-2026-40556",
        "10.1.7.19",
        "212 ms",
    ),
    (
        "প্রকৌশলীরা হোস্ট 10.2.5.63 -এ 33 ms বিলম্বতা বৃদ্ধিকে দুর্বলতা CVE-2026-50871 -এর সঙ্গে যুক্ত করেছেন।",
        "CVE-2026-50871",
        "10.2.5.63",
        "33 ms",
    ),
    (
        "CVE-2026-61190 -এর জন্য একটি প্যাচ 10.2.8.27 -এ স্থাপন করা হয়েছে, থ্রুপুট 156 ms -এর উপরে পুনরুদ্ধার হয়েছে।",
        "CVE-2026-61190",
        "10.2.8.27",
        "156 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_BN)
def test_bn_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = [a.surface for a in atoms]
    assert any(expected_cve in s for s in surfaces), f"Missing CVE {expected_cve} in {surfaces}"
    assert any(expected_ip in s for s in surfaces), f"Missing IP {expected_ip} in {surfaces}"
    assert any(expected_metric.split()[0] in s for s in surfaces), (
        f"Missing metric {expected_metric} in {surfaces}"
    )


# ---------------------------------------------------------------------------
# 3. Negation detection
# ---------------------------------------------------------------------------

NEGATION_CASES_BN = [
    "উপযুক্ত অনুমোদন বিনা কোনো পরিবর্তন প্রয়োগ করা হয় না।",
    "বৈধ কনফিগারেশন ফাইল বিনা পরিষেবা পুনরায় চালু হয় না।",
    "পর্যাপ্ত পরীক্ষা বিনা কোনো প্যাচ স্থাপন করা হয় না।",
]


@pytest.mark.parametrize("text", NEGATION_CASES_BN)
def test_bn_negation_detection(text: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    kinds = [a.kind for a in atoms if a.kind in ("negation", "bound_negation")]
    assert "bound_negation" in kinds, (
        f"Expected a 'bound_negation' atom, got kinds={kinds} for {text!r}"
    )


# ---------------------------------------------------------------------------
# 4. Byte-exact UTF-8 SourceMap span round-trip
# ---------------------------------------------------------------------------

SPAN_CASES_BN = [
    "উৎপাদন সার্ভার 10.0.4.12 -এ CPU ব্যবহার 45 ms -এ পৌঁছানোর পর সতর্কতা জারি হয়েছে, দল এটি CVE-2026-10432 -এর অধীনে ট্র্যাক করছে।",
    "প্রকৌশলীরা হোস্ট 10.0.9.31 -এ 120 ms বিলম্বতা বৃদ্ধিকে দুর্বলতা CVE-2026-20981 -এর সঙ্গে যুক্ত করেছেন।",
    "CVE-2026-31207 -এর জন্য একটি প্যাচ 10.1.2.44 -এ স্থাপন করা হয়েছে, থ্রুপুট 78 ms -এর উপরে পুনরুদ্ধার হয়েছে।",
]


@pytest.mark.parametrize("text", SPAN_CASES_BN)
def test_bn_utf8_byte_span_roundtrip(text: str):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)
    for char_idx in (0, len(text) // 3, len(text) // 2, len(text) - 1):
        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        assert raw_bytes[span.start : span.end].decode("utf-8") == ingest.clean_text[char_idx]


# ---------------------------------------------------------------------------
# 5. End-to-end compile on a slice of the real corpus
# ---------------------------------------------------------------------------


def test_bn_end_to_end_real_corpus_slice():
    if not CORPUS_FILE.exists():
        pytest.skip(f"corpus file not present: {CORPUS_FILE}")
    raw_text = CORPUS_FILE.read_text(encoding="utf-8")[:6000]
    raw_bytes = raw_text.encode("utf-8")
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(raw_bytes, policy=CompilePolicy(mode=CompileMode.COMPACT))
    assert result.status == "OK", result.diagnostics
    assert 0 < len(result.text) < len(raw_text)

    ingest = ingest_bytes(raw_bytes)
    for char_idx in (0, len(raw_text) // 3, len(raw_text) // 2, len(raw_text) - 1):
        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        assert raw_bytes[span.start : span.end].decode("utf-8") == ingest.clean_text[char_idx]
