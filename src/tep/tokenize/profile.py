"""Tokenizer profiles and accounting adapters."""

from __future__ import annotations

from typing import Protocol

import tiktoken


class TokenizerProfile(Protocol):
    """Protocol for counting tokens under a target model encoding."""

    def count_tokens(self, text: str) -> int:
        """Return the number of tokens for the given text."""
        ...

    def is_exact(self) -> bool:
        """Return True if the tokenizer is an exact model encoding rather than an estimator."""
        ...

    @property
    def profile_name(self) -> str:
        """Identifier of the tokenizer profile."""
        ...


class TiktokenProfile:
    """Exact tokenizer profile using OpenAI tiktoken."""

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self._encoding_name = encoding_name
        try:
            self._encoding = tiktoken.get_encoding(encoding_name)
        except ValueError:
            self._encoding = tiktoken.encoding_for_model(encoding_name)

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoding.encode(text, disallowed_special=()))

    def is_exact(self) -> bool:
        return True

    @property
    def profile_name(self) -> str:
        return f"openai:{self._encoding_name}"


class HeuristicProfile:
    """Fast offline heuristic token estimator (~4 chars per token)."""

    def __init__(self, name: str = "heuristic:4char") -> None:
        self._name = name

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        # Estimate based on word count + character count average
        words = len(text.split())
        chars = len(text)
        # Average of char/4 and word * 1.3
        return max(1, (chars // 4 + int(words * 1.3)) // 2)

    def is_exact(self) -> bool:
        return False

    @property
    def profile_name(self) -> str:
        return self._name


def get_tokenizer(profile: str) -> TokenizerProfile:
    """Factory to retrieve or instantiate a TokenizerProfile by identifier."""
    clean = profile.strip().lower()

    if clean.startswith("openai:"):
        model_or_enc = profile.split(":", 1)[1]
        return TiktokenProfile(model_or_enc)
    elif clean in ("cl100k_base", "o200k_base", "p50k_base", "r50k_base", "gpt-4", "gpt-4o", "gpt-3.5-turbo"):
        return TiktokenProfile(profile)
    elif clean.startswith("heuristic"):
        return HeuristicProfile(profile)
    else:
        # Default fallback to heuristic estimator
        return HeuristicProfile(f"heuristic:{profile}")
