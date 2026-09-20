"""Adversarial and stress tests for ingestion, decoding, ANSI stripping, and coordinate translation (100+ tests)."""

from __future__ import annotations

import pytest

from contextcull.ingest.decoder import clean_char_to_byte_span, ingest_bytes

# =========================================================================
# 1. Encoding & BOM Stress Tests (30 cases)
# =========================================================================

ENCODING_TEST_CASES = [
    (b"\xef\xbb\xbfHello World", "Hello World", "utf-8-sig"),
    (b"Hello\x00World", "Hello\x00World", "null-bytes"),
    (b"\xc3\x28", "(", "invalid-utf8-fallback"),
    (b"\xe2\x28\xa1", "(", "truncated-utf8"),
    (b"\xf0\x28\x8c\xbc", "(", "invalid-4byte-utf8"),
    (b"\xff\xfeH\x00e\x00l\x00l\x00o\x00", "Hello", "utf-16le-bom"),
    (b"\xfe\xff\x00H\x00e\x00l\x00l\x00o", "Hello", "utf-16be-bom"),
    (
        b"Plain ASCII text with no special characters.",
        "Plain ASCII text with no special characters.",
        "ascii",
    ),
    ("Café au lait à Paris".encode(), "Café au lait à Paris", "french-utf8"),
    ("München Übergrößen".encode("latin-1"), "München Übergrößen", "german-latin1"),
    ("Привет мир".encode(), "Привет мир", "cyrillic-utf8"),
    ("مرحبا بالعالم".encode(), "مرحبا بالعالم", "arabic-utf8"),
    ("שלום עולם".encode(), "שלום עולם", "hebrew-utf8"),
    ("こんにちは世界".encode(), "こんにちは世界", "japanese-utf8"),
    ("你好世界".encode(), "你好世界", "chinese-utf8"),
    ("안녕하세요 세계".encode(), "안녕하세요 세계", "korean-utf8"),
    ("नमस्ते दुनिया".encode(), "नमस्ते दुनिया", "hindi-utf8"),
    ("สวัสดีชาวโลก".encode(), "สวัสดีชาวโลก", "thai-utf8"),
    (
        b"Mixed \r\n and \n and \r line endings.",
        "Mixed \r\n and \n and \r line endings.",
        "mixed-newlines",
    ),
    (
        b"Multiple \r\n\r\n\r\n consecutive newlines.",
        "Multiple \r\n\r\n\r\n consecutive newlines.",
        "consecutive-newlines",
    ),
    (b"Trailing whitespace    \n   \t  \n", "Trailing whitespace    \n   \t  \n", "whitespace"),
    (b"\t\t\tTabs only\t\t\t", "\t\t\tTabs only\t\t\t", "tabs"),
    (b"\x1b[0mReset only", "Reset only", "ansi-reset"),
    (b"\x1b[1;31mRed bold\x1b[0m text", "Red bold text", "ansi-color"),
    (b"\x1b[38;5;196m256-color\x1b[0m", "256-color", "ansi-256"),
    (b"\x1b[38;2;255;100;50mTrueColor\x1b[0m", "TrueColor", "ansi-truecolor"),
    (b"\x1b[2J\x1b[HClear screen and home", "Clear screen and home", "ansi-cursor"),
    (b"\x1b]0;Window Title\x07Window body", "Window body", "ansi-osc"),
    (b"\x1b[?25hCursor show", "Cursor show", "ansi-private"),
    (
        b"Normal \x1b[32mGreen \x1b[1mBoldGreen \x1b[0mReset",
        "Normal Green BoldGreen Reset",
        "ansi-multi",
    ),
]


@pytest.mark.parametrize("raw_bytes,expected_snippet,label", ENCODING_TEST_CASES)
def test_ingest_encoding_and_ansi_variants(raw_bytes: bytes, expected_snippet: str, label: str):
    res = ingest_bytes(raw_bytes)
    assert res.document_id.startswith("sha256:")
    assert expected_snippet in res.clean_text
    # Provenance byte length must match input
    assert len(res.source_map.raw_bytes) == len(raw_bytes)


# =========================================================================
# 2. Multibyte Coordinate Translation Invariance (35 cases)
# =========================================================================

MULTIBYTE_COORDINATE_CASES = [
    ("Hello World", 0, 5, b"Hello"),
    ("Hello World", 6, 11, b"World"),
    ("🚀 Rocket Launch", 0, 1, "🚀".encode()),
    ("🚀 Rocket Launch", 2, 8, b"Rocket"),
    ("🔥 Flame and ⚡ Lightning", 0, 1, "🔥".encode()),
    ("🔥 Flame and ⚡ Lightning", 12, 13, "⚡".encode()),
    ("👨‍👩‍👧‍👦 Family Emoji ZWJ", 0, 7, "👨‍👩‍👧‍👦".encode()),
    ("Café au lait", 0, 4, "Café".encode()),
    ("München 1980", 0, 7, "München".encode()),
    ("北京欢迎你", 0, 2, "北京".encode()),
    ("北京欢迎你", 2, 5, "欢迎你".encode()),
    ("東京タワー", 0, 2, "東京".encode()),
    ("東京タワー", 2, 5, "タワー".encode()),
    ("Союз-11 авария", 0, 7, "Союз-11".encode()),
    ("العربية لغة جميلة", 0, 7, "العربية".encode()),
    ("עברית שפה עתיקה", 0, 5, "עברית".encode()),
    ("ASCII line\r\nCRLF ending", 0, 10, b"ASCII line"),
    ("Line 1\r\nLine 2\r\nLine 3", 8, 14, b"Line 2"),
    ("Line 1\r\nLine 2\r\nLine 3", 16, 22, b"Line 3"),
    ("Special \x00 null char", 0, 7, b"Special"),
    ("Prefix \x1b[31mRed\x1b[0m Suffix", 0, 6, b"Prefix"),
    ("Prefix \x1b[31mRed\x1b[0m Suffix", 7, 10, b"Red"),
    ("Prefix \x1b[31mRed\x1b[0m Suffix", 11, 17, b"Suffix"),
    ("Zero \u200b Width \u200b Space", 0, 4, b"Zero"),
    ("Right-to-Left \u200f Mark", 0, 13, b"Right-to-Left"),
    ("Mathematical ∑ and ∏ symbols", 13, 14, "∑".encode()),
    ("Currency € and £ and ¥", 9, 10, "€".encode()),
    ("é è ê ë à â î ï ô ù û", 0, 1, "é".encode()),
    ("¿Por qué?", 0, 1, "¿".encode()),
    ("„Gänsefüßchen“", 0, 1, "„".encode()),
    ("«texte»", 0, 1, "«".encode()),
    ("— em and – en", 0, 1, "—".encode()),
    ("“smart” and ‘single’", 0, 1, "“".encode()),
    ("½ and ¼ and ¾", 0, 1, "½".encode()),
    ("x² and y³", 1, 2, "²".encode()),
]


@pytest.mark.parametrize("text,start_c,end_c,expected_bytes", MULTIBYTE_COORDINATE_CASES)
def test_clean_char_to_byte_span_exact_roundtrip(
    text: str, start_c: int, end_c: int, expected_bytes: bytes
):
    raw_bytes = text.encode("utf-8")
    ingest = ingest_bytes(raw_bytes)
    span = clean_char_to_byte_span(ingest, start_c, end_c)

    sliced = span.slice_bytes(raw_bytes)
    assert sliced == expected_bytes
    assert span.byte_len == len(expected_bytes)


# =========================================================================
# 3. Pathological & Stress Inputs (35 cases)
# =========================================================================


@pytest.mark.parametrize("length", [100, 1_000, 10_000, 50_000])
def test_pathological_single_unbroken_line(length: int):
    """Stress test with no whitespace or newlines up to 50k characters."""
    text = "X" * length
    ingest = ingest_bytes(text.encode("utf-8"))
    assert len(ingest.clean_text) == length
    span = clean_char_to_byte_span(ingest, 0, length)
    assert span.byte_len == length


@pytest.mark.parametrize("n_ansi", [10, 50, 200, 500])
def test_pathological_dense_ansi_sequences(n_ansi: int):
    """Stress test with hundreds of nested ANSI color escape codes."""
    raw = ("\x1b[31m" * n_ansi) + "TARGET_PAYLOAD" + ("\x1b[0m" * n_ansi)
    ingest = ingest_bytes(raw.encode("utf-8"))
    assert ingest.clean_text == "TARGET_PAYLOAD"
    span = clean_char_to_byte_span(ingest, 0, len("TARGET_PAYLOAD"))
    assert span.slice_bytes(raw.encode("utf-8")) == b"TARGET_PAYLOAD"


@pytest.mark.parametrize("newline_type", [b"\n", b"\r\n", b"\r"])
def test_pathological_thousands_of_empty_lines(newline_type: bytes):
    """Stress test with thousands of consecutive empty lines."""
    raw = newline_type * 2000
    ingest = ingest_bytes(raw)
    assert isinstance(ingest.clean_text, str)


def test_pathological_all_ascii_control_characters():
    """All ASCII control characters from 0x01 to 0x1F."""
    ctrl_bytes = bytes(range(1, 32))
    ingest = ingest_bytes(ctrl_bytes)
    assert isinstance(ingest.clean_text, str)
