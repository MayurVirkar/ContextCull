"""Regression tests for:

1. Email parser: one synthesized From/To/Cc/Subject/Date header block per message (mbox and
   single RFC 822), transport/routing headers dropped, kind="aggregate" for synthesized text.
2. Mailing-list/sponsor footer boilerplate stripped from bodies without corrupting provenance
   even when a masked divider line sits mid-sentence with no surrounding blank lines.
3. Sentence segmentation: ellipsis + parenthetical/lowercase continuation is not a sentence
   boundary, and the whitespace-follows guard applies to any run of Western terminators.
"""

from __future__ import annotations

from contextcull.api import ContextCompiler
from contextcull.ingest.decoder import ingest_bytes
from contextcull.ir.models import BlockKind, CompileMode
from contextcull.parse.email import parse_email_blocks
from contextcull.segment.sentence import segment_sentences

MBOX_THREAD = b"""From alice@example.com  Thu Aug 22 12:36:23 2002
Return-Path: <alice@example.com>
Delivered-To: bob@example.com
Received: from mx1.example.com (mx1.example.com [10.0.0.1])
\tby relay.example.com (Postfix) with ESMTP id AAAA111
\tfor <bob@example.com>; Thu, 22 Aug 2002 07:36:16 -0400 (EDT)
Received: from smtp.example.com (smtp.example.com [10.0.0.2])
\tby mx1.example.com with ESMTP id BBBB222; Thu, 22 Aug 2002 07:35:02 -0400
From: Alice Example <alice@example.com>
To: Bob Example <bob@example.com>
Cc: team@example.com
Subject: Re: Deploy window
Message-Id: <abc123@example.com>
X-Mailer: Mutt 1.0
MIME-Version: 1.0
Content-Type: text/plain; charset=us-ascii
Precedence: bulk
List-Id: Example List <list.example.com>
Date: Thu, 22 Aug 2002 18:26:25 +0700

Ship it whenever the canary looks stable.

-------------------------------------------------------
This sf.net email is sponsored by: OSDN - Tired of that same old
cell phone?  Get a new one for FREE!
_______________________________________________
Example-list mailing list
Example-list@lists.example.com
--------------------------------------------------------------------------------

From carol@example.com  Thu Aug 22 12:46:39 2002
Return-Path: <carol@example.com>
Received: from mx2.example.com (mx2.example.com [10.0.0.3])
\tby relay.example.com (Postfix) with ESMTP id CCCC333; Thu, 22 Aug 2002 07:46:38 -0400
X-Egroups-From: Carol Example <carol@example.com>
From: Carol Example <carol@example.com>
To: "'zzzzteana@example.com'" <zzzzteana@example.com>
Subject: [team] RE: Rollout
Reply-To: zzzzteana@example.com
Content-Type: text/plain; charset=US-ASCII
Date: Thu, 22 Aug 2002 12:46:18 +0100

Quick status update before the sponsor block.
------------------------ Yahoo! Groups Sponsor ---------------------~-->
4 DVDs Free +s&p Join Now
http://example.com/offer
---------------------------------------------------------------------~-->

To unsubscribe from this group, send an email to:
example-unsubscribe@example.com

Your use of Yahoo! Groups is subject to http://example.com/terms
"""


def test_mbox_thread_one_header_block_per_message_transport_headers_dropped():
    ingest = ingest_bytes(MBOX_THREAD)
    blocks = parse_email_blocks(ingest)
    header_blocks = [b for b in blocks if b.kind == BlockKind.EMAIL_HEADER]

    assert len(header_blocks) == 2

    b1 = header_blocks[0]
    assert b1.metadata["kind"] == "aggregate"
    assert b1.text == (
        "From: Alice Example <alice@example.com>\n"
        "To: Bob Example <bob@example.com>\n"
        "Cc: team@example.com\n"
        "Subject: Re: Deploy window\n"
        "Date: Thu, 22 Aug 2002 18:26:25 +0700"
    )

    b2 = header_blocks[1]
    assert b2.metadata["kind"] == "aggregate"
    assert "From: Carol Example <carol@example.com>" in b2.text
    assert "Subject: [team] RE: Rollout" in b2.text

    # Transport/routing/list-management noise must never surface in any block's text.
    all_text = "\n".join(b.text for b in blocks)
    for dropped in (
        "Received:",
        "Return-Path:",
        "Delivered-To:",
        "X-Mailer",
        "X-Egroups-From",
        "MIME-Version:",
        "Content-Type:",
        "Precedence:",
        "List-Id:",
        "Message-Id:",
        "Reply-To:",
    ):
        assert dropped not in all_text


def test_mbox_envelope_line_not_treated_as_from_header():
    ingest = ingest_bytes(MBOX_THREAD)
    blocks = parse_email_blocks(ingest)
    header_blocks = [b for b in blocks if b.kind == BlockKind.EMAIL_HEADER]
    # The mbox "From addr date" envelope line must not produce its own header block, nor
    # pollute the From: value.
    assert header_blocks[0].text.startswith("From: Alice Example <alice@example.com>")
    assert "Thu Aug 22 12:36:23 2002" not in header_blocks[0].text


def test_mailing_list_and_sponsor_footers_stripped_from_body():
    ingest = ingest_bytes(MBOX_THREAD)
    blocks = parse_email_blocks(ingest)
    body_text = "\n".join(b.text for b in blocks if b.kind == BlockKind.PROSE)

    assert "Ship it whenever the canary looks stable." in body_text
    assert "Quick status update before the sponsor block." in body_text

    for boilerplate in (
        "sponsored by",
        "mailing list",
        "Yahoo! Groups Sponsor",
        "unsubscribe from this group",
        "subject to http://example.com/terms",
        "4 DVDs Free",
    ):
        assert boilerplate not in body_text


def test_single_rfc822_message_still_gets_one_header_block():
    raw = (
        b"From: sec-ops@acme.corp\n"
        b"To: oncall@acme.corp\n"
        b"Subject: Critical CVE alert\n"
        b"Date: Mon, 14 Jul 2026 09:00:00 +0000\n"
        b"Message-Id: <xyz@acme.corp>\n"
        b"\n"
        b"Remediate CVE-2026-9999 immediately across all worker nodes.\n"
    )
    ingest = ingest_bytes(raw)
    blocks = parse_email_blocks(ingest)
    header_blocks = [b for b in blocks if b.kind == BlockKind.EMAIL_HEADER]
    assert len(header_blocks) == 1
    assert header_blocks[0].metadata["kind"] == "aggregate"
    assert header_blocks[0].text == (
        "From: sec-ops@acme.corp\n"
        "To: oncall@acme.corp\n"
        "Subject: Critical CVE alert\n"
        "Date: Mon, 14 Jul 2026 09:00:00 +0000"
    )
    assert "Message-Id" not in header_blocks[0].text


def test_body_sentence_spanning_masked_divider_keeps_provenance_valid():
    """Regression: a mid-body divider masked to blank characters must not be silently merged
    into a surrounding sentence such that the resulting "copy" unit's text no longer matches
    its raw source bytes (previously raised INVARIANT_FAILED)."""
    raw = (
        b"From: reporter@example.com\n"
        b"To: readers@example.com\n"
        b"Subject: Sculpture report\n"
        b"Date: Thu, 22 Aug 2002 13:00:00 +0100\n"
        b"\n"
        b"As well as the granite features, 240 ft high and 170 ft wide, a\n"
        b" museum and car park for admiring crowds are\n"
        b"planned\n"
        b"---------------------\n"
        b"So is this mountain limestone or granite?\n"
    )
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(raw.decode("utf-8"))
    assert result.ok
    assert "240 ft" in result.text
    assert "granite" in result.text


def test_ellipsis_parenthetical_continuation_is_not_a_sentence_boundary():
    text = "For me it is very repeatable... (like every time, without fail)."
    spans = segment_sentences(text)
    assert [s.text for s in spans] == [text]


def test_ellipsis_lowercase_continuation_is_not_a_sentence_boundary():
    text = "He said ok... then left."
    spans = segment_sentences(text)
    assert [s.text for s in spans] == [text]


def test_ellipsis_uppercase_continuation_still_splits():
    text = "Wait... Then it stopped."
    spans = segment_sentences(text)
    assert [s.text for s in spans] == ["Wait...", "Then it stopped."]


def test_terminator_guard_covers_double_bang_and_mixed_runs():
    # Regression: the old guard tuple only covered (".", "!", "?", "...", "!?") and missed
    # "??", "!!" runs, letting them split even when NOT followed by whitespace.
    text = "No way!!Really?"
    spans = segment_sentences(text)
    # "!!" not followed by whitespace must not be treated as a boundary.
    assert len(spans) == 1
    assert spans[0].text == text
