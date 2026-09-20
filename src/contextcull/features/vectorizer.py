"""Multilingual lexical feature extraction and TF-IDF vectorization."""

from __future__ import annotations

from collections.abc import Sequence

import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer

from contextcull.ir.models import CandidateUnit

# Universal multilingual token pattern:
# 1. Unicode words with identifiers/paths/decimals: \b[\w\.:/-]+\b
# 2. CJK / Hangul ideographs & syllables: [\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]
MULTILINGUAL_TOKEN_PATTERN = r"(?u)\b[\w\.:/-]+\b|[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]"


def vectorize_units(units: Sequence[CandidateUnit]) -> sp.csr_matrix:
    """Extracts sparse TF-IDF feature vectors for candidate units across any language.

    Supports Latin (English, German, French, Spanish), Cyrillic, Arabic,
    and non-spaced CJK scripts (Chinese, Japanese, Korean) simultaneously in mixed-language texts.
    """
    if not units:
        return sp.csr_matrix((0, 0), dtype=float)

    texts = [u.text for u in units]
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        token_pattern=MULTILINGUAL_TOKEN_PATTERN,
        sublinear_tf=True,
        min_df=1,
    )
    matrix = vectorizer.fit_transform(texts)
    return sp.csr_matrix(matrix, dtype=float)
