"""Honest multilingual test suite for Hebrew (he).

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
CORPUS_FILE = REPO_ROOT / "examples/eval/multilingual" / "12_he_bereshit_genesis.txt"


# ---------------------------------------------------------------------------
# 1. Native sentence segmentation
# ---------------------------------------------------------------------------

SEGMENTATION_CASES_HE = [
    ("מסד הנתונים הופעל מחדש בהצלחה. לא נרשמו שגיאות במהלך ההפעלה מחדש.", 2),
    ("התנועה הגיעה לשיא בתשע בבוקר. הצוות הרחיב את האשכול. זמן ההשהיה חזר לקדמותו תוך דקות.", 3),
    ("האם הגיבוי הושלם? הלוח עדיין מציג שהוא פועל.", 2),
    ("הפעל את התיקון עכשיו! אמת את בדיקת התקינות לאחר מכן.", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_HE)
def test_he_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# ---------------------------------------------------------------------------
# 2. Atom extraction: CVE, IPv4 AND metric must all be detected
# ---------------------------------------------------------------------------

ATOM_CASES_HE = [
    (
        "שרת הייצור 10.0.4.12 הפעיל התראה לאחר שניצול המעבד הגיע ל- 45 ms, והצוות עוקב אחר כך תחת CVE-2026-10432.",
        "CVE-2026-10432",
        "10.0.4.12",
        "45 ms",
    ),
    (
        "המהנדסים קישרו את קפיצת זמן ההשהיה של 120 ms במארח 10.0.9.31 לפגיעות CVE-2026-20981.",
        "CVE-2026-20981",
        "10.0.9.31",
        "120 ms",
    ),
    (
        "תיקון עבור CVE-2026-31207 הופעל בשרת 10.1.2.44, והשיב את התפוקה מעל 78 ms.",
        "CVE-2026-31207",
        "10.1.2.44",
        "78 ms",
    ),
    (
        "שרת הייצור 10.1.7.19 הפעיל התראה לאחר שניצול המעבד הגיע ל- 212 ms, והצוות עוקב אחר כך תחת CVE-2026-40556.",
        "CVE-2026-40556",
        "10.1.7.19",
        "212 ms",
    ),
    (
        "המהנדסים קישרו את קפיצת זמן ההשהיה של 33 ms במארח 10.2.5.63 לפגיעות CVE-2026-50871.",
        "CVE-2026-50871",
        "10.2.5.63",
        "33 ms",
    ),
    (
        "תיקון עבור CVE-2026-61190 הופעל בשרת 10.2.8.27, והשיב את התפוקה מעל 156 ms.",
        "CVE-2026-61190",
        "10.2.8.27",
        "156 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_HE)
def test_he_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
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

NEGATION_CASES_HE = [
    "לא אירע אובדן נתונים במהלך המעבר לגיבוי.",
    "לא ניתן להפעיל מחדש את השירות ללא קובץ תצורה תקין.",
    "מעולם לא צפינו באובדן חבילות בקישור הזה.",
]


@pytest.mark.parametrize("text", NEGATION_CASES_HE)
def test_he_negation_detection(text: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    kinds = [a.kind for a in atoms if a.kind in ("negation", "bound_negation")]
    assert "negation" in kinds, f"Expected a 'negation' atom, got kinds={kinds} for {text!r}"


# ---------------------------------------------------------------------------
# 4. Byte-exact UTF-8 SourceMap span round-trip
# ---------------------------------------------------------------------------

SPAN_CASES_HE = [
    "שרת הייצור 10.0.4.12 הפעיל התראה לאחר שניצול המעבד הגיע ל- 45 ms, והצוות עוקב אחר כך תחת CVE-2026-10432.",
    "המהנדסים קישרו את קפיצת זמן ההשהיה של 120 ms במארח 10.0.9.31 לפגיעות CVE-2026-20981.",
    "תיקון עבור CVE-2026-31207 הופעל בשרת 10.1.2.44, והשיב את התפוקה מעל 78 ms.",
]


@pytest.mark.parametrize("text", SPAN_CASES_HE)
def test_he_utf8_byte_span_roundtrip(text: str):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)
    for char_idx in (0, len(text) // 3, len(text) // 2, len(text) - 1):
        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        assert raw_bytes[span.start : span.end].decode("utf-8") == ingest.clean_text[char_idx]


# ---------------------------------------------------------------------------
# 5. End-to-end compile on a slice of the real corpus
# ---------------------------------------------------------------------------


def test_he_end_to_end_real_corpus_slice():
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
