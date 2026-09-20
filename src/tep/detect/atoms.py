"""Detection and extraction of protected semantic atoms with exact source byte spans."""

from __future__ import annotations

import re
from collections.abc import Sequence

from tep.ingest.decoder import IngestionResult, clean_char_to_byte_span
from tep.ir.models import Atom, Block
from tep.ir.spans import ByteSpan

# Generic regular expressions for critical technical identifiers & protected classes
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
IPV4_RE = re.compile(r"\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}\b")
IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b")
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
GIT_SHA_RE = re.compile(r"\b[0-9a-fA-F]{40}\b|\b(?=[0-9a-f]{7,39}\b)(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,39}\b")
AWS_INSTANCE_RE = re.compile(r"\bi-[0-9a-f]{8,17}\b")

QUANTITY_RE = re.compile(
    r"\b(\d+(?:[\.,]\d+)*)\s*(MB|GB|TB|kB|ms|µs|ns|s|sec|second|seconds|min|mins|minute|minutes|h|hr|hrs|hour|hours|wk|week|weeks|mo|month|months|yr|year|years|%|\$|USD|EUR|billion|million|thousand|ppb)?\b",
    re.IGNORECASE,
)

PATH_OR_URL_RE = re.compile(
    r"(?:https?://[^\s/$.?#].[^\s]*|/[a-zA-Z0-9_\.\-]+(?:/[a-zA-Z0-9_\.\-]+)+|[a-zA-Z0-9_\.\-]+(?:\.[a-zA-Z0-9_\.\-]+)+/[^\s]*)"
)

FILE_LOCATION_RE = re.compile(
    r"\b[a-zA-Z0-9_\.\-]+(?:\s*/\s*[a-zA-Z0-9_\.\-]+)+(?::\d+(?::\d+)?)?\b"
)

CODE_IDENTIFIER_RE = re.compile(
    r"\b(?:[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+|[a-zA-Z0-9]+::[a-zA-Z0-9_:]+|[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)+)\b"
)

ISO_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?\b"
)

NEGATION_RE = re.compile(
    r"\b(not|never|no|without|neither|nor|cannot)\b",
    re.IGNORECASE,
)

MODALITY_RE = re.compile(
    r"\b(must|should|may|might|could|shall)\b",
    re.IGNORECASE,
)

CONDITION_RE = re.compile(
    r"\b(if|unless|except|provided that|excluding)\b",
    re.IGNORECASE,
)

CAUSALITY_RE = re.compile(
    r"\b(because|therefore|caused by|results in|leads to)\b",
    re.IGNORECASE,
)

UNIT_CANONICAL_MAP = {
    "minute": "min",
    "minutes": "min",
    "mins": "min",
    "second": "s",
    "seconds": "s",
    "sec": "s",
    "hour": "h",
    "hours": "h",
    "hr": "h",
    "hrs": "h",
    "week": "wk",
    "weeks": "wk",
    "month": "mo",
    "months": "mo",
    "year": "yr",
    "years": "yr",
}


def extract_atoms(
    ingest: IngestionResult,
    required_terms: Sequence[str] = (),
    blocks: Sequence[Block] | None = None,
) -> list[Atom]:
    """Extracts protected semantic atoms from the ingested document with exact byte spans.

    Critical technical identifiers (CVEs, IPs, UUIDs, Git SHAs, Instance IDs) and explicit
    user-required terms are marked required=True by default to guarantee retention.
    """
    atoms: list[Atom] = []
    seen_spans: set[tuple[int, int, str]] = set()
    clean_text = ingest.clean_text

    def add_atom(
        kind: str,
        surface: str,
        start_char: int,
        end_char: int,
        canonical: str | None = None,
        required: bool = False,
    ) -> None:
        key = (start_char, end_char, kind)
        if key in seen_spans:
            return
        seen_spans.add(key)

        byte_span = clean_char_to_byte_span(ingest, start_char, end_char)
        atom_id = f"atom_{len(atoms):04d}_{kind}"
        atoms.append(
            Atom(
                atom_id=atom_id,
                kind=kind,
                surface=surface,
                canonical=canonical or surface.lower(),
                sources=(byte_span,),
                confidence=1.0,
                required=required,
            )
        )

    # 1. User-required terms (highest priority, always required)
    for term in required_terms:
        if not term:
            continue
        term_re = re.compile(r"(?<![a-zA-Z0-9_])" + re.escape(term) + r"(?![a-zA-Z0-9_])", re.IGNORECASE)
        found = False
        for match in term_re.finditer(clean_text):
            found = True
            start, end = match.span()
            add_atom("required_term", clean_text[start:end], start, end, required=True)

        if not found and " " in term:
            parts = term.split()
            if len(parts) == 2 and parts[0].isdigit():
                val, u = parts
                u_pattern = r"(?:" + re.escape(u) + r"|minutes?|hours?|seconds?)"
                flex_re = re.compile(
                    r"\b" + re.escape(val) + r"\s*" + u_pattern + r"\b",
                    re.IGNORECASE,
                )
                for match in flex_re.finditer(clean_text):
                    start, end = match.span()
                    add_atom("required_term", clean_text[start:end], start, end, canonical=term.lower(), required=True)

    # 2. Critical Technical Identifiers (Always required by default)
    for match in CVE_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("cve", clean_text[start:end], start, end, required=True)

    for match in AWS_INSTANCE_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("instance_id", clean_text[start:end], start, end, required=True)

    for match in IPV4_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("ipv4", clean_text[start:end], start, end, required=True)

    for match in IPV6_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("ipv6", clean_text[start:end], start, end, required=True)

    for match in UUID_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("uuid", clean_text[start:end], start, end, required=True)

    for match in GIT_SHA_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("git_sha", clean_text[start:end], start, end, required=True)

    # 3. File locations and URLs
    for match in PATH_OR_URL_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("path_or_url", clean_text[start:end], start, end)

    for match in FILE_LOCATION_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("file_location", clean_text[start:end], start, end)

    # 4. Quantities & Units
    for match in QUANTITY_RE.finditer(clean_text):
        start, end = match.span()
        val = match.group(1)
        raw_unit = (match.group(2) or "").lower()
        canonical_unit = UNIT_CANONICAL_MAP.get(raw_unit, raw_unit)
        canonical = f"{val} {canonical_unit}".strip()
        add_atom("quantity", clean_text[start:end], start, end, canonical=canonical)

    # 5. Technical code identifiers
    for match in CODE_IDENTIFIER_RE.finditer(clean_text):
        start, end = match.span()
        surface = clean_text[start:end]
        if not any(
            isinstance(a.sources[0], ByteSpan) and start >= a.sources[0].start and end <= a.sources[0].end
            for a in atoms
            if a.kind in ("path_or_url", "file_location")
        ):
            add_atom("code_identifier", surface, start, end)

    # 6. ISO Timestamps
    for match in ISO_TIMESTAMP_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("timestamp", clean_text[start:end], start, end)

    # 7. Negations
    for match in NEGATION_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("negation", clean_text[start:end], start, end, canonical=clean_text[start:end].lower())

    # 8. Modalities
    for match in MODALITY_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("modality", clean_text[start:end], start, end)

    # 9. Conditions
    for match in CONDITION_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("condition", clean_text[start:end], start, end)

    # 10. Causality
    for match in CAUSALITY_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("causality", clean_text[start:end], start, end)

    # Filter out atoms originating in discarded non-content zones (e.g., <script>, <style> in HTML)
    if blocks is not None:
        has_rewrites = any(b.metadata.get("kind") == "rewrite" for b in blocks)
        if has_rewrites:
            combined = "\n".join(b.text for b in blocks)
            atoms = [a for a in atoms if a.surface in combined]
        else:
            valid_spans = [
                (b.sources[0].start, b.sources[0].end)
                for b in blocks
                if b.sources and isinstance(b.sources[0], ByteSpan)
            ]
            if valid_spans:
                atoms = [
                    a for a in atoms
                    if any(
                        isinstance(a.sources[0], ByteSpan) and a.sources[0].start >= s_start and a.sources[0].end <= s_end
                        for s_start, s_end in valid_spans
                    )
                ]

    return atoms
