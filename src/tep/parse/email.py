"""RFC 5322 Email parsing and speech-act block extraction."""

from __future__ import annotations

import re

from tep.ingest.decoder import IngestionResult, clean_char_to_byte_span
from tep.ir.models import Block, BlockKind
from tep.segment.sentence import segment_sentences

FROM_HEADER_RE = re.compile(r"(?i)^From:\s*(.+)$", re.MULTILINE)
SUBJ_HEADER_RE = re.compile(r"(?i)^Subject:\s*(.+)$", re.MULTILINE)
QUOTE_LINE_RE = re.compile(r"^(?:>|On\s+.+wrote:)", re.MULTILINE)

REQUEST_RE = re.compile(r"(?i)\b(?:please|could you|action required|need you to|kindly)\b")
DECISION_RE = re.compile(r"(?i)\b(?:decided to|agreed to|approved|confirmed|concluded)\b")


def is_email(text: str) -> bool:
    return bool(FROM_HEADER_RE.search(text) and SUBJ_HEADER_RE.search(text))


def parse_email_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses email text into header block and categorized body sentence blocks."""
    clean_text = ingest.clean_text
    blocks: list[Block] = []

    from_match = FROM_HEADER_RE.search(clean_text)
    subj_match = SUBJ_HEADER_RE.search(clean_text)

    from_val = ""
    if from_match:
        raw_from = from_match.group(1).strip()
        from_val = raw_from.split("<")[0].strip() or raw_from

    subj_val = subj_match.group(1).strip() if subj_match else ""

    header_parts: list[str] = []
    if from_val:
        header_parts.append(f"from: {from_val}")
    if subj_val:
        header_parts.append(f"subj: {subj_val}")

    # Header block
    if header_parts:
        header_text = " · ".join(header_parts)
        start_c = min(
            from_match.start() if from_match else 0,
            subj_match.start() if subj_match else 0,
        )
        end_c = max(
            from_match.end() if from_match else 0,
            subj_match.end() if subj_match else 0,
        )
        span = clean_char_to_byte_span(ingest, start_c, end_c)
        blocks.append(
            Block(
                block_id="block_0000_email_header",
                kind=BlockKind.EMAIL_HEADER,
                sources=(span,),
                text=header_text,
                metadata={"from": from_val, "subject": subj_val, "kind": "aggregate"},
            )
        )

    # Find body start (after headers)
    body_start_idx = max(
        from_match.end() if from_match else 0,
        subj_match.end() if subj_match else 0,
    )
    raw_body = clean_text[body_start_idx:]

    # Remove quote threads and signature markers
    line_start_in_body = 0
    clean_body_end = len(raw_body)

    for line in raw_body.splitlines(keepends=True):
        trimmed = line.strip()
        if QUOTE_LINE_RE.match(trimmed) or trimmed.startswith("--"):
            clean_body_end = line_start_in_body
            break
        line_start_in_body += len(line)

    body_text = raw_body[:clean_body_end]
    body_offset = body_start_idx

    # Segment sentences in body
    sentences = segment_sentences(body_text)
    for s in sentences:
        s_text = s.text.strip()
        # Skip trivial courtesy greetings
        if (
            len(s_text) <= 5
            or s_text.lower().startswith("best regards")
            or s_text.lower().startswith("thanks")
        ):
            continue

        c_start = body_offset + s.start_char
        c_end = body_offset + s.end_char
        span = clean_char_to_byte_span(ingest, c_start, c_end)

        # Categorize
        if DECISION_RE.search(s_text):
            category = "decision"
        elif REQUEST_RE.search(s_text):
            category = "request"
        elif s_text.endswith("?") or s_text.startswith(("Do ", "What ", "How ", "Could ")):
            category = "question"
        else:
            category = "fact"

        blocks.append(
            Block(
                block_id=f"block_{len(blocks):04d}_{category}",
                kind=BlockKind.PROSE,
                sources=(span,),
                text=s_text,
                metadata={"category": category, "kind": "copy"},
            )
        )

    return blocks
