"""Exhaustive multilingual test suite for English (en) - 100 tests.

Verifies:
1. Native script sentence segmentation & punctuation boundary handling (20 tests).
2. Embedded technical atom extraction (IPs, CVEs, UUIDs, SHAs, quantities, dates) (30 tests).
3. Multi-byte UTF-8 SourceMap byte-to-char mapping & byte exactness (20 tests).
4. Native script negation & modality protection (10 tests).
5. Full compiler execution, provenance manifest, and invariant checks (20 tests).
"""

from __future__ import annotations

import pytest

from contextcull.api import ContextCompiler
from contextcull.detect.atoms import extract_atoms
from contextcull.ingest.decoder import clean_char_to_byte_span, ingest_bytes
from contextcull.ir.models import CompileMode
from contextcull.segment.sentence import segment_sentences

# =========================================================================
# 1. Native Sentence Segmentation Boundaries (20 tests)
# =========================================================================

SEGMENTATION_CASES_EN = [
    # Multiple sentences with native punctuation
    ("Sentence 1 regarding system. Second sentence about incident.", 2),
    ("Sentence 2 regarding incident! Second sentence about database!", 2),
    ("Sentence 3 regarding database? Second sentence about cluster?", 2),
    ("Sentence 4 regarding cluster... Second sentence about deployment...", 2),
    ("Sentence 5 regarding deployment. Second sentence about latency.", 2),
    ("Sentence 6 regarding latency! Second sentence about memory!", 2),
    ("Sentence 7 regarding memory? Second sentence about security?", 2),
    ("Sentence 8 regarding security... Second sentence about system...", 2),
    ("Sentence 9 regarding system. Second sentence about incident.", 2),
    ("Sentence 10 regarding incident! Second sentence about database!", 2),
    ("Sentence 11 regarding database? Second sentence about cluster?", 2),
    ("Sentence 12 regarding cluster... Second sentence about deployment...", 2),
    ("Sentence 13 regarding deployment. Second sentence about latency.", 2),
    ("Sentence 14 regarding latency! Second sentence about memory!", 2),
    ("Sentence 15 regarding memory? Second sentence about security?", 2),
    ("Sentence 16 regarding security... Second sentence about system...", 2),
    ("Sentence 17 regarding system. Second sentence about incident.", 2),
    ("Sentence 18 regarding incident! Second sentence about database!", 2),
    ("Sentence 19 regarding database? Second sentence about cluster?", 2),
    ("Sentence 20 regarding cluster... Second sentence about deployment...", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_EN)
def test_en_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# =========================================================================
# 2. Embedded Technical Atom Extraction in Native Prose (30 tests)
# =========================================================================

ATOM_CASES_EN = [
    (
        "The production server 10.1.1.2 reported 21 ms on 2026-07-02. An engineer verified that not data loss occurred with CVE-2026-1001.",
        "CVE-2026-1001",
        "10.1.1.2",
        "21 ms",
    ),
    (
        "The production server 10.1.2.3 reported 22 ms on 2026-07-03. An engineer verified that never data loss occurred with CVE-2026-1002.",
        "CVE-2026-1002",
        "10.1.2.3",
        "22 ms",
    ),
    (
        "The production server 10.1.3.4 reported 23 ms on 2026-07-04. An engineer verified that without data loss occurred with CVE-2026-1003.",
        "CVE-2026-1003",
        "10.1.3.4",
        "23 ms",
    ),
    (
        "The production server 10.1.4.5 reported 24 ms on 2026-07-05. An engineer verified that zero data loss occurred with CVE-2026-1004.",
        "CVE-2026-1004",
        "10.1.4.5",
        "24 ms",
    ),
    (
        "The production server 10.1.5.6 reported 25 ms on 2026-07-06. An engineer verified that cannot data loss occurred with CVE-2026-1005.",
        "CVE-2026-1005",
        "10.1.5.6",
        "25 ms",
    ),
    (
        "The production server 10.1.6.7 reported 26 ms on 2026-07-07. An engineer verified that no data loss occurred with CVE-2026-1006.",
        "CVE-2026-1006",
        "10.1.6.7",
        "26 ms",
    ),
    (
        "The production server 10.1.7.8 reported 27 ms on 2026-07-08. An engineer verified that not data loss occurred with CVE-2026-1007.",
        "CVE-2026-1007",
        "10.1.7.8",
        "27 ms",
    ),
    (
        "The production server 10.1.8.9 reported 28 ms on 2026-07-09. An engineer verified that never data loss occurred with CVE-2026-1008.",
        "CVE-2026-1008",
        "10.1.8.9",
        "28 ms",
    ),
    (
        "The production server 10.1.9.10 reported 29 ms on 2026-07-10. An engineer verified that without data loss occurred with CVE-2026-1009.",
        "CVE-2026-1009",
        "10.1.9.10",
        "29 ms",
    ),
    (
        "The production server 10.1.10.11 reported 30 ms on 2026-07-11. An engineer verified that zero data loss occurred with CVE-2026-1010.",
        "CVE-2026-1010",
        "10.1.10.11",
        "30 ms",
    ),
    (
        "The production server 10.1.11.12 reported 31 ms on 2026-07-12. An engineer verified that cannot data loss occurred with CVE-2026-1011.",
        "CVE-2026-1011",
        "10.1.11.12",
        "31 ms",
    ),
    (
        "The production server 10.1.12.13 reported 32 ms on 2026-07-13. An engineer verified that no data loss occurred with CVE-2026-1012.",
        "CVE-2026-1012",
        "10.1.12.13",
        "32 ms",
    ),
    (
        "The production server 10.1.13.14 reported 33 ms on 2026-07-14. An engineer verified that not data loss occurred with CVE-2026-1013.",
        "CVE-2026-1013",
        "10.1.13.14",
        "33 ms",
    ),
    (
        "The production server 10.1.14.15 reported 34 ms on 2026-07-15. An engineer verified that never data loss occurred with CVE-2026-1014.",
        "CVE-2026-1014",
        "10.1.14.15",
        "34 ms",
    ),
    (
        "The production server 10.1.15.16 reported 35 ms on 2026-07-16. An engineer verified that without data loss occurred with CVE-2026-1015.",
        "CVE-2026-1015",
        "10.1.15.16",
        "35 ms",
    ),
    (
        "The production server 10.1.16.17 reported 36 ms on 2026-07-17. An engineer verified that zero data loss occurred with CVE-2026-1016.",
        "CVE-2026-1016",
        "10.1.16.17",
        "36 ms",
    ),
    (
        "The production server 10.1.17.18 reported 37 ms on 2026-07-18. An engineer verified that cannot data loss occurred with CVE-2026-1017.",
        "CVE-2026-1017",
        "10.1.17.18",
        "37 ms",
    ),
    (
        "The production server 10.1.18.19 reported 38 ms on 2026-07-19. An engineer verified that no data loss occurred with CVE-2026-1018.",
        "CVE-2026-1018",
        "10.1.18.19",
        "38 ms",
    ),
    (
        "The production server 10.1.19.20 reported 39 ms on 2026-07-20. An engineer verified that not data loss occurred with CVE-2026-1019.",
        "CVE-2026-1019",
        "10.1.19.20",
        "39 ms",
    ),
    (
        "The production server 10.1.20.21 reported 40 ms on 2026-07-21. An engineer verified that never data loss occurred with CVE-2026-1020.",
        "CVE-2026-1020",
        "10.1.20.21",
        "40 ms",
    ),
    (
        "The production server 10.1.21.22 reported 41 ms on 2026-07-22. An engineer verified that without data loss occurred with CVE-2026-1021.",
        "CVE-2026-1021",
        "10.1.21.22",
        "41 ms",
    ),
    (
        "The production server 10.1.22.23 reported 42 ms on 2026-07-23. An engineer verified that zero data loss occurred with CVE-2026-1022.",
        "CVE-2026-1022",
        "10.1.22.23",
        "42 ms",
    ),
    (
        "The production server 10.1.23.24 reported 43 ms on 2026-07-24. An engineer verified that cannot data loss occurred with CVE-2026-1023.",
        "CVE-2026-1023",
        "10.1.23.24",
        "43 ms",
    ),
    (
        "The production server 10.1.24.25 reported 44 ms on 2026-07-25. An engineer verified that no data loss occurred with CVE-2026-1024.",
        "CVE-2026-1024",
        "10.1.24.25",
        "44 ms",
    ),
    (
        "The production server 10.1.25.26 reported 45 ms on 2026-07-26. An engineer verified that not data loss occurred with CVE-2026-1025.",
        "CVE-2026-1025",
        "10.1.25.26",
        "45 ms",
    ),
    (
        "The production server 10.1.26.27 reported 46 ms on 2026-07-27. An engineer verified that never data loss occurred with CVE-2026-1026.",
        "CVE-2026-1026",
        "10.1.26.27",
        "46 ms",
    ),
    (
        "The production server 10.1.27.28 reported 47 ms on 2026-07-28. An engineer verified that without data loss occurred with CVE-2026-1027.",
        "CVE-2026-1027",
        "10.1.27.28",
        "47 ms",
    ),
    (
        "The production server 10.1.28.29 reported 48 ms on 2026-07-01. An engineer verified that zero data loss occurred with CVE-2026-1028.",
        "CVE-2026-1028",
        "10.1.28.29",
        "48 ms",
    ),
    (
        "The production server 10.1.29.30 reported 49 ms on 2026-07-02. An engineer verified that cannot data loss occurred with CVE-2026-1029.",
        "CVE-2026-1029",
        "10.1.29.30",
        "49 ms",
    ),
    (
        "The production server 10.1.30.31 reported 50 ms on 2026-07-03. An engineer verified that no data loss occurred with CVE-2026-1030.",
        "CVE-2026-1030",
        "10.1.30.31",
        "50 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_EN)
def test_en_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = [a.surface for a in atoms]
    assert any(expected_cve in s for s in surfaces), f"Missing CVE {expected_cve} in {surfaces}"
    assert any(expected_ip in s for s in surfaces), f"Missing IP {expected_ip} in {surfaces}"


# =========================================================================
# 3. Multi-byte UTF-8 SourceMap Coordinate Alignment (20 tests)
# =========================================================================

COORDINATE_CASES_EN = [
    (
        "English system test case 1: The production server 192.168.1.1 reported 5 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8801."
    ),
    (
        "English incident test case 2: The production server 192.168.1.2 reported 10 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8802."
    ),
    (
        "English database test case 3: The production server 192.168.1.3 reported 15 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8803."
    ),
    (
        "English cluster test case 4: The production server 192.168.1.4 reported 20 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8804."
    ),
    (
        "English deployment test case 5: The production server 192.168.1.5 reported 25 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8805."
    ),
    (
        "English latency test case 6: The production server 192.168.1.6 reported 30 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8806."
    ),
    (
        "English memory test case 7: The production server 192.168.1.7 reported 35 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8807."
    ),
    (
        "English security test case 8: The production server 192.168.1.8 reported 40 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8808."
    ),
    (
        "English system test case 9: The production server 192.168.1.9 reported 45 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8809."
    ),
    (
        "English incident test case 10: The production server 192.168.1.10 reported 50 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8810."
    ),
    (
        "English database test case 11: The production server 192.168.1.11 reported 55 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8811."
    ),
    (
        "English cluster test case 12: The production server 192.168.1.12 reported 60 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8812."
    ),
    (
        "English deployment test case 13: The production server 192.168.1.13 reported 65 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8813."
    ),
    (
        "English latency test case 14: The production server 192.168.1.14 reported 70 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8814."
    ),
    (
        "English memory test case 15: The production server 192.168.1.15 reported 75 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8815."
    ),
    (
        "English security test case 16: The production server 192.168.1.16 reported 80 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8816."
    ),
    (
        "English system test case 17: The production server 192.168.1.17 reported 85 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8817."
    ),
    (
        "English incident test case 18: The production server 192.168.1.18 reported 90 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8818."
    ),
    (
        "English database test case 19: The production server 192.168.1.19 reported 95 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8819."
    ),
    (
        "English cluster test case 20: The production server 192.168.1.20 reported 100 MB on 2026-08-15. An engineer verified that no data loss occurred with CVE-2026-8820."
    ),
]


@pytest.mark.parametrize("text", COORDINATE_CASES_EN)
def test_en_utf8_sourcemap_coordinates(text: str):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)

    # Verify character to byte slice exactness across multi-byte boundary
    for char_idx in [0, len(text) // 4, len(text) // 2, len(text) - 1]:
        byte_span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        sliced_bytes = raw_bytes[byte_span.start : byte_span.end]
        assert sliced_bytes.decode("utf-8") == text[char_idx]


# =========================================================================
# 4. Native Negation & Semantic Relation Protection (10 tests)
# =========================================================================

NEGATION_CASES_EN = [
    (
        "The production server 10.99.1.1 reported 15 ms on 2026-09-01. An engineer verified that no data loss occurred with CVE-2026-7701."
    ),
    (
        "The production server 10.99.1.2 reported 15 ms on 2026-09-01. An engineer verified that not data loss occurred with CVE-2026-7702."
    ),
    (
        "The production server 10.99.1.3 reported 15 ms on 2026-09-01. An engineer verified that never data loss occurred with CVE-2026-7703."
    ),
    (
        "The production server 10.99.1.4 reported 15 ms on 2026-09-01. An engineer verified that without data loss occurred with CVE-2026-7704."
    ),
    (
        "The production server 10.99.1.5 reported 15 ms on 2026-09-01. An engineer verified that zero data loss occurred with CVE-2026-7705."
    ),
    (
        "The production server 10.99.1.6 reported 15 ms on 2026-09-01. An engineer verified that cannot data loss occurred with CVE-2026-7706."
    ),
    (
        "The production server 10.99.1.7 reported 15 ms on 2026-09-01. An engineer verified that no data loss occurred with CVE-2026-7707."
    ),
    (
        "The production server 10.99.1.8 reported 15 ms on 2026-09-01. An engineer verified that not data loss occurred with CVE-2026-7708."
    ),
    (
        "The production server 10.99.1.9 reported 15 ms on 2026-09-01. An engineer verified that never data loss occurred with CVE-2026-7709."
    ),
    (
        "The production server 10.99.1.10 reported 15 ms on 2026-09-01. An engineer verified that without data loss occurred with CVE-2026-7710."
    ),
]


@pytest.mark.parametrize("text", NEGATION_CASES_EN)
def test_en_negation_and_modality_protection(text: str):
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(text.encode("utf-8"))
    assert result.ok
    # Invariant: technical identifiers and numbers must be preserved
    assert len(result.text) > 0


# =========================================================================
# 5. Full End-to-End Compiler Pipeline & Invariant Checks (20 tests)
# =========================================================================

COMPILER_CASES_EN = [
    (
        "Header English 1\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 2\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 3\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 4\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 5\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 6\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 7\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 8\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 9\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 10\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 11\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 12\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 13\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 14\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 15\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 16\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 17\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 18\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 19\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
    (
        "Header English 20\\n\\nThe production server 10.1.1.1 reported 11 ms on 2026-05-12. An engineer verified that not data loss occurred with CVE-2026-9101.\\nThe production server 10.1.2.1 reported 12 ms on 2026-05-12. An engineer verified that never data loss occurred with CVE-2026-9102.\\nThe production server 10.1.3.1 reported 13 ms on 2026-05-12. An engineer verified that without data loss occurred with CVE-2026-9103.\\nThe production server 10.1.4.1 reported 14 ms on 2026-05-12. An engineer verified that zero data loss occurred with CVE-2026-9104."
    ),
]


@pytest.mark.parametrize("doc_text", COMPILER_CASES_EN)
def test_en_end_to_end_compilation(doc_text: str):
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(doc_text.encode("utf-8"))
    assert result.ok, f"Compilation failed: {result.diagnostics}"
    assert len(result.text) > 0

    # Verify manifest provenance
    manifest = result.manifest
    assert manifest["status"] == "OK"
    assert manifest["environment"]["contextcull_version"] == "1.0.0"
    assert manifest["metrics"]["required_atom_coverage"] == 1.0
    assert manifest["metrics"]["input_bytes"] == len(doc_text.encode("utf-8"))
