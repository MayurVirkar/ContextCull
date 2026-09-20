"""HTML block parser extracting semantic structures (headings, prose, lists, tables, code)."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from tep.ingest.decoder import IngestionResult
from tep.ir.models import Block, BlockKind
from tep.ir.spans import ByteSpan

HTML_DETECT_RE = re.compile(
    r"<!DOCTYPE\s+html\b|<html\b|<head\b|<body\b|<div\b|<table\b|<article\b|<section\b",
    re.IGNORECASE,
)


def is_html(text: str) -> bool:
    """Detects whether text contains HTML markup."""
    sample = text[:3000].strip()
    return bool(HTML_DETECT_RE.search(sample))


def parse_html_blocks(ingest: IngestionResult) -> list[Block]:
    """Parses HTML into structural blocks using lxml.html with HTMLParser fallback."""
    raw_bytes = ingest.source_map.raw_bytes
    raw_text = ingest.clean_text
    file_span = ByteSpan(ingest.document_id, 0, len(raw_bytes))

    try:
        import lxml.html

        doc = lxml.html.fromstring(raw_text)

        # Drop non-content trees
        for el in doc.xpath(
            "//script | //style | //noscript | //svg | //nav | //header | //footer"
        ):
            el.drop_tree()

        # Drop edit links and navigation elements
        for el in doc.xpath('//span[contains(@class, "mw-editsection")]'):
            el.drop_tree()

        blocks: list[Block] = []
        elements = doc.xpath(
            "//h1 | //h2 | //h3 | //h4 | //h5 | //h6 | //p | //li | //tr | //pre | //code | //blockquote"
        )

        for el in elements:
            text = " ".join(el.text_content().split()).strip()
            if not text or len(text) < 4:
                continue

            tag = el.tag.lower()
            if tag.startswith("h"):
                kind = BlockKind.HEADING
                level = int(tag[1]) if len(tag) > 1 and tag[1].isdigit() else 1
                meta = {"kind": "rewrite", "tag": tag, "level": level}
            elif tag in ("li", "dt", "dd"):
                kind = BlockKind.LIST
                meta = {"kind": "rewrite", "tag": tag}
            elif tag == "tr":
                kind = BlockKind.TABLE
                meta = {"kind": "rewrite", "tag": tag}
            elif tag in ("pre", "code"):
                kind = BlockKind.CODE
                meta = {"kind": "rewrite", "tag": tag}
            else:
                kind = BlockKind.PROSE
                meta = {"kind": "rewrite", "tag": tag}

            blocks.append(
                Block(
                    block_id=f"block_{len(blocks):04d}_{tag}",
                    kind=kind,
                    sources=(file_span,),
                    text=text,
                    metadata=meta,
                )
            )

        if blocks:
            return blocks

    except Exception:
        pass

    # Fallback to stdlib HTMLParser
    class _FallbackParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.blocks: list[Block] = []
            self.curr: list[str] = []
            self.curr_tag: str | None = None
            self.ignore = {"script", "style", "noscript", "svg", "meta", "link"}
            self.stack: list[str] = []

        def _flush(self) -> None:
            if not self.curr:
                return
            text = " ".join("".join(self.curr).split()).strip()
            self.curr = []
            if not text or len(text) < 4:
                return

            tag = self.curr_tag or "p"
            kind = (
                BlockKind.HEADING
                if tag.startswith("h")
                else (
                    BlockKind.LIST
                    if tag == "li"
                    else (
                        BlockKind.TABLE
                        if tag in ("td", "th", "tr")
                        else (BlockKind.CODE if tag in ("pre", "code") else BlockKind.PROSE)
                    )
                )
            )
            self.blocks.append(
                Block(
                    block_id=f"block_{len(self.blocks):04d}_{tag}",
                    kind=kind,
                    sources=(file_span,),
                    text=text,
                    metadata={"kind": "rewrite", "tag": tag},
                )
            )

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            self.stack.append(tag.lower())
            if tag.lower() in (
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "li",
                "td",
                "th",
                "tr",
                "pre",
                "div",
                "blockquote",
            ):
                self._flush()
                self.curr_tag = tag.lower()

        def handle_endtag(self, tag: str) -> None:
            if self.stack and self.stack[-1] == tag.lower():
                self.stack.pop()
            if tag.lower() in (
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "li",
                "td",
                "th",
                "tr",
                "pre",
                "div",
                "blockquote",
            ):
                self._flush()
                self.curr_tag = None

        def handle_data(self, data: str) -> None:
            if any(t in self.ignore for t in self.stack):
                return
            if data.strip():
                self.curr.append(data)

    fallback = _FallbackParser()
    fallback.feed(raw_text)
    fallback._flush()
    return fallback.blocks
