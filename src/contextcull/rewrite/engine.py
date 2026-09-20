"""Transactional rewriting engine with net token savings and atom preservation validation."""

from __future__ import annotations

import re
from collections.abc import Sequence

from contextcull.ir.models import Atom, CandidateUnit, CompileMode, CompilePolicy, OutputSegment
from contextcull.rewrite.rules import ABBREVIATIONS, PHRASE_RULES
from contextcull.tokenize.profile import TokenizerProfile

try:
    import ahocorasick_rs

    HAS_AHOCORASICK_RS = True
except ImportError:
    ahocorasick_rs = None
    HAS_AHOCORASICK_RS = False


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

        unit_atom_surfaces = {a.surface.lower() for a in atoms if a.atom_id in unit.atom_ids}
        unit_required_atoms = [a for a in atoms if a.atom_id in unit.atom_ids and a.required]

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
                (self._patterns[i], self._replacements[i], self._rule_ids[i])
                for i in matched_indices
            ]
        else:
            rules_to_check = list(zip(self._patterns, self._replacements, self._rule_ids))

        for pat, repl, rule_id in rules_to_check:
            if pat.lower() in unit_atom_surfaces:
                continue

            # Protect hyphenated flags (e.g. --policy-document) and paths (/foo/document)
            pattern_re = re.compile(
                r"(?<![\w\-\/])" + re.escape(pat) + r"(?![\w\-\/])", re.IGNORECASE
            )
            if pattern_re.search(masked_text):
                new_text = pattern_re.sub(repl, masked_text)
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

        if (
            (
                new_tokens < orig_tokens
                or (new_tokens == orig_tokens and len(candidate_text) < len(orig_text))
            )
            and candidate_text != orig_text
            and atoms_preserved
        ):
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
