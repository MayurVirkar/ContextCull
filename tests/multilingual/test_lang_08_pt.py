"""Honest multilingual test suite for Portuguese (pt).

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
CORPUS_FILE = REPO_ROOT / "examples/eval/multilingual" / "09_pt_dom_casmurro.txt"


# ---------------------------------------------------------------------------
# 1. Native sentence segmentation
# ---------------------------------------------------------------------------

SEGMENTATION_CASES_PT = [
    (
        "O banco de dados reiniciou corretamente. Nenhum erro foi registrado durante a reinicialização.",
        2,
    ),
    (
        "O tráfego atingiu o pico às nove da manhã. A equipe escalou o cluster. A latência voltou ao normal em minutos.",
        3,
    ),
    ("O backup foi concluído? O painel ainda mostra que está em execução.", 2),
    ("Implante o patch agora! Verifique a checagem de integridade depois.", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_PT)
def test_pt_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# ---------------------------------------------------------------------------
# 2. Atom extraction: CVE, IPv4 AND metric must all be detected
# ---------------------------------------------------------------------------

ATOM_CASES_PT = [
    (
        "O servidor de produção 10.0.4.12 emitiu um alerta após o uso de CPU atingir 45 ms, e a equipe está rastreando isso sob CVE-2026-10432.",
        "CVE-2026-10432",
        "10.0.4.12",
        "45 ms",
    ),
    (
        "Os engenheiros associaram o pico de latência de 120 ms no host 10.0.9.31 à vulnerabilidade CVE-2026-20981.",
        "CVE-2026-20981",
        "10.0.9.31",
        "120 ms",
    ),
    (
        "Um patch para CVE-2026-31207 foi implantado em 10.1.2.44, restaurando a taxa de transferência acima de 78 ms.",
        "CVE-2026-31207",
        "10.1.2.44",
        "78 ms",
    ),
    (
        "O servidor de produção 10.1.7.19 emitiu um alerta após o uso de CPU atingir 212 ms, e a equipe está rastreando isso sob CVE-2026-40556.",
        "CVE-2026-40556",
        "10.1.7.19",
        "212 ms",
    ),
    (
        "Os engenheiros associaram o pico de latência de 33 ms no host 10.2.5.63 à vulnerabilidade CVE-2026-50871.",
        "CVE-2026-50871",
        "10.2.5.63",
        "33 ms",
    ),
    (
        "Um patch para CVE-2026-61190 foi implantado em 10.2.8.27, restaurando a taxa de transferência acima de 156 ms.",
        "CVE-2026-61190",
        "10.2.8.27",
        "156 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_PT)
def test_pt_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
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

NEGATION_CASES_PT = [
    "Nenhuma perda de dados ocorreu durante o failover.",
    "O serviço não pode reiniciar sem um arquivo de configuração válido.",
    "Nunca observamos perda de pacotes nesse link.",
]


@pytest.mark.parametrize("text", NEGATION_CASES_PT)
def test_pt_negation_detection(text: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    kinds = [a.kind for a in atoms if a.kind in ("negation", "bound_negation")]
    assert "negation" in kinds, f"Expected a 'negation' atom, got kinds={kinds} for {text!r}"


# ---------------------------------------------------------------------------
# 4. Byte-exact UTF-8 SourceMap span round-trip
# ---------------------------------------------------------------------------

SPAN_CASES_PT = [
    "O servidor de produção 10.0.4.12 emitiu um alerta após o uso de CPU atingir 45 ms, e a equipe está rastreando isso sob CVE-2026-10432.",
    "Os engenheiros associaram o pico de latência de 120 ms no host 10.0.9.31 à vulnerabilidade CVE-2026-20981.",
    "Um patch para CVE-2026-31207 foi implantado em 10.1.2.44, restaurando a taxa de transferência acima de 78 ms.",
]


@pytest.mark.parametrize("text", SPAN_CASES_PT)
def test_pt_utf8_byte_span_roundtrip(text: str):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)
    for char_idx in (0, len(text) // 3, len(text) // 2, len(text) - 1):
        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        assert raw_bytes[span.start : span.end].decode("utf-8") == ingest.clean_text[char_idx]


# ---------------------------------------------------------------------------
# 5. End-to-end compile on a slice of the real corpus
# ---------------------------------------------------------------------------


def test_pt_end_to_end_real_corpus_slice():
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
