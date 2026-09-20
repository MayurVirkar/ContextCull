"""Log parsing and test runner extraction (Cargo, Pytest, Vitest, Go test)."""

from __future__ import annotations

import re

from tep.ingest.decoder import IngestionResult, clean_char_to_byte_span
from tep.ir.models import Block, BlockKind

# Test runner patterns
CARGO_TEST_HEADER_RE = re.compile(r"running \d+ tests?")
CARGO_TEST_RESULT_RE = re.compile(
    r"test result:\s*(FAILED|ok)\.\s*(\d+)\s*passed;\s*(\d+)\s*failed;\s*(\d+)\s*ignored.*finished in\s*([\d\.]+\w*)"
)
CARGO_FAILURE_LINE_RE = re.compile(r"test\s+([^\s]+)\s+\.\.\.\s+FAILED")
CARGO_ASSERT_FAIL_RE = re.compile(r"assertion `left == right` failed\s*\n\s*left:\s*(.+)\s*\n\s*right:\s*(.+)")
CARGO_LOCATION_RE = re.compile(r"panicked at ([^:]+:\d+:\d+):")

PYTEST_HEADER_RE = re.compile(r"==+ test session starts =+")
PYTEST_RESULT_RE = re.compile(r"=+\s*(?:(\d+)\s*failed,?\s*)?(?:(\d+)\s*passed,?\s*)?.*in\s*([\d\.]+s)\s*=+")
PYTEST_FAIL_LOCATION_RE = re.compile(r"([a-zA-Z0-9_\.\-/]+:\d+):\s*AssertionError")
PYTEST_ASSERT_RE = re.compile(r"E\s+assert\s+(.+)\s*==\s*(.+)")

VITEST_FAIL_RE = re.compile(r"FAIL\s+([^\n]+)")
VITEST_EXPECT_RE = re.compile(r"- Expected:\s*\n\s*([^\n]+)\s*\n\+\s*Received:\s*\n\s*([^\n]+)")
VITEST_LOCATION_RE = re.compile(r"❯\s+([^\s:]+:\d+:\d+)")
VITEST_RESULT_RE = re.compile(r"Tests\s+(?:(\d+)\s*failed)?\s*\|\s*(\d+)\s*passed.*Duration\s+([\d\.]+\w*)")


def is_test_log(text: str) -> bool:
    return bool(
        CARGO_TEST_HEADER_RE.search(text)
        or PYTEST_HEADER_RE.search(text)
        or "FAIL " in text
        or "=== RUN" in text
    )


def parse_test_log_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses test runner output into structured summary blocks and failure event blocks."""
    clean_text = ingest.clean_text
    blocks: list[Block] = []

    # 1. Cargo test
    if CARGO_TEST_HEADER_RE.search(clean_text):
        res_match = CARGO_TEST_RESULT_RE.search(clean_text)
        passed = int(res_match.group(2)) if res_match else 0
        failed = int(res_match.group(3)) if res_match else 0
        duration = res_match.group(5) if res_match else ""

        summary_line = f"✓ {passed} · ✗ {failed}"
        if duration:
            summary_line += f" · {duration}"

        # Find failures
        for fail_match in CARGO_FAILURE_LINE_RE.finditer(clean_text):
            test_name = fail_match.group(1)
            loc_match = CARGO_LOCATION_RE.search(clean_text)
            location = loc_match.group(1) if loc_match else ""

            assert_match = CARGO_ASSERT_FAIL_RE.search(clean_text)
            exp_actual = ""
            if assert_match:
                exp_actual = f"exp: {assert_match.group(2).strip()} got: {assert_match.group(1).strip()}"

            fail_desc = f"✗ {test_name}"
            if location:
                fail_desc += f" ({location})"
            if exp_actual:
                fail_desc += f" · {exp_actual}"

            span = clean_char_to_byte_span(ingest, fail_match.start(), fail_match.end())
            blocks.append(
                Block(
                    block_id=f"block_{len(blocks):04d}_test_failure",
                    kind=BlockKind.LOG,
                    sources=(span,),
                    text=fail_desc,
                    metadata={"runner": "cargo", "test_name": test_name, "location": location, "kind": "aggregate"},
                )
            )

        # Append overall header
        if res_match:
            span = clean_char_to_byte_span(ingest, res_match.start(), res_match.end())
        else:
            span = clean_char_to_byte_span(ingest, 0, min(50, len(clean_text)))
        blocks.insert(
            0,
            Block(
                block_id="block_0000_test_summary",
                kind=BlockKind.LOG,
                sources=(span,),
                text=summary_line,
                metadata={"runner": "cargo", "passed": passed, "failed": failed, "duration": duration, "kind": "aggregate"},
            ),
        )
        return blocks

    # 2. Pytest
    if PYTEST_HEADER_RE.search(clean_text):
        res_match = PYTEST_RESULT_RE.search(clean_text)
        failed = int(res_match.group(1)) if res_match and res_match.group(1) else 0
        passed = int(res_match.group(2)) if res_match and res_match.group(2) else 0
        duration = res_match.group(3) if res_match else ""

        summary_line = f"✓ {passed} · ✗ {failed}"
        if duration:
            summary_line += f" · {duration}"

        loc_match = PYTEST_FAIL_LOCATION_RE.search(clean_text)
        location = loc_match.group(1) if loc_match else ""

        assert_match = PYTEST_ASSERT_RE.search(clean_text)
        exp_actual = ""
        if assert_match:
            exp_actual = f"exp: {assert_match.group(2).strip()} got: {assert_match.group(1).strip()}"

        func_match = re.search(r"_{3,}\s*([^\s_]+)\s*_{3,}", clean_text)
        test_name = func_match.group(1) if func_match else "test"

        fail_desc = f"✗ {test_name}"
        if location:
            fail_desc += f" ({location})"
        if exp_actual:
            fail_desc += f" · {exp_actual}"

        start_c = loc_match.start() if loc_match else 0
        end_c = loc_match.end() if loc_match else len(clean_text)
        span = clean_char_to_byte_span(ingest, start_c, end_c)
        blocks.append(
            Block(
                block_id=f"block_{len(blocks):04d}_test_failure",
                kind=BlockKind.LOG,
                sources=(span,),
                text=fail_desc,
                metadata={"runner": "pytest", "test_name": test_name, "location": location, "kind": "aggregate"},
            )
        )

        if res_match:
            span_h = clean_char_to_byte_span(ingest, res_match.start(), res_match.end())
        else:
            span_h = clean_char_to_byte_span(ingest, 0, min(50, len(clean_text)))
        blocks.insert(
            0,
            Block(
                block_id="block_0000_test_summary",
                kind=BlockKind.LOG,
                sources=(span_h,),
                text=summary_line,
                metadata={"runner": "pytest", "passed": passed, "failed": failed, "duration": duration, "kind": "aggregate"},
            ),
        )
        return blocks

    # 3. Vitest
    if "FAIL " in clean_text and ("Test Files" in clean_text or "Duration" in clean_text):
        fail_match = VITEST_FAIL_RE.search(clean_text)
        test_name = fail_match.group(1).strip() if fail_match else "test"

        loc_match = VITEST_LOCATION_RE.search(clean_text)
        location = loc_match.group(1).strip() if loc_match else ""

        exp_match = VITEST_EXPECT_RE.search(clean_text)
        exp_actual = ""
        if exp_match:
            exp_actual = f"exp: {exp_match.group(1).strip()} got: {exp_match.group(2).strip()}"

        res_match = VITEST_RESULT_RE.search(clean_text)
        failed = int(res_match.group(1)) if res_match and res_match.group(1) else 1
        passed = int(res_match.group(2)) if res_match and res_match.group(2) else 0
        duration = res_match.group(3) if res_match else ""

        summary_line = f"✓ {passed} · ✗ {failed}"
        if duration:
            summary_line += f" · {duration}"

        fail_desc = f"✗ {test_name}"
        if exp_actual:
            fail_desc += f" · {exp_actual}"
        if location:
            fail_desc += f" · {location}"

        start_c = fail_match.start() if fail_match else 0
        end_c = loc_match.end() if loc_match else len(clean_text)
        span = clean_char_to_byte_span(ingest, start_c, end_c)
        blocks.append(
            Block(
                block_id=f"block_{len(blocks):04d}_test_failure",
                kind=BlockKind.LOG,
                sources=(span,),
                text=fail_desc,
                metadata={"runner": "vitest", "test_name": test_name, "location": location, "kind": "aggregate"},
            )
        )

        span_h = clean_char_to_byte_span(ingest, 0, min(50, len(clean_text)))
        blocks.insert(
            0,
            Block(
                block_id="block_0000_test_summary",
                kind=BlockKind.LOG,
                sources=(span_h,),
                text=summary_line,
                metadata={"runner": "vitest", "passed": passed, "failed": failed, "duration": duration, "kind": "aggregate"},
            ),
        )
        return blocks

    # Generic log lines
    lines = clean_text.splitlines()
    curr_c = 0
    for _idx, line in enumerate(lines):
        line_len = len(line)
        line_str = line.strip()
        if line_str:
            c_start = clean_text.find(line_str, curr_c)
            c_end = c_start + len(line_str)
            span = clean_char_to_byte_span(ingest, c_start, c_end)
            blocks.append(
                Block(
                    block_id=f"block_{len(blocks):04d}_log",
                    kind=BlockKind.LOG,
                    sources=(span,),
                    text=line_str,
                    metadata={"kind": "copy"},
                )
            )
        curr_c += line_len + 1

    return blocks
