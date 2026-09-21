"""Honest multilingual test suite for Chinese (zh).

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
CORPUS_FILE = REPO_ROOT / "examples/eval/multilingual" / "03_zh_journey_to_the_west.txt"


# ---------------------------------------------------------------------------
# 1. Native sentence segmentation
# ---------------------------------------------------------------------------

SEGMENTATION_CASES_ZH = [
    ("数据库已顺利重启。重启过程中没有记录任何错误。", 2),
    ("流量在上午九点达到峰值。团队扩展了集群。延迟在几分钟内恢复正常。", 3),
    ("备份完成了吗？仪表盘仍然显示它在运行。", 2),
    ("现在部署补丁！之后请验证健康检查。", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_ZH)
def test_zh_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# ---------------------------------------------------------------------------
# 2. Atom extraction: CVE, IPv4 AND metric must all be detected
# ---------------------------------------------------------------------------

ATOM_CASES_ZH = [
    (
        "生产服务器 10.0.4.12 在CPU使用率达到 45 ms 后发出警报，团队正在通过 CVE-2026-10432 跟踪此事件。",
        "CVE-2026-10432",
        "10.0.4.12",
        "45 ms",
    ),
    (
        "工程师将主机 10.0.9.31 上 120 ms 的延迟峰值与漏洞 CVE-2026-20981 联系起来。",
        "CVE-2026-20981",
        "10.0.9.31",
        "120 ms",
    ),
    (
        "针对 CVE-2026-31207 的补丁已部署到 10.1.2.44，吞吐量恢复到 78 ms 以上。",
        "CVE-2026-31207",
        "10.1.2.44",
        "78 ms",
    ),
    (
        "生产服务器 10.1.7.19 在CPU使用率达到 212 ms 后发出警报，团队正在通过 CVE-2026-40556 跟踪此事件。",
        "CVE-2026-40556",
        "10.1.7.19",
        "212 ms",
    ),
    (
        "工程师将主机 10.2.5.63 上 33 ms 的延迟峰值与漏洞 CVE-2026-50871 联系起来。",
        "CVE-2026-50871",
        "10.2.5.63",
        "33 ms",
    ),
    (
        "针对 CVE-2026-61190 的补丁已部署到 10.2.8.27，吞吐量恢复到 156 ms 以上。",
        "CVE-2026-61190",
        "10.2.8.27",
        "156 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_ZH)
def test_zh_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
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

NEGATION_CASES_ZH = [
    "故障转移期间没有数据丢失。",
    "服务器在未获授权的情况下无法访问数据库。",
    "该链路从未出现丢包现象。",
]


@pytest.mark.parametrize("text", NEGATION_CASES_ZH)
def test_zh_negation_detection(text: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    kinds = [a.kind for a in atoms if a.kind in ("negation", "bound_negation")]
    assert "bound_negation" in kinds, (
        f"Expected a 'bound_negation' atom, got kinds={kinds} for {text!r}"
    )


# ---------------------------------------------------------------------------
# 4. Byte-exact UTF-8 SourceMap span round-trip
# ---------------------------------------------------------------------------

SPAN_CASES_ZH = [
    "生产服务器 10.0.4.12 在CPU使用率达到 45 ms 后发出警报，团队正在通过 CVE-2026-10432 跟踪此事件。",
    "工程师将主机 10.0.9.31 上 120 ms 的延迟峰值与漏洞 CVE-2026-20981 联系起来。",
    "针对 CVE-2026-31207 的补丁已部署到 10.1.2.44，吞吐量恢复到 78 ms 以上。",
]


@pytest.mark.parametrize("text", SPAN_CASES_ZH)
def test_zh_utf8_byte_span_roundtrip(text: str):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)
    for char_idx in (0, len(text) // 3, len(text) // 2, len(text) - 1):
        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        assert raw_bytes[span.start : span.end].decode("utf-8") == ingest.clean_text[char_idx]


# ---------------------------------------------------------------------------
# 5. End-to-end compile on a slice of the real corpus
# ---------------------------------------------------------------------------


def test_zh_end_to_end_real_corpus_slice():
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
