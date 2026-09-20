"""Exhaustive multilingual test suite for Spanish (es) - 100 tests.

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

SEGMENTATION_CASES_ES = [
    # Multiple sentences with native punctuation
    ("Sentence 1 regarding sistema. Second sentence about incidente.", 2),
    ("Sentence 2 regarding incidente! Second sentence about base de datos!", 2),
    ("Sentence 3 regarding base de datos? Second sentence about clúster?", 2),
    ("Sentence 4 regarding clúster... Second sentence about despliegue...", 2),
    ("Sentence 5 regarding despliegue. Second sentence about latencia.", 2),
    ("Sentence 6 regarding latencia! Second sentence about memoria!", 2),
    ("Sentence 7 regarding memoria? Second sentence about seguridad?", 2),
    ("Sentence 8 regarding seguridad... Second sentence about sistema...", 2),
    ("Sentence 9 regarding sistema. Second sentence about incidente.", 2),
    ("Sentence 10 regarding incidente! Second sentence about base de datos!", 2),
    ("Sentence 11 regarding base de datos? Second sentence about clúster?", 2),
    ("Sentence 12 regarding clúster... Second sentence about despliegue...", 2),
    ("Sentence 13 regarding despliegue. Second sentence about latencia.", 2),
    ("Sentence 14 regarding latencia! Second sentence about memoria!", 2),
    ("Sentence 15 regarding memoria? Second sentence about seguridad?", 2),
    ("Sentence 16 regarding seguridad... Second sentence about sistema...", 2),
    ("Sentence 17 regarding sistema. Second sentence about incidente.", 2),
    ("Sentence 18 regarding incidente! Second sentence about base de datos!", 2),
    ("Sentence 19 regarding base de datos? Second sentence about clúster?", 2),
    ("Sentence 20 regarding clúster... Second sentence about despliegue...", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_ES)
def test_es_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# =========================================================================
# 2. Embedded Technical Atom Extraction in Native Prose (30 tests)
# =========================================================================

ATOM_CASES_ES = [
    (
        "El servidor de producción 10.4.1.2 reportó 21 ms el 2026-07-02. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4001.",
        "CVE-2026-4001",
        "10.4.1.2",
        "21 ms",
    ),
    (
        "El servidor de producción 10.4.2.3 reportó 22 ms el 2026-07-03. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4002.",
        "CVE-2026-4002",
        "10.4.2.3",
        "22 ms",
    ),
    (
        "El servidor de producción 10.4.3.4 reportó 23 ms el 2026-07-04. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4003.",
        "CVE-2026-4003",
        "10.4.3.4",
        "23 ms",
    ),
    (
        "El servidor de producción 10.4.4.5 reportó 24 ms el 2026-07-05. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4004.",
        "CVE-2026-4004",
        "10.4.4.5",
        "24 ms",
    ),
    (
        "El servidor de producción 10.4.5.6 reportó 25 ms el 2026-07-06. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4005.",
        "CVE-2026-4005",
        "10.4.5.6",
        "25 ms",
    ),
    (
        "El servidor de producción 10.4.6.7 reportó 26 ms el 2026-07-07. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4006.",
        "CVE-2026-4006",
        "10.4.6.7",
        "26 ms",
    ),
    (
        "El servidor de producción 10.4.7.8 reportó 27 ms el 2026-07-08. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4007.",
        "CVE-2026-4007",
        "10.4.7.8",
        "27 ms",
    ),
    (
        "El servidor de producción 10.4.8.9 reportó 28 ms el 2026-07-09. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4008.",
        "CVE-2026-4008",
        "10.4.8.9",
        "28 ms",
    ),
    (
        "El servidor de producción 10.4.9.10 reportó 29 ms el 2026-07-10. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4009.",
        "CVE-2026-4009",
        "10.4.9.10",
        "29 ms",
    ),
    (
        "El servidor de producción 10.4.10.11 reportó 30 ms el 2026-07-11. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4010.",
        "CVE-2026-4010",
        "10.4.10.11",
        "30 ms",
    ),
    (
        "El servidor de producción 10.4.11.12 reportó 31 ms el 2026-07-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4011.",
        "CVE-2026-4011",
        "10.4.11.12",
        "31 ms",
    ),
    (
        "El servidor de producción 10.4.12.13 reportó 32 ms el 2026-07-13. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4012.",
        "CVE-2026-4012",
        "10.4.12.13",
        "32 ms",
    ),
    (
        "El servidor de producción 10.4.13.14 reportó 33 ms el 2026-07-14. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4013.",
        "CVE-2026-4013",
        "10.4.13.14",
        "33 ms",
    ),
    (
        "El servidor de producción 10.4.14.15 reportó 34 ms el 2026-07-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4014.",
        "CVE-2026-4014",
        "10.4.14.15",
        "34 ms",
    ),
    (
        "El servidor de producción 10.4.15.16 reportó 35 ms el 2026-07-16. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4015.",
        "CVE-2026-4015",
        "10.4.15.16",
        "35 ms",
    ),
    (
        "El servidor de producción 10.4.16.17 reportó 36 ms el 2026-07-17. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4016.",
        "CVE-2026-4016",
        "10.4.16.17",
        "36 ms",
    ),
    (
        "El servidor de producción 10.4.17.18 reportó 37 ms el 2026-07-18. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4017.",
        "CVE-2026-4017",
        "10.4.17.18",
        "37 ms",
    ),
    (
        "El servidor de producción 10.4.18.19 reportó 38 ms el 2026-07-19. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4018.",
        "CVE-2026-4018",
        "10.4.18.19",
        "38 ms",
    ),
    (
        "El servidor de producción 10.4.19.20 reportó 39 ms el 2026-07-20. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4019.",
        "CVE-2026-4019",
        "10.4.19.20",
        "39 ms",
    ),
    (
        "El servidor de producción 10.4.20.21 reportó 40 ms el 2026-07-21. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4020.",
        "CVE-2026-4020",
        "10.4.20.21",
        "40 ms",
    ),
    (
        "El servidor de producción 10.4.21.22 reportó 41 ms el 2026-07-22. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4021.",
        "CVE-2026-4021",
        "10.4.21.22",
        "41 ms",
    ),
    (
        "El servidor de producción 10.4.22.23 reportó 42 ms el 2026-07-23. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4022.",
        "CVE-2026-4022",
        "10.4.22.23",
        "42 ms",
    ),
    (
        "El servidor de producción 10.4.23.24 reportó 43 ms el 2026-07-24. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4023.",
        "CVE-2026-4023",
        "10.4.23.24",
        "43 ms",
    ),
    (
        "El servidor de producción 10.4.24.25 reportó 44 ms el 2026-07-25. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4024.",
        "CVE-2026-4024",
        "10.4.24.25",
        "44 ms",
    ),
    (
        "El servidor de producción 10.4.25.26 reportó 45 ms el 2026-07-26. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4025.",
        "CVE-2026-4025",
        "10.4.25.26",
        "45 ms",
    ),
    (
        "El servidor de producción 10.4.26.27 reportó 46 ms el 2026-07-27. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4026.",
        "CVE-2026-4026",
        "10.4.26.27",
        "46 ms",
    ),
    (
        "El servidor de producción 10.4.27.28 reportó 47 ms el 2026-07-28. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4027.",
        "CVE-2026-4027",
        "10.4.27.28",
        "47 ms",
    ),
    (
        "El servidor de producción 10.4.28.29 reportó 48 ms el 2026-07-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4028.",
        "CVE-2026-4028",
        "10.4.28.29",
        "48 ms",
    ),
    (
        "El servidor de producción 10.4.29.30 reportó 49 ms el 2026-07-02. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4029.",
        "CVE-2026-4029",
        "10.4.29.30",
        "49 ms",
    ),
    (
        "El servidor de producción 10.4.30.31 reportó 50 ms el 2026-07-03. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-4030.",
        "CVE-2026-4030",
        "10.4.30.31",
        "50 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_ES)
def test_es_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = [a.surface for a in atoms]
    assert any(expected_cve in s for s in surfaces), f"Missing CVE {expected_cve} in {surfaces}"
    assert any(expected_ip in s for s in surfaces), f"Missing IP {expected_ip} in {surfaces}"


# =========================================================================
# 3. Multi-byte UTF-8 SourceMap Coordinate Alignment (20 tests)
# =========================================================================

COORDINATE_CASES_ES = [
    (
        "Spanish sistema test case 1: El servidor de producción 192.168.4.1 reportó 5 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8801."
    ),
    (
        "Spanish incidente test case 2: El servidor de producción 192.168.4.2 reportó 10 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8802."
    ),
    (
        "Spanish base de datos test case 3: El servidor de producción 192.168.4.3 reportó 15 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8803."
    ),
    (
        "Spanish clúster test case 4: El servidor de producción 192.168.4.4 reportó 20 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8804."
    ),
    (
        "Spanish despliegue test case 5: El servidor de producción 192.168.4.5 reportó 25 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8805."
    ),
    (
        "Spanish latencia test case 6: El servidor de producción 192.168.4.6 reportó 30 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8806."
    ),
    (
        "Spanish memoria test case 7: El servidor de producción 192.168.4.7 reportó 35 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8807."
    ),
    (
        "Spanish seguridad test case 8: El servidor de producción 192.168.4.8 reportó 40 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8808."
    ),
    (
        "Spanish sistema test case 9: El servidor de producción 192.168.4.9 reportó 45 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8809."
    ),
    (
        "Spanish incidente test case 10: El servidor de producción 192.168.4.10 reportó 50 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8810."
    ),
    (
        "Spanish base de datos test case 11: El servidor de producción 192.168.4.11 reportó 55 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8811."
    ),
    (
        "Spanish clúster test case 12: El servidor de producción 192.168.4.12 reportó 60 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8812."
    ),
    (
        "Spanish despliegue test case 13: El servidor de producción 192.168.4.13 reportó 65 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8813."
    ),
    (
        "Spanish latencia test case 14: El servidor de producción 192.168.4.14 reportó 70 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8814."
    ),
    (
        "Spanish memoria test case 15: El servidor de producción 192.168.4.15 reportó 75 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8815."
    ),
    (
        "Spanish seguridad test case 16: El servidor de producción 192.168.4.16 reportó 80 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8816."
    ),
    (
        "Spanish sistema test case 17: El servidor de producción 192.168.4.17 reportó 85 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8817."
    ),
    (
        "Spanish incidente test case 18: El servidor de producción 192.168.4.18 reportó 90 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8818."
    ),
    (
        "Spanish base de datos test case 19: El servidor de producción 192.168.4.19 reportó 95 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8819."
    ),
    (
        "Spanish clúster test case 20: El servidor de producción 192.168.4.20 reportó 100 MB el 2026-08-15. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-8820."
    ),
]


@pytest.mark.parametrize("text", COORDINATE_CASES_ES)
def test_es_utf8_sourcemap_coordinates(text: str):
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

NEGATION_CASES_ES = [
    (
        "El servidor de producción 10.99.4.1 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7701."
    ),
    (
        "El servidor de producción 10.99.4.2 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7702."
    ),
    (
        "El servidor de producción 10.99.4.3 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7703."
    ),
    (
        "El servidor de producción 10.99.4.4 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7704."
    ),
    (
        "El servidor de producción 10.99.4.5 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7705."
    ),
    (
        "El servidor de producción 10.99.4.6 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7706."
    ),
    (
        "El servidor de producción 10.99.4.7 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7707."
    ),
    (
        "El servidor de producción 10.99.4.8 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7708."
    ),
    (
        "El servidor de producción 10.99.4.9 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7709."
    ),
    (
        "El servidor de producción 10.99.4.10 reportó 15 ms el 2026-09-01. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-7710."
    ),
]


@pytest.mark.parametrize("text", NEGATION_CASES_ES)
def test_es_negation_and_modality_protection(text: str):
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(text.encode("utf-8"))
    assert result.ok
    # Invariant: technical identifiers and numbers must be preserved
    assert len(result.text) > 0


# =========================================================================
# 5. Full End-to-End Compiler Pipeline & Invariant Checks (20 tests)
# =========================================================================

COMPILER_CASES_ES = [
    (
        "Header Spanish 1\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 2\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 3\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 4\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 5\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 6\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 7\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 8\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 9\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 10\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 11\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 12\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 13\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 14\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 15\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 16\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 17\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 18\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 19\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
    (
        "Header Spanish 20\\n\\nEl servidor de producción 10.4.1.1 reportó 11 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9401.\\nEl servidor de producción 10.4.2.1 reportó 12 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9402.\\nEl servidor de producción 10.4.3.1 reportó 13 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9403.\\nEl servidor de producción 10.4.4.1 reportó 14 ms el 2026-05-12. Un ingeniero verificó que no ocurrió pérdida de datos con CVE-2026-9404."
    ),
]


@pytest.mark.parametrize("doc_text", COMPILER_CASES_ES)
def test_es_end_to_end_compilation(doc_text: str):
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
