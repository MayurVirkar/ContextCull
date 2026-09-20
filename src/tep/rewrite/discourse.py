"""Deterministic discourse and bureaucratic scaffolding pruner for multilingual documents."""

from __future__ import annotations

import re

# Comprehensive catalog of corporate, academic, and bureaucratic filler preambles
# Supports English, German, French, Spanish, and mixed-language documents
DISCOURSE_PREAMBLES = [
    # English Preambles
    re.compile(r"^(?:OpenAI|Responders|The team|Investigators)\s+(?:determined|found|noted|observed|identified|concluded)\s+that,?\s*", re.IGNORECASE),
    re.compile(r"^It\s+is\s+(?:important|worth|critical|notable)\s+to\s+note\s+that,?\s*", re.IGNORECASE),
    re.compile(r"^It\s+should\s+be\s+noted\s+that,?\s*", re.IGNORECASE),
    re.compile(r"^As\s+(?:previously|earlier|already)\s+(?:explained|described|noted|mentioned)(?:\s+in\s+Section\s+[A-Z0-9]+)?,?\s*", re.IGNORECASE),
    re.compile(r"^In\s+(?:the\s+course|furtherance)\s+of\s+(?:carrying\s+out\s+)?(?:the\s+[^,]+),?\s*", re.IGNORECASE),
    re.compile(r"^For\s+these\s+reviews,?\s*", re.IGNORECASE),
    re.compile(r"^With\s+the\s+benefit\s+of\s+hindsight,?\s*", re.IGNORECASE),
    re.compile(r"^The\s+goal\s+of\s+the\s+evaluation\s+is\s+to\s*", re.IGNORECASE),
    re.compile(r"^During\s+these\s+evaluations,?\s*(?:however,?)?\s*", re.IGNORECASE),
    re.compile(r"^In\s+particular,?\s*", re.IGNORECASE),
    re.compile(r"^Additionally,?\s*", re.IGNORECASE),
    re.compile(r"^Furthermore,?\s*", re.IGNORECASE),
    re.compile(r"^Moreover,?\s*", re.IGNORECASE),
    re.compile(r"^Specifically,?\s*", re.IGNORECASE),
    re.compile(r"^According\s+to\s+(?:the\s+investigation|the\s+report|OpenAI|findings),?\s*", re.IGNORECASE),
    re.compile(r"^In\s+order\s+to\s+(?:ensure|verify|investigate)\s+that,?\s*", re.IGNORECASE),
    re.compile(r"^As\s+a\s+result\s+of\s+(?:this|these)\s+(?:actions|findings),?\s*", re.IGNORECASE),

    # German Preambles (Kanzleideutsch)
    re.compile(r"^(?:Es\s+ist\s+(?:darauf\s+hinzuweisen|zu\s+beachten|festzuhalten),\s+dass,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Es\s+sollte\s+beachtet\s+werden,\s+dass,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Wie\s+(?:bereits|oben)\s+(?:erwähnt|beschrieben|ausgeführt),?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Im\s+Rahmen\s+der\s+(?:Durchführung|Untersuchung)\s+von\s+[^,]+,?\s*)", re.IGNORECASE),

    # French Preambles (Langage administratif)
    re.compile(r"^(?:Il\s+convient\s+de\s+(?:noter|souligner)\s+que,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Il\s+est\s+à\s+noter\s+que,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Comme\s+(?:mentionné|indiqué)\s+précédemment,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Dans\s+le\s+cadre\s+de\s+[^,]+,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Il\s+faut\s+garder\s+à\s+l'esprit\s+que,?\s*)", re.IGNORECASE),

    # Spanish Preambles (Lenguaje administrativo)
    re.compile(r"^(?:Cabe\s+(?:señalar|destacar|resaltar)\s+que,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Es\s+importante\s+(?:tener\s+en\s+cuenta|notar)\s+que,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Como\s+se\s+(?:mencionó|indicó)\s+anteriormente,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:En\s+el\s+marco\s+de\s+[^,]+,?\s*)", re.IGNORECASE),
    re.compile(r"^(?:Es\s+preciso\s+mencionar\s+que,?\s*)", re.IGNORECASE),
]

BOILERPLATE_PATTERNS = [
    re.compile(r"^OpenAI\s*–\s*Hugging\s*Face\s*(?:Incident)?$", re.IGNORECASE),
    re.compile(r"^Technical\s*Report$", re.IGNORECASE),
    re.compile(r"^OpenAI$", re.IGNORECASE),
    re.compile(r"^\d{1,3}$"),  # Isolated page numbers
    # Table of Contents across languages (EN, DE, FR, ES, ZH, JA)
    re.compile(r"^(?:Table of Contents|Inhaltsverzeichnis|Table des matières|Índice|Tabla de contenidos|目录|目次)$", re.IGNORECASE),
    re.compile(r"^[I|V|X]+\.\s+.*?\s+\d+$"),  # TOC entries
    re.compile(r"^[A-Z]\.\s+.*?\s+\d+$"),    # TOC entries
]


def is_structural_boilerplate(text: str) -> bool:
    """Checks if a text block is pure structural boilerplate (headers, footers, page numbers, TOC)."""
    t = text.strip()
    if not t or len(t) < 3:
        return True
    return any(pat.match(t) for pat in BOILERPLATE_PATTERNS)


def prune_discourse_scaffolding(text: str) -> str:
    """Strips leading bureaucratic framing and hedging phrases while preserving the core factual clause."""
    cleaned = text.strip()
    for pat in DISCOURSE_PREAMBLES:
        cleaned = pat.sub("", cleaned)
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned
