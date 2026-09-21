"""Detection and extraction of protected semantic atoms with exact source byte spans."""

from __future__ import annotations

import bisect
import re
from collections.abc import Sequence

from contextcull.ingest.decoder import IngestionResult, clean_char_to_byte_span
from contextcull.ir.models import Atom, Block
from contextcull.ir.spans import ByteSpan

# Generic regular expressions for critical technical identifiers & protected classes
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
IPV4_RE = re.compile(
    r"\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?::\d{2,5})?\b"
)
# Preceding-word context that indicates a dotted-quad number is a version/section number,
# not a real IP address (e.g. "Upgrade from 1.2.3.4", "section 3.1.4.1"). Checked as the
# token immediately before the match, so it never suppresses real IPs elsewhere in prose
# (e.g. "host 10.0.0.1", "Received: ... [10.0.0.1]").
_IPV4_VERSION_CONTEXT_RE = re.compile(
    r"(?:upgrad(?:e|ed|ing)\s+from|downgrad(?:e|ed|ing)\s+from|version|release|section|upgrade|downgrade|v)[\s:#]{0,3}$",
    re.IGNORECASE,
)
IPV6_RE = re.compile(
    r"\b[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4})*::(?:[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4})*)?\b|\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|::1\b"
)
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
# Full-length hashes (40 = SHA-1, 64 = SHA-256) are unconditionally real git SHAs.
GIT_SHA_RE = re.compile(r"\b[0-9a-fA-F]{64}\b|\b[0-9a-fA-F]{40}\b")
# Short hashes (7-12 hex chars, mixed digit+letter) are only treated as git SHAs when
# adjacent to a git-related context word -- otherwise short hex-looking tokens (scientific
# notation "1e10000", random hex-ish words "12abcdef"/"deadbee1", MIME boundaries, CSS
# colors) get flagged as required "hard invariant" atoms and inflate the mandatory floor.
GIT_SHA_SHORT_CANDIDATE_RE = re.compile(
    r"\b(?=[0-9a-f]{7,12}\b)(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,12}\b", re.IGNORECASE
)
_GIT_SHA_SCI_NOTATION_RE = re.compile(r"^\d+e\d+$", re.IGNORECASE)
_GIT_SHA_CONTEXT_RE = re.compile(
    r"\b(?:commit|sha1?|sha256|rev|revision|rollback|hash|merge|cherry-pick|cherry-picked|"
    r"fixes|fixed|tag|tagged|verified|build|ref|branch|head|rebase|parent|tree|blob)\b",
    re.IGNORECASE,
)
AWS_INSTANCE_RE = re.compile(r"\bi-[0-9a-f]{8,17}\b")

QUANTITY_RE = re.compile(
    r"\b(\d+(?:[\.,]\d+)*)\s*(MB|GB|TB|kB|KB|ms|µs|ns|s|sec|second|seconds|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|wk|week|weeks|mo|month|months|yr|year|years|\$|USD|EUR|billion|million|thousand|ppb|M)\b|\b(\d+(?:[\.,]\d+)*)%",
    re.IGNORECASE,
)
CURRENCY_RE = re.compile(
    r"(?:[\$€£]\s*|(?:USD|EUR)\s*)(\d+(?:[\.,]\d+)*(?:\s*(?:billion|million|thousand|[MmkK]))?)\b"
)

PATH_OR_URL_RE = re.compile(
    r"(?:[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>\"'()]+|arn:aws:[a-zA-Z0-9_\.\-]+:[a-zA-Z0-9_\.\-]*:(?:\d{12})?:[a-zA-Z0-9_\.\-/:*]+|/[a-zA-Z0-9_\.\-]+(?:/[a-zA-Z0-9_\.\-]+)+|[a-zA-Z0-9_\.\-]+(?:\.[a-zA-Z0-9_\.\-]+)+/[^\s]*)"
)

FILE_LOCATION_RE = re.compile(
    r"\b[a-zA-Z0-9_\.\-]+(?:\s*/\s*[a-zA-Z0-9_\.\-]+)+(?::\d+(?::\d+)?)?\b"
)

CODE_IDENTIFIER_RE = re.compile(
    r"\b(?:"
    r"[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+"  # PascalCase (e.g. ContextCompiler)
    r"|[a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+"  # camelCase (e.g. getNextToken)
    r"|[a-zA-Z0-9_]+::[a-zA-Z0-9_:]+"  # C++/Rust namespaced (e.g. std::vector)
    r"|[a-z0-9]+(?:_[a-z0-9]+)+"  # snake_case (e.g. parse_code_blocks)
    r"|[a-zA-Z0-9]+-[a-zA-Z0-9-]*(?:\d[a-zA-Z0-9-]*)"  # Technical hyphenated with digits (e.g. k8s-worker-1, srv-01)
    r")\b"
)

ISO_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?\b|\b\d{2}:\d{2}(?::\d{2})?(?:\s*UTC)\b"
)

HEBREW_NEGATION = r"לא|ללא|אין|אל|בלי|אינו|אינה|אינם|אינן"
WESTERN_NEGATION = (
    r"no|not|never|without|neither|nor|cannot|zero|"
    r"não|nunca|jamais|sem|nenhum|nenhuma|"
    r"jamás|sin|ningún|ninguno|ninguna|tampoco|"
    r"pas|aucun|aucune|sans|rien|"
    r"nicht|kein|keine|keinen|keinem|nie|niemals|ohne"
)
OTHER_NEGATION = r"не|нет|никогда|без|никакой|नहीं|मत|बिना|না|নয়|বিনা|لم|لن|ليس|بدون"

BOUND_NEGATION_RE = re.compile(
    rf"\b(?:{WESTERN_NEGATION}|{HEBREW_NEGATION}|{OTHER_NEGATION})\s+([^\s\.,;!?:\"'\(\)\[\]\{{\}}]+(?:\s+[^\s\.,;!?:\"'\(\)\[\]\{{\}}]+){{0,2}})(?:\b|(?<=[\u05f3\u05f4]))",
    re.IGNORECASE,
)

NEGATION_RE = re.compile(
    rf"\b(?:{WESTERN_NEGATION}|{HEBREW_NEGATION}|{OTHER_NEGATION})\b",
    re.IGNORECASE,
)

CJK_NEGATION_RE = re.compile(
    r"(?:不|没|没有|未|无|非)(?:[\u4e00-\u9fff]{1,4})",
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

COMPLIANCE_ACRONYM_RE = re.compile(
    r"\b(?:PII|GDPR|HIPAA|SOC2|mTLS|CIDR|STS|IAM|ACL|RBAC)\b",
    re.IGNORECASE,
)

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")

CRITICAL_ENTITY_PATTERNS: list[re.Pattern] = [
    CVE_RE,
    # IPV4_RE and GIT_SHA_RE (short-hash form) are intentionally excluded here: they need
    # context filtering (see iter_ipv4_spans / iter_git_sha_spans below) that a plain
    # Pattern.finditer() can't express. GIT_SHA_RE (full 40/64-hex) is safe unfiltered.
    IPV6_RE,
    UUID_RE,
    GIT_SHA_RE,
    AWS_INSTANCE_RE,
    QUANTITY_RE,
    CURRENCY_RE,
    PATH_OR_URL_RE,
    FILE_LOCATION_RE,
    CODE_IDENTIFIER_RE,
    ISO_TIMESTAMP_RE,
    BOUND_NEGATION_RE,
    CJK_NEGATION_RE,
    COMPLIANCE_ACRONYM_RE,
    EMAIL_RE,
]


def iter_ipv4_spans(text: str) -> list[tuple[int, int]]:
    """Yields (start, end) spans for real IPv4 addresses, rejecting dotted-quad numbers
    that are really version/section numbers (see _IPV4_VERSION_CONTEXT_RE)."""
    spans = []
    for match in IPV4_RE.finditer(text):
        start, end = match.span()
        window = text[max(0, start - 24) : start]
        if _IPV4_VERSION_CONTEXT_RE.search(window):
            continue
        spans.append((start, end))
    return spans


def iter_git_sha_spans(text: str) -> list[tuple[int, int]]:
    """Yields (start, end) spans for git SHAs: full 40/64-hex hashes unconditionally, plus
    short 7-12 hex hashes only when adjacent to a git-related context word (commit, sha,
    rev, hash, merge, cherry-pick, fixes). Rejects scientific-notation tokens ("1e10000")."""
    spans = [m.span() for m in GIT_SHA_RE.finditer(text)]
    for match in GIT_SHA_SHORT_CANDIDATE_RE.finditer(text):
        token = match.group(0)
        if _GIT_SHA_SCI_NOTATION_RE.match(token):
            continue
        start, end = match.span()
        before = text[max(0, start - 20) : start]
        after = text[end : end + 20]
        if _GIT_SHA_CONTEXT_RE.search(before) or _GIT_SHA_CONTEXT_RE.search(after):
            spans.append((start, end))
    return spans


def extract_unit_entities(text: str) -> set[str]:
    """Extracts critical domain entities from a unit text using unified atom patterns."""
    entities: set[str] = set()
    for pat in CRITICAL_ENTITY_PATTERNS:
        for match in pat.finditer(text):
            entities.add(match.group(0).strip())
    for start, end in iter_ipv4_spans(text):
        entities.add(text[start:end].strip())
    for start, end in iter_git_sha_spans(text):
        entities.add(text[start:end].strip())
    return entities


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
        term_re = re.compile(
            r"(?<![a-zA-Z0-9_])" + re.escape(term) + r"(?![a-zA-Z0-9_])", re.IGNORECASE
        )
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
                    add_atom(
                        "required_term",
                        clean_text[start:end],
                        start,
                        end,
                        canonical=term.lower(),
                        required=True,
                    )

    # 2. Critical Technical Identifiers (Always required by default)
    for match in CVE_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("cve", clean_text[start:end], start, end, required=True)

    for match in AWS_INSTANCE_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("instance_id", clean_text[start:end], start, end, required=True)

    for start, end in iter_ipv4_spans(clean_text):
        add_atom("ipv4", clean_text[start:end], start, end, required=True)

    for match in IPV6_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("ipv6", clean_text[start:end], start, end, required=True)

    for match in UUID_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("uuid", clean_text[start:end], start, end, required=True)

    for start, end in iter_git_sha_spans(clean_text):
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

    for match in CURRENCY_RE.finditer(clean_text):
        start, end = match.span()
        surface = clean_text[start:end]
        add_atom("quantity", surface, start, end, canonical=surface.lower())

    # 5. Technical code identifiers (skip any span already covered by a path_or_url or
    # file_location atom). Spans are sorted + merged once so each match is checked with a
    # single bisect lookup instead of scanning every previously-added atom (was O(n*m)).
    _url_file_spans = sorted(
        (a.sources[0].start, a.sources[0].end)
        for a in atoms
        if a.kind in ("path_or_url", "file_location") and isinstance(a.sources[0], ByteSpan)
    )
    _merged_url_file_spans: list[tuple[int, int]] = []
    for s_start, s_end in _url_file_spans:
        if _merged_url_file_spans and s_start <= _merged_url_file_spans[-1][1]:
            _merged_url_file_spans[-1] = (
                _merged_url_file_spans[-1][0],
                max(_merged_url_file_spans[-1][1], s_end),
            )
        else:
            _merged_url_file_spans.append((s_start, s_end))
    _url_file_starts = [s[0] for s in _merged_url_file_spans]

    for match in CODE_IDENTIFIER_RE.finditer(clean_text):
        start, end = match.span()
        surface = clean_text[start:end]
        idx = bisect.bisect_right(_url_file_starts, start) - 1
        covered = False
        if idx >= 0:
            s_start, s_end = _merged_url_file_spans[idx]
            covered = start >= s_start and end <= s_end
        if not covered:
            add_atom("code_identifier", surface, start, end)

    # 6. ISO Timestamps
    for match in ISO_TIMESTAMP_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("timestamp", clean_text[start:end], start, end)

    # 7. Bound Negations (Protected semantic atoms to prevent statement inversion)
    for match in BOUND_NEGATION_RE.finditer(clean_text):
        start, end = match.span()
        add_atom(
            "bound_negation",
            clean_text[start:end],
            start,
            end,
            canonical=clean_text[start:end].lower(),
            required=False,
        )

    for match in CJK_NEGATION_RE.finditer(clean_text):
        start, end = match.span()
        add_atom(
            "bound_negation",
            clean_text[start:end],
            start,
            end,
            canonical=clean_text[start:end].lower(),
            required=False,
        )

    # 8. Negations
    for match in NEGATION_RE.finditer(clean_text):
        start, end = match.span()
        add_atom(
            "negation", clean_text[start:end], start, end, canonical=clean_text[start:end].lower()
        )

    # 9. Modalities
    for match in MODALITY_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("modality", clean_text[start:end], start, end)

    # 10. Conditions
    for match in CONDITION_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("condition", clean_text[start:end], start, end)

    # 11. Causality
    for match in CAUSALITY_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("causality", clean_text[start:end], start, end)

    # 12. Compliance Acronyms (Extracted for entity cover, optional by default)
    for match in COMPLIANCE_ACRONYM_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("compliance_acronym", clean_text[start:end], start, end, required=False)

    # 13. Email Addresses (Extracted for entity cover, optional by default)
    for match in EMAIL_RE.finditer(clean_text):
        start, end = match.span()
        add_atom("email", clean_text[start:end], start, end, required=False)

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
                valid_spans.sort(key=lambda s: s[0])
                merged_spans: list[tuple[int, int]] = []
                for s_start, s_end in valid_spans:
                    if merged_spans and s_start <= merged_spans[-1][1]:
                        merged_spans[-1] = (merged_spans[-1][0], max(merged_spans[-1][1], s_end))
                    else:
                        merged_spans.append((s_start, s_end))

                span_starts = [s[0] for s in merged_spans]
                filtered_atoms: list[Atom] = []
                for a in atoms:
                    if not a.sources or not isinstance(a.sources[0], ByteSpan):
                        continue
                    a_start = a.sources[0].start
                    a_end = a.sources[0].end
                    idx = bisect.bisect_right(span_starts, a_start) - 1
                    if idx >= 0:
                        s_start, s_end = merged_spans[idx]
                        if a_start >= s_start and a_end <= s_end:
                            filtered_atoms.append(a)
                atoms = filtered_atoms

    return atoms
