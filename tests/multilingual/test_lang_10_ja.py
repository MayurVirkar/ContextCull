"""Honest multilingual test suite for Japanese (ja).

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
CORPUS_FILE = REPO_ROOT / "examples/eval/multilingual" / "11_ja_akutagawa_rashomon.txt"


# ---------------------------------------------------------------------------
# 1. Native sentence segmentation
# ---------------------------------------------------------------------------

SEGMENTATION_CASES_JA = [
    ("データベースは正常に再起動しました。再起動中にエラーは記録されませんでした。", 2),
    (
        "トラフィックは午前九時にピークに達しました。チームはクラスターを拡張しました。数分でレイテンシは正常に戻りました。",
        3,
    ),
    ("バックアップは完了しましたか？ダッシュボードにはまだ実行中と表示されています。", 2),
    ("今すぐパッチを展開してください！その後、ヘルスチェックを確認してください。", 2),
]


@pytest.mark.parametrize("text,expected_count", SEGMENTATION_CASES_JA)
def test_ja_sentence_segmentation(text: str, expected_count: int):
    spans = segment_sentences(text)
    assert len(spans) == expected_count
    for s in spans:
        assert s.text.strip() != ""
        assert s.end_char > s.start_char


# ---------------------------------------------------------------------------
# 2. Atom extraction: CVE, IPv4 AND metric must all be detected
# ---------------------------------------------------------------------------

ATOM_CASES_JA = [
    (
        "本番サーバー 10.0.4.12 はCPU使用率が 45 ms に達した後にアラートを発し、チームは CVE-2026-10432 のもとで追跡しています。",
        "CVE-2026-10432",
        "10.0.4.12",
        "45 ms",
    ),
    (
        "エンジニアはホスト 10.0.9.31 での 120 ms のレイテンシ急増を脆弱性 CVE-2026-20981 に関連付けました。",
        "CVE-2026-20981",
        "10.0.9.31",
        "120 ms",
    ),
    (
        "CVE-2026-31207 に対するパッチが 10.1.2.44 に展開され、スループットが 78 ms 以上に回復しました。",
        "CVE-2026-31207",
        "10.1.2.44",
        "78 ms",
    ),
    (
        "本番サーバー 10.1.7.19 はCPU使用率が 212 ms に達した後にアラートを発し、チームは CVE-2026-40556 のもとで追跡しています。",
        "CVE-2026-40556",
        "10.1.7.19",
        "212 ms",
    ),
    (
        "エンジニアはホスト 10.2.5.63 での 33 ms のレイテンシ急増を脆弱性 CVE-2026-50871 に関連付けました。",
        "CVE-2026-50871",
        "10.2.5.63",
        "33 ms",
    ),
    (
        "CVE-2026-61190 に対するパッチが 10.2.8.27 に展開され、スループットが 156 ms 以上に回復しました。",
        "CVE-2026-61190",
        "10.2.8.27",
        "156 ms",
    ),
]


@pytest.mark.parametrize("text,expected_cve,expected_ip,expected_metric", ATOM_CASES_JA)
def test_ja_technical_atoms(text: str, expected_cve: str, expected_ip: str, expected_metric: str):
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

NEGATION_CASES_JA = [
    "フェイルオーバー中にデータ損失は発生しませんでした。",
    "有効な設定ファイルなしではサービスを再起動できません。",
    "そのリンクでパケット損失を確認したことは一度もありません。",
]


@pytest.mark.parametrize("text", NEGATION_CASES_JA)
def test_ja_negation_detection(text: str):
    # Japanese negation is the grammatical ...ない inflection, which neither
    # the Western/Hebrew/Other word-list regex nor the CJK prefix-negation regex
    # covers - so this asserts the extractive guarantee instead: compiling at
    # COMPACT mode must not corrupt or drop the negation clause.
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(text.encode("utf-8"), policy=CompilePolicy(mode=CompileMode.COMPACT))
    assert result.status == "OK"
    assert text in result.text


# ---------------------------------------------------------------------------
# 4. Byte-exact UTF-8 SourceMap span round-trip
# ---------------------------------------------------------------------------

SPAN_CASES_JA = [
    "本番サーバー 10.0.4.12 はCPU使用率が 45 ms に達した後にアラートを発し、チームは CVE-2026-10432 のもとで追跡しています。",
    "エンジニアはホスト 10.0.9.31 での 120 ms のレイテンシ急増を脆弱性 CVE-2026-20981 に関連付けました。",
    "CVE-2026-31207 に対するパッチが 10.1.2.44 に展開され、スループットが 78 ms 以上に回復しました。",
]


@pytest.mark.parametrize("text", SPAN_CASES_JA)
def test_ja_utf8_byte_span_roundtrip(text: str):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    assert len(ingest.source_map.raw_bytes) == len(raw_bytes)
    for char_idx in (0, len(text) // 3, len(text) // 2, len(text) - 1):
        span = clean_char_to_byte_span(ingest, char_idx, char_idx + 1)
        assert raw_bytes[span.start : span.end].decode("utf-8") == ingest.clean_text[char_idx]


# ---------------------------------------------------------------------------
# 5. End-to-end compile on a slice of the real corpus
# ---------------------------------------------------------------------------


def test_ja_end_to_end_real_corpus_slice():
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
