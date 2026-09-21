"""Transactional rewriting engine with net token savings and atom preservation validation."""

from __future__ import annotations

import re
from collections.abc import Sequence

from contextcull.ir.models import Atom, CandidateUnit, CompileMode, CompilePolicy, OutputSegment
from contextcull.rewrite.rules import ABBREVIATIONS, PHRASE_RULES, UNIT_ABBREVIATIONS
from contextcull.tokenize.profile import TokenizerProfile

try:
    import ahocorasick_rs

    HAS_AHOCORASICK_RS = True
except ImportError:
    ahocorasick_rs = None
    HAS_AHOCORASICK_RS = False

# Lines that look like email/mail headers ("From:", "References:", "X-Mailer:") --
# abbreviations are never applied inside these, only the header name but any content
# on the same unit, since header field names and display names are not prose.
_HEADER_LINE_RE = re.compile(r"^[ \t]*[A-Za-z][A-Za-z-]*:\s")

# "30 minutes" -> "30 min", "3 years" -> "3 yr" -- only fires directly after a number.
_UNIT_RULES: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s+" + re.escape(word) + r"\b", re.IGNORECASE),
        abbrev,
        f"unit_{word}",
    )
    for word, abbrev in UNIT_ABBREVIATIONS.items()
]


class RewriteEngine:
    """Executes verified, reversible transactional rewrites in compact/task modes."""

    def __init__(self) -> None:
        self._patterns: list[str] = []
        self._replacements: list[str] = []
        self._rule_ids: list[str] = []

        for r in PHRASE_RULES:
            self._patterns.append(r.pattern)
            self._replacements.append(r.replacement)
            self._rule_ids.append(r.rule_id)

        for word, abbrev in ABBREVIATIONS.items():
            self._patterns.append(word)
            self._replacements.append(abbrev)
            self._rule_ids.append(f"abbrev_{word}")

        if HAS_AHOCORASICK_RS and ahocorasick_rs is not None:
            # Build Aho-Corasick automaton with lowercased patterns for fast substring pre-filtering
            self._ac = ahocorasick_rs.AhoCorasick([p.lower() for p in self._patterns])
        else:
            self._ac = None

        self._pattern_res = [
            re.compile(r"(?<![\w\-\/])" + re.escape(pat) + r"(?![\w\-\/])", re.IGNORECASE)
            for pat in self._patterns
        ]

        # Cache of atom_id -> Atom built once per distinct `atoms` sequence (keyed by
        # identity), so rewrite_unit doesn't rescan the full atom list for every unit.
        self._atoms_index_cache: tuple[int, int, dict[str, Atom]] | None = None

    def _atoms_by_id(self, atoms: Sequence[Atom]) -> dict[str, Atom]:
        cache = self._atoms_index_cache
        if cache is not None and cache[0] == id(atoms) and cache[1] == len(atoms):
            return cache[2]
        index = {a.atom_id: a for a in atoms}
        self._atoms_index_cache = (id(atoms), len(atoms), index)
        return index

    def rewrite_unit(
        self,
        unit: CandidateUnit,
        atoms: Sequence[Atom],
        policy: CompilePolicy,
        tokenizer: TokenizerProfile,
    ) -> tuple[str, list[OutputSegment]]:
        """Rewrites a single candidate unit transactionally.

        In strict or verbatim mode, returns the original text without changes.
        In compact/task mode, commits rewrites ONLY IF:
          1. Token cost strictly decreases (new_tokens < orig_tokens).
          2. 100% of required atoms bound to this unit are preserved.
        """
        if policy.mode in (CompileMode.VERBATIM, CompileMode.STRICT):
            seg = OutputSegment(
                output_start=0,
                output_end=len(unit.text.encode("utf-8")),
                kind=unit.kind,
                sources=unit.sources,
                rule_id="parser_structural" if unit.kind == "rewrite" else None,
                text=unit.text,
            )
            return unit.text, [seg]

        orig_text = unit.text
        orig_tokens = tokenizer.count_tokens(orig_text)

        atoms_by_id = self._atoms_by_id(atoms)
        unit_atom_surfaces = {
            a.surface.lower() for aid in unit.atom_ids if (a := atoms_by_id.get(aid)) is not None
        }
        unit_required_atoms = [
            a for aid in unit.atom_ids if (a := atoms_by_id.get(aid)) is not None and a.required
        ]

        candidate_text = orig_text
        used_rules: list[str] = []

        # Protect code spans (fenced code blocks first, then inline backticks) from rewrites
        code_spans: list[str] = []

        def _mask_code(m: re.Match) -> str:
            code_spans.append(m.group(0))
            return f"\x00CODE_{len(code_spans) - 1}\x00"

        masked_text = re.sub(r"```[\s\S]*?```", _mask_code, candidate_text)
        masked_text = re.sub(r"`[^`\r\n]+`", _mask_code, masked_text)

        if policy.discourse_pruning:
            from contextcull.rewrite.discourse import prune_discourse_scaffolding

            pruned = prune_discourse_scaffolding(masked_text)
            if pruned != masked_text:
                masked_text = pruned
                used_rules.append("discourse_prune")

        # Email/header-like lines ("From:", "References:", ...) are never abbreviated --
        # header field names and display names are not prose and abbreviating them
        # (e.g. "References:" -> "refs:", "NOI Administrator" -> "NOI admin") corrupts them.
        header_like = bool(_HEADER_LINE_RE.match(masked_text))

        # Fast pre-filtering with Aho-Corasick automaton if available
        if self._ac is not None:
            # m is a tuple (pattern_index, start, end)
            matched_indices = sorted(
                set(
                    m[0]
                    for m in self._ac.find_matches_as_indexes(masked_text.lower(), overlapping=True)
                ),
                key=lambda i: len(self._patterns[i]),
                reverse=True,
            )
            rules_to_check = [
                (self._patterns[i], self._replacements[i], self._rule_ids[i], self._pattern_res[i])
                for i in matched_indices
            ]
        else:
            rules_to_check = list(
                zip(self._patterns, self._replacements, self._rule_ids, self._pattern_res)
            )

        for pat, repl, rule_id, pattern_re in rules_to_check:
            is_abbrev = rule_id.startswith("abbrev_")
            if is_abbrev and (not policy.abbreviations or header_like):
                continue
            if pat.lower() in unit_atom_surfaces:
                continue

            if is_abbrev:
                # Never rewrite a capitalized word mid-unit -- likely a proper noun
                # ("Security Service", "March" as a name). Sentence-initial capitals
                # (position 0) are still eligible.
                def _replace_if_safe(m: re.Match, _repl: str = repl) -> str:
                    token = m.group(0)
                    if token[:1].isupper() and m.start() != 0:
                        return token
                    return _repl

                new_text = pattern_re.sub(_replace_if_safe, masked_text)
            else:
                if not pattern_re.search(masked_text):
                    continue
                new_text = pattern_re.sub(repl, masked_text)

            if new_text != masked_text:
                masked_text = new_text
                used_rules.append(rule_id)

        # Number-gated unit abbreviations ("30 minutes" -> "30 min")
        if policy.abbreviations and not header_like:
            for unit_re, abbrev, rule_id in _UNIT_RULES:
                if not unit_re.search(masked_text):
                    continue
                new_text = unit_re.sub(lambda m, _a=abbrev: f"{m.group(1)} {_a}", masked_text)
                if new_text != masked_text:
                    masked_text = new_text
                    used_rules.append(rule_id)

        # Restore protected code spans
        for idx, span in enumerate(code_spans):
            masked_text = masked_text.replace(f"\x00CODE_{idx}\x00", span)

        candidate_text = masked_text
        new_tokens = tokenizer.count_tokens(candidate_text)

        # Gate commit on both token reduction AND 100% required atom preservation
        atoms_preserved = all(a.surface in candidate_text for a in unit_required_atoms)

        if new_tokens < orig_tokens and candidate_text != orig_text and atoms_preserved:
            rule_str = "+".join(used_rules)
            seg = OutputSegment(
                output_start=0,
                output_end=len(candidate_text.encode("utf-8")),
                kind="rewrite",
                sources=unit.sources,
                rule_id=rule_str,
                text=candidate_text,
            )
            return candidate_text, [seg]
        else:
            seg = OutputSegment(
                output_start=0,
                output_end=len(orig_text.encode("utf-8")),
                kind=unit.kind,
                sources=unit.sources,
                rule_id="parser_structural" if unit.kind == "rewrite" else None,
                text=orig_text,
            )
            return orig_text, [seg]
