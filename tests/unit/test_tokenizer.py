"""Unit tests for tokenizer profiles."""

from tep.tokenize.profile import HeuristicProfile, TiktokenProfile, get_tokenizer


def test_tiktoken_profile():
    tok = TiktokenProfile("cl100k_base")
    assert tok.is_exact()
    assert tok.profile_name == "openai:cl100k_base"

    text = "Hello world! This is a test."
    tokens = tok.count_tokens(text)
    assert tokens > 0
    assert tok.count_tokens("") == 0


def test_heuristic_profile():
    tok = HeuristicProfile()
    assert not tok.is_exact()
    assert tok.count_tokens("Hello world! This is a test.") > 0
    assert tok.count_tokens("") == 0


def test_get_tokenizer_factory():
    t1 = get_tokenizer("openai:gpt-4o")
    assert isinstance(t1, TiktokenProfile)

    t2 = get_tokenizer("heuristic:custom")
    assert isinstance(t2, HeuristicProfile)
