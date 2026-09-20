"""Language detection for monolingual and mixed-language documents."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from lingua import Language, LanguageDetectorBuilder

logger = logging.getLogger(__name__)

# Pre-configure common languages for fast, high-accuracy detection
_COMMON_LANGUAGES = [
    Language.ENGLISH,
    Language.GERMAN,
    Language.FRENCH,
    Language.SPANISH,
    Language.ITALIAN,
    Language.PORTUGUESE,
    Language.DUTCH,
    Language.RUSSIAN,
    Language.CHINESE,
    Language.JAPANESE,
    Language.KOREAN,
    Language.ARABIC,
]

_DETECTOR = (
    LanguageDetectorBuilder.from_languages(*_COMMON_LANGUAGES)
    .with_minimum_relative_distance(0.1)
    .build()
)


def detect_document_language(text: str) -> str:
    """Detects the primary language of a document. Returns ISO 639-1 code (e.g. 'en', 'de', 'zh')."""
    if not text.strip():
        return "en"
    lang = _DETECTOR.detect_language_of(text)
    if lang is not None:
        return lang.iso_code_639_1.name.lower()
    return "en"


def detect_sentence_languages(sentences: Sequence[str]) -> list[str]:
    """Detects the language of each sentence in a mixed-language document or email thread."""
    results: list[str] = []
    for s in sentences:
        s_clean = s.strip()
        if len(s_clean) < 15:
            # Fallback to English or default for very short snippets/numbers
            results.append("en")
            continue
        lang = _DETECTOR.detect_language_of(s_clean)
        results.append(lang.iso_code_639_1.name.lower() if lang else "en")
    return results
