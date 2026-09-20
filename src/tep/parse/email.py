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
    """Parses email text (single or multi-message thread) into header and body blocks."""
    clean_text = ingest.clean_text
    blocks: list[Block] = []

    pos = 0
    messages: list[tuple[int, int]] = []
    while pos < len(clean_text):
        # Next message boundary: separator line or blank lines followed by From:
        next_m = re.search(
            r"(?:\r?\n\s*[-=_]{3,}\s*\r?\n+|\r?\n\s*\r?\n(?=From:\s*))",
            clean_text[pos:],
            re.IGNORECASE,
        )
        if next_m:
            end = pos + next_m.start()
            messages.append((pos, end))
            pos = pos + next_m.end()
        else:
            messages.append((pos, len(clean_text)))
            break

    for msg_start, msg_end in messages:
        msg_chunk = clean_text[msg_start:msg_end]
        if not msg_chunk.strip():
            continue

        # Split header section from body at first blank line
        hdr_sep = re.search(r"\r?\n\s*\r?\n", msg_chunk)
        if hdr_sep:
            header_text_raw = msg_chunk[: hdr_sep.start()]
            body_start_in_chunk = hdr_sep.end()
        else:
            header_text_raw = msg_chunk
            body_start_in_chunk = len(msg_chunk)

        from_m = FROM_HEADER_RE.search(header_text_raw)
        subj_m = SUBJ_HEADER_RE.search(header_text_raw)

        from_val = ""
        if from_m:
            raw_from = from_m.group(1).strip()
            from_val = raw_from.split("<")[0].strip() or raw_from

        subj_val = subj_m.group(1).strip() if subj_m else ""

        header_parts: list[str] = []
        if from_val:
            header_parts.append(f"from: {from_val}")
        if subj_val:
            header_parts.append(f"subj: {subj_val}")

        # Header block for this message
        if header_parts:
            header_summary = " · ".join(header_parts)
            h_start = msg_start + min(
                from_m.start() if from_m else 0,
                subj_m.start() if subj_m else 0,
            )
            h_end = msg_start + max(
                from_m.end() if from_m else 0,
                subj_m.end() if subj_m else 0,
            )
            span = clean_char_to_byte_span(ingest, h_start, h_end)
            blocks.append(
                Block(
                    block_id=f"block_{len(blocks):04d}_email_header",
                    kind=BlockKind.EMAIL_HEADER,
                    sources=(span,),
                    text=header_summary,
                    metadata={"from": from_val, "subject": subj_val, "kind": "aggregate"},
                )
            )

        body_text = msg_chunk[body_start_in_chunk:]
        body_abs_offset = msg_start + body_start_in_chunk

        # Mask quotes and signature delimiters in body to keep char indexing intact
        masked_body_chars = list(body_text)
        line_start = 0
        in_sig = False
        for line in body_text.splitlines(keepends=True):
            trimmed = line.strip()
            if in_sig or trimmed.startswith("--") or QUOTE_LINE_RE.match(trimmed):
                if trimmed == "--" or trimmed.startswith("-- "):
                    in_sig = True
                for idx in range(line_start, line_start + len(line)):
                    if masked_body_chars[idx] != "\n":
                        masked_body_chars[idx] = " "
            line_start += len(line)

        masked_body = "".join(masked_body_chars)
        sentences = segment_sentences(masked_body)

        for s in sentences:
            s_text = s.text.strip()
            # Skip trivial courtesy greetings
            if (
                len(s_text) <= 5
                or s_text.lower().startswith("best regards")
                or s_text.lower().startswith("thanks")
            ):
                continue

            c_start = body_abs_offset + s.start_char
            c_end = body_abs_offset + s.end_char
            span = clean_char_to_byte_span(ingest, c_start, c_end)

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
