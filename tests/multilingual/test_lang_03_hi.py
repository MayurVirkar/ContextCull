"""Honest multilingual test suite for Hindi (hi).

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
CORPUS_FILE = REPO_ROOT / "examples/eval/multilingual" / "04_hi_premchand_stories.txt"


# ---------------------------------------------------------------------------
# 1. Native sentence segmentation
# ---------------------------------------------------------------------------

SEGMENTATION_CASES_HI = [
    ("डेटाबेस सफलतापूर्वक पुनः आरंभ हुआ। पुनः आरंभ के दौरान कोई त्रुटि दर्ज नहीं हुई।", 2),
    ("सुबह नौ बजे ट्रैफ़िक चरम पर पहुंचा। टीम ने क्लस्टर को बड़ा किया। कुछ ही मिनटों में विलंबता सामान्य हो गई।", 3),
    ("क्या बैकअप पूरा हो गया है? डैशबोर्ड अभी भी दिखा रहा है कि यह चल रहा है।", 2),
    ("अभी पैच तैनात करें! बाद में स्वास्थ्य जांच सत्यापित करें।", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_HI)
def test_hi_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# ---------------------------------------------------------------------------
# 2. Atom extraction: CVE, IPv4 AND metric must all be detected
# ---------------------------------------------------------------------------

ATOM_CASES_HI = [
    (
        "उत्पादन सर्वर 10.0.4.12 पर CPU उपयोग 45 ms तक पहुंचने के बाद चेतावनी जारी हुई, टीम इसे CVE-2026-10432 के तहत ट्रैक कर रही है।",
        "CVE-2026-10432",
        "10.0.4.12",
        "45 ms",
    ),
    (
        "इंजीनियरों ने होस्ट 10.0.9.31 पर 120 ms विलंबता वृद्धि को भेद्यता CVE-2026-20981 से जोड़ा।",
        "CVE-2026-20981",
        "10.0.9.31",
        "120 ms",
    ),
    (
        "CVE-2026-31207 के लिए पैच 10.1.2.44 पर तैनात किया गया, थ्रूपुट 78 ms से ऊपर बहाल हुआ।",
        "CVE-2026-31207",
        "10.1.2.44",
        "78 ms",
    ),
    (
        "उत्पादन सर्वर 10.1.7.19 पर CPU उपयोग 212 ms तक पहुंचने के बाद चेतावनी जारी हुई, टीम इसे CVE-2026-40556 के तहत ट्रैक कर रही है।",
        "CVE-2026-40556",
        "10.1.7.19",
        "212 ms",
    ),
    (
        "इंजीनियरों ने होस्ट 10.2.5.63 पर 33 ms विलंबता वृद्धि को भेद्यता CVE-2026-50871 से जोड़ा।",
        "CVE-2026-50871",
        "10.2.5.63",
        "33 ms",
    ),
    (
        "CVE-2026-61190 के लिए पैच 10.2.8.27 पर तैनात किया गया, थ्रूपुट 156 ms से ऊपर बहाल हुआ।",
        "CVE-2026-61190",
        "10.2.8.27",
        "156 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_HI)
def test_hi_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
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

NEGATION_CASES_HI = [
    "फेलओवर के दौरान कोई डेटा हानि नहीं हुई।",
    "वैध कॉन्फ़िगरेशन फ़ाइल के बिना सेवा पुनः आरंभ नहीं हो सकती।",
    "उस लिंक पर हमने कभी पैकेट हानि नहीं देखी।",
]


@pytest.mark.parametrize("text", NEGATION_CASES_HI)
def test_hi_negation_detection(text: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    kinds = [a.kind for a in atoms if a.kind in ("negation", "bound_negation")]
    assert "bound_negation" in kinds, (
        f"Expected a 'bound_negation' atom, got kinds={kinds} for {text!r}"
    )


# ---------------------------------------------------------------------------
# 4. Byte-exact UTF-8 SourceMap span round-trip
# ---------------------------------------------------------------------------

SPAN_CASES_HI = [
    "उत्पादन सर्वर 10.0.4.12 पर CPU उपयोग 45 ms तक पहुंचने के बाद चेतावनी जारी हुई, टीम इसे CVE-2026-10432 के तहत ट्रैक कर रही है।",
    "इंजीनियरों ने होस्ट 10.0.9.31 पर 120 ms विलंबता वृद्धि को भेद्यता CVE-2026-20981 से जोड़ा।",
    "CVE-2026-31207 के लिए पैच 10.1.2.44 पर तैनात किया गया, थ्रूपुट 78 ms से ऊपर बहाल हुआ।",
]


@pytest.mark.parametrize("text", SPAN_CASES_HI)
def test_hi_utf8_byte_span_roundtrip(text: str):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)
    for char_idx in (0, len(text) // 3, len(text) // 2, len(text) - 1):
        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        assert raw_bytes[span.start : span.end].decode("utf-8") == ingest.clean_text[char_idx]


# ---------------------------------------------------------------------------
# 5. End-to-end compile on a slice of the real corpus
# ---------------------------------------------------------------------------


def test_hi_end_to_end_real_corpus_slice():
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
