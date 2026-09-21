"""RFC 5322 Email parsing and speech-act block extraction."""

from __future__ import annotations

import re

from contextcull.ingest.decoder import IngestionResult, clean_char_to_byte_span
from contextcull.ir.models import Block, BlockKind
from contextcull.ir.spans import ByteSpan
from contextcull.segment.sentence import segment_sentences

FROM_HEADER_RE = re.compile(r"(?i)^From:\s*(.+)$", re.MULTILINE)
SUBJ_HEADER_RE = re.compile(r"(?i)^Subject:\s*(.+)$", re.MULTILINE)
QUOTE_LINE_RE = re.compile(r"^(?:>|On\s+.+wrote:)", re.MULTILINE)

# Classic mbox envelope separator: "From <addr> <ctime-asctime>" (no colon).
MBOX_FROM_RE = re.compile(
    r"(?m)^From \S+\s+\w{3}\s+\w{3}\s+\d{1,2}\s+\d{1,2}:\d{2}:\d{2}\s+\d{4}\s*$"
)

HEADER_FIELD_RE = re.compile(r"(?m)^([A-Za-z0-9\-]+):\s*", re.IGNORECASE)

# Header fields worth keeping in the synthesized per-message header block. Everything else
# (Received, Return-Path, Delivered-To, X-*, List-*, Precedence, Sender, Errors-To, MIME-Version,
# Content-*, Message-Id, In-Reply-To, References, Mailing-List, ...) is transport/routing noise.
KEEP_HEADERS = ("from", "to", "cc", "subject", "date")
HEADER_LABELS = {"from": "From", "to": "To", "cc": "Cc", "subject": "Subject", "date": "Date"}

# Mailing-list / sponsor footer boilerplate. Once one of these lines is seen, everything to the
# end of the message body is masked out (same treatment as a "-- " signature delimiter).
FOOTER_TRIGGER_RE = re.compile(
    r"(?i)^(?:"
    r"-{2,}\s*Yahoo!\s*Groups\s*Sponsor\s*-{2,}.*"
    r"|to unsubscribe from this group\b.*"
    r"|this sf\.net email is sponsored by\b.*"
    r"|_{10,}"
    r")$"
)

REQUEST_RE = re.compile(r"(?i)\b(?:please|could you|action required|need you to|kindly)\b")
DECISION_RE = re.compile(r"(?i)\b(?:decided to|agreed to|approved|confirmed|concluded)\b")


def is_email(text: str) -> bool:
    return bool(FROM_HEADER_RE.search(text) and SUBJ_HEADER_RE.search(text))


def parse_email_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses email text (single or multi-message thread) into header and body blocks."""
    clean_text = ingest.clean_text
    blocks: list[Block] = []

    messages: list[tuple[int, int]] = []
    mbox_starts = [m.start() for m in MBOX_FROM_RE.finditer(clean_text)]
    if mbox_starts:
        # Real mbox thread: split strictly on "From <addr> <date>" envelope lines so that
        # dash/underscore dividers and sponsor blocks *inside* a message body never fragment it.
        if mbox_starts[0] > 0:
            messages.append((0, mbox_starts[0]))
        bounds = mbox_starts + [len(clean_text)]
        messages.extend((bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1))
    else:
        pos = 0
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

        # Strip the mbox envelope line itself; it is not an RFC 822 header.
        envelope_m = MBOX_FROM_RE.match(msg_chunk)
        if envelope_m:
            strip_len = envelope_m.end()
            while strip_len < len(msg_chunk) and msg_chunk[strip_len] in "\r\n":
                strip_len += 1
            msg_start += strip_len
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

        # Extract every header field's span, then keep only From/To/Cc/Subject/Date, folded
        # into a single synthesized header block (dropping transport/routing/list headers).
        hdr_matches = list(HEADER_FIELD_RE.finditer(header_text_raw))
        kept: dict[str, tuple[str, ByteSpan]] = {}
        for idx_h, h_match in enumerate(hdr_matches):
            h_start_in_hdr = h_match.start()
            h_end_in_hdr = (
                hdr_matches[idx_h + 1].start()
                if idx_h + 1 < len(hdr_matches)
                else len(header_text_raw)
            )
            hdr_name = h_match.group(1).lower()
            if hdr_name not in KEEP_HEADERS or hdr_name in kept:
                continue

            raw_hdr_seg = header_text_raw[h_start_in_hdr:h_end_in_hdr]
            value = header_text_raw[h_match.end() : h_end_in_hdr]
            value = re.sub(r"\s*\r?\n\s+", " ", value).strip()
            if not value:
                continue

            trailing_ws = len(raw_hdr_seg) - len(raw_hdr_seg.rstrip())
            adj_start = msg_start + h_start_in_hdr
            adj_end = msg_start + h_end_in_hdr - trailing_ws
            span = clean_char_to_byte_span(ingest, adj_start, adj_end)
            kept[hdr_name] = (value, span)

        present = [k for k in KEEP_HEADERS if k in kept]
        if present:
            header_lines = [f"{HEADER_LABELS[k]}: {kept[k][0]}" for k in present]
            header_spans = tuple(kept[k][1] for k in present)
            blocks.append(
                Block(
                    block_id=f"block_{len(blocks):04d}_email_header",
                    kind=BlockKind.EMAIL_HEADER,
                    sources=header_spans,
                    text="\n".join(header_lines),
                    metadata={"headers": present, "kind": "aggregate"},
                )
            )

        body_text = msg_chunk[body_start_in_chunk:]
        body_abs_offset = msg_start + body_start_in_chunk

        # Mask quotes, signature delimiters, and mailing-list/sponsor footers in body to keep
        # char indexing intact.
        masked_body_chars = list(body_text)
        line_start = 0
        in_sig = False
        in_footer = False
        for line in body_text.splitlines(keepends=True):
            trimmed = line.strip()
            if not in_footer and FOOTER_TRIGGER_RE.match(trimmed):
                in_footer = True
            if in_sig or in_footer or trimmed.startswith("--") or QUOTE_LINE_RE.match(trimmed):
                if trimmed == "--" or trimmed.startswith("-- "):
                    in_sig = True
                # Mask with newlines (not spaces) so a masked line always forces a sentence
                # boundary instead of silently merging into the surrounding prose (which would
                # make the resulting "copy" unit's text diverge from its raw source bytes).
                for idx in range(line_start, line_start + len(line)):
                    if masked_body_chars[idx] != "\n":
                        masked_body_chars[idx] = "\n"
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
