"""Tests for universal multilingual segmentation, detection, vectorization, and pruning."""

from __future__ import annotations

from tep.detect.language import detect_document_language, detect_sentence_languages
from tep.features.vectorizer import vectorize_units
from tep.ir.models import CandidateUnit
from tep.ir.spans import ByteSpan
from tep.rewrite.discourse import prune_discourse_scaffolding
from tep.segment.sentence import segment_sentences


def test_multilingual_sentence_segmentation() -> None:
    text = (
        "OpenAI detected an intrusion on host 10.0.0.1. "
        "Z.B. wurden Kubernetes-Tokens gestohlen! "
        "多智能体系统在没有人类干预的情况下自主运行。 "
        "Il convient de noter que l'accès a été coupé. "
        "¿Qué pasó? ¡Fue un ataque grave! "
        "2026-07-11 14:00 UTC."
    )
    spans = segment_sentences(text)
    assert len(spans) >= 6

    # Verify that offsets match text exactly
    for s in spans:
        assert text[s.start_char : s.end_char] == s.text

    texts = [s.text for s in spans]
    assert any("OpenAI detected" in t for t in texts)
    assert any("Kubernetes-Tokens" in t for t in texts)
    assert any("多智能体系统" in t for t in texts)
    assert any("Il convient de noter" in t for t in texts)
    assert any("¿Qué pasó?" in t for t in texts)


def test_language_detection_mixed_text() -> None:
    doc_en = "OpenAI published an extensive technical incident report detailing security evaluations."
    doc_de = "Es ist darauf hinzuweisen, dass die Sicherheitsmaßnahmen im Cluster versagt haben."
    doc_zh = "自主攻击性智能体系统在无需人类干预的情况下完成了多阶段网络攻击。"

    assert detect_document_language(doc_en) == "en"
    assert detect_document_language(doc_de) == "de"
    assert detect_document_language(doc_zh) == "zh"

    sentences = [doc_en, doc_de, doc_zh]
    detected = detect_sentence_languages(sentences)
    assert detected == ["en", "de", "zh"]


def test_multilingual_vectorization() -> None:
    units = [
        CandidateUnit("u1", "b1", (ByteSpan("doc1", 0, 10),), "OpenAI detected an intrusion on host 10.0.0.1."),
        CandidateUnit("u2", "b1", (ByteSpan("doc1", 10, 20),), "Die Überprüfung der Sicherheitsmaßnahmen ist fehlgeschlagen."),
        CandidateUnit("u3", "b1", (ByteSpan("doc1", 20, 30),), "La organización confirmó el ataque cibernético."),
        CandidateUnit("u4", "b1", (ByteSpan("doc1", 30, 40),), "多智能体系统自主运行并发现了安全漏洞。"),
    ]
    matrix = vectorize_units(units)
    assert matrix.shape[0] == 4
    assert matrix.shape[1] > 20  # Extracted features across all scripts


def test_multilingual_discourse_pruning() -> None:
    en_raw = "OpenAI determined that the models exploited a legacy endpoint."
    assert prune_discourse_scaffolding(en_raw) == "The models exploited a legacy endpoint."

    de_raw = "Es ist darauf hinzuweisen, dass die Tokens gestohlen wurden."
    assert prune_discourse_scaffolding(de_raw) == "Die Tokens gestohlen wurden."

    fr_raw = "Il convient de noter que l'accès a été révoqué."
    assert prune_discourse_scaffolding(fr_raw) == "L'accès a été révoqué."

    es_raw = "Cabe señalar que los administradores actuaron rápidamente."
    assert prune_discourse_scaffolding(es_raw) == "Los administradores actuaron rápidamente."
