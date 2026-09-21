"""RFC 5322 Email parsing and speech-act block extraction."""

from __future__ import annotations

import re

from contextcull.ingest.decoder import IngestionResult, clean_char_to_byte_span
from contextcull.ir.models import Block, BlockKind
from contextcull.segment.sentence import segment_sentences

FROM_HEADER_RE = re.compile(r"(?i)^From:\s*(.+)$", re.MULTILINE)
SUBJ_HEADER_RE = re.compile(r"(?i)^Subject:\s*(.+)$", re.MULTILINE)
QUOTE_LINE_RE = re.compile(r"^(?:>|On\s+.+wrote:)", re.MULTILINE)

HEADER_FIELD_RE = re.compile(
    r"(?m)^(?:(From)\s+|([A-Za-z0-9\-]+):\s*)",
    re.IGNORECASE,
)
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

        # Extract headers with exact byte spans
        hdr_matches = list(HEADER_FIELD_RE.finditer(header_text_raw))
        if hdr_matches:
            for idx_h, h_match in enumerate(hdr_matches):
                h_start_in_hdr = h_match.start()
                h_end_in_hdr = (
                    hdr_matches[idx_h + 1].start()
                    if idx_h + 1 < len(hdr_matches)
                    else len(header_text_raw)
                )
                raw_hdr_seg = header_text_raw[h_start_in_hdr:h_end_in_hdr]
                stripped_hdr = raw_hdr_seg.strip()
                if not stripped_hdr:
                    continue

                leading_ws = len(raw_hdr_seg) - len(raw_hdr_seg.lstrip())
                trailing_ws = len(raw_hdr_seg) - len(raw_hdr_seg.rstrip())
                adj_start = msg_start + h_start_in_hdr + leading_ws
                adj_end = msg_start + h_end_in_hdr - trailing_ws
                span = clean_char_to_byte_span(ingest, adj_start, adj_end)

                hdr_name = (h_match.group(1) or h_match.group(2) or "header").lower()
                blocks.append(
                    Block(
                        block_id=f"block_{len(blocks):04d}_email_header_{hdr_name}",
                        kind=BlockKind.EMAIL_HEADER,
                        sources=(span,),
                        text=stripped_hdr,
                        metadata={"header": hdr_name, "kind": "copy"},
                    )
                )
        else:
            from_m = FROM_HEADER_RE.search(header_text_raw)
            subj_m = SUBJ_HEADER_RE.search(header_text_raw)
            if from_m or subj_m:
                h_start = msg_start + min(
                    from_m.start() if from_m else 0,
                    subj_m.start() if subj_m else 0,
                )
                h_end = msg_start + max(
                    from_m.end() if from_m else 0,
                    subj_m.end() if subj_m else 0,
                )
                raw_h = clean_text[h_start:h_end].strip()
                if raw_h:
                    span = clean_char_to_byte_span(ingest, h_start, h_start + len(raw_h))
                    blocks.append(
                        Block(
                            block_id=f"block_{len(blocks):04d}_email_header",
                            kind=BlockKind.EMAIL_HEADER,
                            sources=(span,),
                            text=raw_h,
                            metadata={"kind": "copy"},
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
