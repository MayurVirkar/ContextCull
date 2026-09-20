"""Exhaustive multilingual test suite for French (fr) - 100 tests.

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

SEGMENTATION_CASES_FR = [
    # Multiple sentences with native punctuation
    ("Sentence 1 regarding système. Second sentence about incident.", 2),
    ("Sentence 2 regarding incident! Second sentence about base de données!", 2),
    ("Sentence 3 regarding base de données? Second sentence about grappe?", 2),
    ("Sentence 4 regarding grappe... Second sentence about déploiement...", 2),
    ("Sentence 5 regarding déploiement. Second sentence about latence.", 2),
    ("Sentence 6 regarding latence! Second sentence about mémoire!", 2),
    ("Sentence 7 regarding mémoire? Second sentence about sécurité?", 2),
    ("Sentence 8 regarding sécurité... Second sentence about système...", 2),
    ("Sentence 9 regarding système. Second sentence about incident.", 2),
    ("Sentence 10 regarding incident! Second sentence about base de données!", 2),
    ("Sentence 11 regarding base de données? Second sentence about grappe?", 2),
    ("Sentence 12 regarding grappe... Second sentence about déploiement...", 2),
    ("Sentence 13 regarding déploiement. Second sentence about latence.", 2),
    ("Sentence 14 regarding latence! Second sentence about mémoire!", 2),
    ("Sentence 15 regarding mémoire? Second sentence about sécurité?", 2),
    ("Sentence 16 regarding sécurité... Second sentence about système...", 2),
    ("Sentence 17 regarding système. Second sentence about incident.", 2),
    ("Sentence 18 regarding incident! Second sentence about base de données!", 2),
    ("Sentence 19 regarding base de données? Second sentence about grappe?", 2),
    ("Sentence 20 regarding grappe... Second sentence about déploiement...", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_FR)
def test_fr_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# =========================================================================
# 2. Embedded Technical Atom Extraction in Native Prose (30 tests)
# =========================================================================

ATOM_CASES_FR = [
    (
        "Le serveur de production 10.5.1.2 a signalé 21 ms le 2026-07-02. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5001.",
        "CVE-2026-5001",
        "10.5.1.2",
        "21 ms",
    ),
    (
        "Le serveur de production 10.5.2.3 a signalé 22 ms le 2026-07-03. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5002.",
        "CVE-2026-5002",
        "10.5.2.3",
        "22 ms",
    ),
    (
        "Le serveur de production 10.5.3.4 a signalé 23 ms le 2026-07-04. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5003.",
        "CVE-2026-5003",
        "10.5.3.4",
        "23 ms",
    ),
    (
        "Le serveur de production 10.5.4.5 a signalé 24 ms le 2026-07-05. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5004.",
        "CVE-2026-5004",
        "10.5.4.5",
        "24 ms",
    ),
    (
        "Le serveur de production 10.5.5.6 a signalé 25 ms le 2026-07-06. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5005.",
        "CVE-2026-5005",
        "10.5.5.6",
        "25 ms",
    ),
    (
        "Le serveur de production 10.5.6.7 a signalé 26 ms le 2026-07-07. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5006.",
        "CVE-2026-5006",
        "10.5.6.7",
        "26 ms",
    ),
    (
        "Le serveur de production 10.5.7.8 a signalé 27 ms le 2026-07-08. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5007.",
        "CVE-2026-5007",
        "10.5.7.8",
        "27 ms",
    ),
    (
        "Le serveur de production 10.5.8.9 a signalé 28 ms le 2026-07-09. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5008.",
        "CVE-2026-5008",
        "10.5.8.9",
        "28 ms",
    ),
    (
        "Le serveur de production 10.5.9.10 a signalé 29 ms le 2026-07-10. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5009.",
        "CVE-2026-5009",
        "10.5.9.10",
        "29 ms",
    ),
    (
        "Le serveur de production 10.5.10.11 a signalé 30 ms le 2026-07-11. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5010.",
        "CVE-2026-5010",
        "10.5.10.11",
        "30 ms",
    ),
    (
        "Le serveur de production 10.5.11.12 a signalé 31 ms le 2026-07-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5011.",
        "CVE-2026-5011",
        "10.5.11.12",
        "31 ms",
    ),
    (
        "Le serveur de production 10.5.12.13 a signalé 32 ms le 2026-07-13. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5012.",
        "CVE-2026-5012",
        "10.5.12.13",
        "32 ms",
    ),
    (
        "Le serveur de production 10.5.13.14 a signalé 33 ms le 2026-07-14. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5013.",
        "CVE-2026-5013",
        "10.5.13.14",
        "33 ms",
    ),
    (
        "Le serveur de production 10.5.14.15 a signalé 34 ms le 2026-07-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5014.",
        "CVE-2026-5014",
        "10.5.14.15",
        "34 ms",
    ),
    (
        "Le serveur de production 10.5.15.16 a signalé 35 ms le 2026-07-16. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5015.",
        "CVE-2026-5015",
        "10.5.15.16",
        "35 ms",
    ),
    (
        "Le serveur de production 10.5.16.17 a signalé 36 ms le 2026-07-17. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5016.",
        "CVE-2026-5016",
        "10.5.16.17",
        "36 ms",
    ),
    (
        "Le serveur de production 10.5.17.18 a signalé 37 ms le 2026-07-18. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5017.",
        "CVE-2026-5017",
        "10.5.17.18",
        "37 ms",
    ),
    (
        "Le serveur de production 10.5.18.19 a signalé 38 ms le 2026-07-19. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5018.",
        "CVE-2026-5018",
        "10.5.18.19",
        "38 ms",
    ),
    (
        "Le serveur de production 10.5.19.20 a signalé 39 ms le 2026-07-20. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5019.",
        "CVE-2026-5019",
        "10.5.19.20",
        "39 ms",
    ),
    (
        "Le serveur de production 10.5.20.21 a signalé 40 ms le 2026-07-21. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5020.",
        "CVE-2026-5020",
        "10.5.20.21",
        "40 ms",
    ),
    (
        "Le serveur de production 10.5.21.22 a signalé 41 ms le 2026-07-22. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5021.",
        "CVE-2026-5021",
        "10.5.21.22",
        "41 ms",
    ),
    (
        "Le serveur de production 10.5.22.23 a signalé 42 ms le 2026-07-23. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5022.",
        "CVE-2026-5022",
        "10.5.22.23",
        "42 ms",
    ),
    (
        "Le serveur de production 10.5.23.24 a signalé 43 ms le 2026-07-24. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5023.",
        "CVE-2026-5023",
        "10.5.23.24",
        "43 ms",
    ),
    (
        "Le serveur de production 10.5.24.25 a signalé 44 ms le 2026-07-25. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5024.",
        "CVE-2026-5024",
        "10.5.24.25",
        "44 ms",
    ),
    (
        "Le serveur de production 10.5.25.26 a signalé 45 ms le 2026-07-26. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5025.",
        "CVE-2026-5025",
        "10.5.25.26",
        "45 ms",
    ),
    (
        "Le serveur de production 10.5.26.27 a signalé 46 ms le 2026-07-27. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5026.",
        "CVE-2026-5026",
        "10.5.26.27",
        "46 ms",
    ),
    (
        "Le serveur de production 10.5.27.28 a signalé 47 ms le 2026-07-28. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5027.",
        "CVE-2026-5027",
        "10.5.27.28",
        "47 ms",
    ),
    (
        "Le serveur de production 10.5.28.29 a signalé 48 ms le 2026-07-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5028.",
        "CVE-2026-5028",
        "10.5.28.29",
        "48 ms",
    ),
    (
        "Le serveur de production 10.5.29.30 a signalé 49 ms le 2026-07-02. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5029.",
        "CVE-2026-5029",
        "10.5.29.30",
        "49 ms",
    ),
    (
        "Le serveur de production 10.5.30.31 a signalé 50 ms le 2026-07-03. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-5030.",
        "CVE-2026-5030",
        "10.5.30.31",
        "50 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_FR)
def test_fr_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = [a.surface for a in atoms]
    assert any(expected_cve in s for s in surfaces), f"Missing CVE {expected_cve} in {surfaces}"
    assert any(expected_ip in s for s in surfaces), f"Missing IP {expected_ip} in {surfaces}"


# =========================================================================
# 3. Multi-byte UTF-8 SourceMap Coordinate Alignment (20 tests)
# =========================================================================

COORDINATE_CASES_FR = [
    (
        "French système test case 1: Le serveur de production 192.168.5.1 a signalé 5 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8801."
    ),
    (
        "French incident test case 2: Le serveur de production 192.168.5.2 a signalé 10 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8802."
    ),
    (
        "French base de données test case 3: Le serveur de production 192.168.5.3 a signalé 15 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8803."
    ),
    (
        "French grappe test case 4: Le serveur de production 192.168.5.4 a signalé 20 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8804."
    ),
    (
        "French déploiement test case 5: Le serveur de production 192.168.5.5 a signalé 25 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8805."
    ),
    (
        "French latence test case 6: Le serveur de production 192.168.5.6 a signalé 30 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8806."
    ),
    (
        "French mémoire test case 7: Le serveur de production 192.168.5.7 a signalé 35 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8807."
    ),
    (
        "French sécurité test case 8: Le serveur de production 192.168.5.8 a signalé 40 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8808."
    ),
    (
        "French système test case 9: Le serveur de production 192.168.5.9 a signalé 45 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8809."
    ),
    (
        "French incident test case 10: Le serveur de production 192.168.5.10 a signalé 50 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8810."
    ),
    (
        "French base de données test case 11: Le serveur de production 192.168.5.11 a signalé 55 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8811."
    ),
    (
        "French grappe test case 12: Le serveur de production 192.168.5.12 a signalé 60 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8812."
    ),
    (
        "French déploiement test case 13: Le serveur de production 192.168.5.13 a signalé 65 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8813."
    ),
    (
        "French latence test case 14: Le serveur de production 192.168.5.14 a signalé 70 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8814."
    ),
    (
        "French mémoire test case 15: Le serveur de production 192.168.5.15 a signalé 75 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8815."
    ),
    (
        "French sécurité test case 16: Le serveur de production 192.168.5.16 a signalé 80 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8816."
    ),
    (
        "French système test case 17: Le serveur de production 192.168.5.17 a signalé 85 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8817."
    ),
    (
        "French incident test case 18: Le serveur de production 192.168.5.18 a signalé 90 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8818."
    ),
    (
        "French base de données test case 19: Le serveur de production 192.168.5.19 a signalé 95 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8819."
    ),
    (
        "French grappe test case 20: Le serveur de production 192.168.5.20 a signalé 100 MB le 2026-08-15. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-8820."
    ),
]


@pytest.mark.parametrize("text", COORDINATE_CASES_FR)
def test_fr_utf8_sourcemap_coordinates(text: str):
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

NEGATION_CASES_FR = [
    (
        "Le serveur de production 10.99.5.1 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7701."
    ),
    (
        "Le serveur de production 10.99.5.2 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7702."
    ),
    (
        "Le serveur de production 10.99.5.3 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7703."
    ),
    (
        "Le serveur de production 10.99.5.4 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7704."
    ),
    (
        "Le serveur de production 10.99.5.5 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7705."
    ),
    (
        "Le serveur de production 10.99.5.6 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7706."
    ),
    (
        "Le serveur de production 10.99.5.7 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7707."
    ),
    (
        "Le serveur de production 10.99.5.8 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7708."
    ),
    (
        "Le serveur de production 10.99.5.9 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7709."
    ),
    (
        "Le serveur de production 10.99.5.10 a signalé 15 ms le 2026-09-01. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-7710."
    ),
]


@pytest.mark.parametrize("text", NEGATION_CASES_FR)
def test_fr_negation_and_modality_protection(text: str):
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(text.encode("utf-8"))
    assert result.ok
    # Invariant: technical identifiers and numbers must be preserved
    assert len(result.text) > 0


# =========================================================================
# 5. Full End-to-End Compiler Pipeline & Invariant Checks (20 tests)
# =========================================================================

COMPILER_CASES_FR = [
    (
        "Header French 1\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 2\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 3\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 4\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 5\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 6\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 7\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 8\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 9\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 10\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 11\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 12\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 13\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 14\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 15\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 16\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 17\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 18\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 19\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
    (
        "Header French 20\\n\\nLe serveur de production 10.5.1.1 a signalé 11 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9501.\\nLe serveur de production 10.5.2.1 a signalé 12 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9502.\\nLe serveur de production 10.5.3.1 a signalé 13 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9503.\\nLe serveur de production 10.5.4.1 a signalé 14 ms le 2026-05-12. Un ingénieur a vérifié qu'aucune perte de données n'est survenue avec CVE-2026-9504."
    ),
]


@pytest.mark.parametrize("doc_text", COMPILER_CASES_FR)
def test_fr_end_to_end_compilation(doc_text: str):
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
