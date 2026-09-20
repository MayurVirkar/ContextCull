"""Source code block parsing and test case signature extraction."""

from __future__ import annotations

import re

from contextcull.ingest.decoder import IngestionResult, clean_char_to_byte_span
from contextcull.ir.models import Block, BlockKind

CODE_INDICATOR_RE = re.compile(
    r"^\s*(?:"
    r"#\[test\]|#\[tokio::test\]|"
    r"def\s+[a-zA-Z_]\w*\s*\(|"
    r"async\s+def\s+[a-zA-Z_]\w*\s*\(|"
    r"class\s+[a-zA-Z_]\w*[:\(]|"
    r"@\w+|"
    r"fn\s+[a-zA-Z_]\w*(?:<[^>]+>)?\s*\(|"
    r"pub\s+(?:struct|fn|enum)\s+[a-zA-Z_]\w*|"
    r"struct\s+[a-zA-Z_]\w*\s*\{|"
    r"impl\s+[a-zA-Z_]\w*|"
    r"enum\s+[a-zA-Z_]\w*\s*\{|"
    r"export\s+(?:interface|type|function)\s+[a-zA-Z_]\w*|"
    r"package\s+[a-zA-Z_]\w*\b|"
    r"func\s+(?:\([^\)]+\)\s*)?[a-zA-Z_]\w*\s*\(|"
    r"import\s+[a-zA-Z_]\w*|"
    r"from\s+[a-zA-Z_]\w*\s+import|"
    r"type\s+[a-zA-Z_]\w*(?:<[^>]+>)?\s*(?:struct|=)|"
    r"(?:it|test)\s*\(\s*['\"]"
    r")",
    re.MULTILINE,
)

FN_SIGNATURE_RE = re.compile(
    r"(?:fn\s+([a-zA-Z0-9_]+)(?:<[^>]+>)?\s*\(|def\s+([a-zA-Z0-9_]+)\s*\(|(?:it|test)\(\s*['\"]([^'\"]+)['\"])"
)

ASSERT_RE = re.compile(r"(?:assert_eq!\s*\(([^,]+),\s*([^)]+)\)|assert\s+([^;\n]+))")


def is_code_input(text: str) -> bool:
    return bool(CODE_INDICATOR_RE.search(text))


CODE_TEST_MARKER_RE = re.compile(
    r"(?:#\[test\]|#\[tokio::test\]|def test_[a-zA-Z0-9_]+\(|it\(['\"]|test\(['\"])"
)


def parse_code_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses code text into structured test case summaries or source code blocks."""
    clean_text = ingest.clean_text
    blocks: list[Block] = []

    # If it's a test file, extract test functions and asserts
    if CODE_TEST_MARKER_RE.search(clean_text):
        fn_matches = list(FN_SIGNATURE_RE.finditer(clean_text))
        if fn_matches:
            for match in fn_matches:
                name = match.group(1) or match.group(2) or match.group(3) or "test"
                start_c = match.start()
                next_m = [m for m in fn_matches if m.start() > start_c]
                end_c = next_m[0].start() if next_m else len(clean_text)

                fn_body = clean_text[start_c:end_c]
                span = clean_char_to_byte_span(ingest, start_c, end_c)

                asserts: list[str] = []
                for a_match in ASSERT_RE.finditer(fn_body):
                    if a_match.group(1) and a_match.group(2):
                        asserts.append(
                            f"assert: {a_match.group(1).strip()} == {a_match.group(2).strip()}"
                        )
                    elif a_match.group(3):
                        asserts.append(f"assert: {a_match.group(3).strip()}")

                summary_lines = [f"test: {name}"]
                summary_lines.extend(asserts)

                blocks.append(
                    Block(
                        block_id=f"block_{len(blocks):04d}_code_test",
                        kind=BlockKind.CODE,
                        sources=(span,),
                        text="\n".join(summary_lines),
                        metadata={"test_name": name, "assert_count": len(asserts)},
                    )
                )
            return blocks

    # Emit source code block
    span = clean_char_to_byte_span(ingest, 0, len(clean_text))
    return [
        Block(
            block_id="block_0000_code",
            kind=BlockKind.CODE,
            sources=(span,),
            text=clean_text.strip(),
        )
    ]
