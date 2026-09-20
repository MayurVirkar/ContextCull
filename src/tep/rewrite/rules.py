"""Comprehensive abbreviations and phrase rules for compact context compilation.

Derived from write-good, proselint, plainlanguage.gov, and standard technical dictionaries.
All rules are guarded by tokenizer token-cost validation: substitutions are committed
ONLY if the resulting token count strictly decreases and no protected atom is violated.
"""

from __future__ import annotations

from typing import NamedTuple


class PhraseRule(NamedTuple):
    pattern: str
    replacement: str
    rule_id: str
    reversible: bool = True


# =========================================================================
# 1. TECHNICAL, TEMPORAL & QUANTITATIVE ABBREVIATIONS
# =========================================================================
ABBREVIATIONS: dict[str, str] = {
    # Calendar & Days
    "monday": "Mon",
    "tuesday": "Tue",
    "wednesday": "Wed",
    "thursday": "Thu",
    "friday": "Fri",
    "saturday": "Sat",
    "sunday": "Sun",
    "january": "Jan",
    "february": "Feb",
    "march": "Mar",
    "april": "Apr",
    "may": "May",
    "june": "Jun",
    "july": "Jul",
    "august": "Aug",
    "september": "Sep",
    "october": "Oct",
    "november": "Nov",
    "december": "Dec",

    # Units of Time
    "millisecond": "ms",
    "milliseconds": "ms",
    "microsecond": "µs",
    "microseconds": "µs",
    "nanosecond": "ns",
    "nanoseconds": "ns",
    "second": "s",
    "seconds": "s",
    "minute": "min",
    "minutes": "min",
    "hour": "h",
    "hours": "h",
    "week": "wk",
    "weeks": "wk",
    "month": "mo",
    "months": "mo",
    "year": "yr",
    "years": "yr",

    # Units of Data & Storage
    "kilobyte": "kB",
    "kilobytes": "kB",
    "megabyte": "MB",
    "megabytes": "MB",
    "gigabyte": "GB",
    "gigabytes": "GB",
    "terabyte": "TB",
    "terabytes": "TB",

    # Systems, Infrastructure & Architecture
    "database": "db",
    "databases": "dbs",
    "configuration": "cfg",
    "configurations": "cfgs",
    "infrastructure": "infra",
    "environment": "env",
    "environments": "envs",
    "repository": "repo",
    "repositories": "repos",
    "connection": "conn",
    "connections": "conns",
    "parameter": "param",
    "parameters": "params",
    "argument": "arg",
    "arguments": "args",
    "function": "fn",
    "functions": "fns",
    "directory": "dir",
    "directories": "dirs",
    "reference": "ref",
    "references": "refs",
    "token": "tok",
    "tokens": "toks",
    "maximum": "max",
    "minimum": "min",
    "initialize": "init",
    "initialized": "init",
    "initialization": "init",
    "assertion": "assert",
    "assertions": "asserts",
    "request": "req",
    "requests": "reqs",
    "response": "res",
    "responses": "res",
    "context": "ctx",
    "expected": "exp",
    "performance": "perf",
    "security": "sec",
    "authentication": "auth",
    "authorization": "authz",
    "production": "prod",
    "staging": "staging",
    "transaction": "tx",
    "transactions": "txs",
    "kubernetes": "k8s",
    "application": "app",
    "applications": "apps",
    "asynchronous": "async",
    "synchronous": "sync",
    "vulnerability": "vuln",
    "vulnerabilities": "vulns",
    "administrator": "admin",
    "administrators": "admins",
    "credential": "cred",
    "credentials": "creds",
    "specification": "spec",
    "specifications": "specs",
    "certificate": "cert",
    "certificates": "certs",
    "management": "mgmt",
    "destination": "dest",
    "destinations": "dests",
    "identifier": "id",
    "identifiers": "ids",
    "information": "info",
    "dependency": "dep",
    "dependencies": "deps",
    "software": "sw",
    "hardware": "hw",
    "network": "net",
    "packet": "pkt",
    "packets": "pkts",
    "message": "msg",
    "messages": "msgs",
    "command": "cmd",
    "commands": "cmds",
    "library": "lib",
    "libraries": "libs",
    "binary": "bin",
    "binaries": "bins",
    "executable": "exe",
    "executables": "exes",
    "process": "proc",
    "processes": "procs",
    "variable": "var",
    "variables": "vars",
    "constant": "const",
    "constants": "consts",
    "document": "doc",
    "documents": "docs",
    "documentation": "docs",
    "implementation": "impl",
    "implementations": "impls",

    # International Common Contractions (German, French, Spanish)
    "beziehungsweise": "bzw.",
    "circa": "ca.",
    "und so weiter": "usw.",
    "aproximadamente": "aprox.",
    "madame": "Mme",
    "monsieur": "M.",
}


# =========================================================================
# 2. PROSE REDUNDANCY & WORDINESS RULES (write-good, proselint, PlainLanguage)
# =========================================================================
_WORDINESS_CATALOG: list[tuple[str, str, str]] = [
    # Transition & Causal Scaffolding
    ("as a result of", "due to", "wg_as_result_of"),
    ("due to the fact that", "because", "wg_due_to_fact"),
    ("in order to", "to", "wg_in_order_to"),
    ("for the purpose of", "to", "wg_for_purpose_of"),
    ("for the reason that", "because", "wg_for_reason_that"),
    ("in the event that", "if", "wg_in_event_that"),
    ("in view of the fact that", "since", "wg_in_view_of_fact"),
    ("owing to the fact that", "because", "wg_owing_to_fact"),
    ("in accordance with", "per", "wg_in_accordance_with"),
    ("in connection with", "about", "wg_in_connection_with"),
    ("with respect to", "re:", "wg_with_respect_to"),
    ("with regard to", "re:", "wg_with_regard_to"),
    ("in reference to", "re:", "wg_in_reference_to"),
    ("prior to", "before", "wg_prior_to"),
    ("subsequent to", "after", "wg_subsequent_to"),
    ("in the course of", "during", "wg_in_course_of"),
    ("during the course of", "during", "wg_during_course_of"),
    ("by means of", "by", "wg_by_means_of"),
    ("by virtue of", "by", "wg_by_virtue_of"),
    ("in excess of", "over", "wg_in_excess_of"),
    ("in addition to", "besides", "wg_in_addition_to"),
    ("with the exception of", "except", "wg_with_exception_of"),

    # Temporal Wordiness
    ("at this point in time", "now", "wg_at_this_point"),
    ("at the present time", "now", "wg_at_present_time"),
    ("at the moment", "now", "wg_at_the_moment"),
    ("in the near future", "soon", "wg_in_near_future"),
    ("at an early date", "soon", "wg_at_early_date"),
    ("until such time as", "until", "wg_until_such_time"),
    ("at the same time that", "while", "wg_at_same_time_that"),
    ("on a regular basis", "regularly", "wg_on_regular_basis"),
    ("on a daily basis", "daily", "wg_on_daily_basis"),
    ("on a weekly basis", "weekly", "wg_on_weekly_basis"),
    ("on a monthly basis", "monthly", "wg_on_monthly_basis"),
    ("period of time", "period", "pl_period_of_time"),
    ("point in time", "time", "pl_point_in_time"),

    # Quantities & Modifiers
    ("a large number of", "many", "wg_large_num_of"),
    ("a majority of", "most", "wg_majority_of"),
    ("a small number of", "few", "wg_small_num_of"),
    ("a number of", "several", "wg_num_of"),
    ("the vast majority of", "most", "wg_vast_majority_of"),
    ("in close proximity to", "near", "wg_in_close_proximity"),
    ("close proximity", "proximity", "pl_close_proximity"),

    # Verbose Verb Phrases (Nominalizations)
    ("take into consideration", "consider", "pl_take_into_consideration"),
    ("give consideration to", "consider", "pl_give_consideration_to"),
    ("make an assumption", "assume", "pl_make_assumption"),
    ("make a decision", "decide", "pl_make_decision"),
    ("make a determination", "determine", "pl_make_determination"),
    ("conduct an investigation", "investigate", "pl_conduct_investigation"),
    ("come to an agreement", "agree", "pl_come_to_agreement"),
    ("reach a conclusion", "conclude", "pl_reach_conclusion"),
    ("has the ability to", "can", "pl_has_ability_to"),
    ("have the ability to", "can", "pl_have_ability_to"),
    ("is able to", "can", "pl_is_able_to"),
    ("are able to", "can", "pl_are_able_to"),
    ("is capable of", "can", "pl_is_capable_of"),
    ("are capable of", "can", "pl_are_capable_of"),
    ("has the potential to", "may", "pl_has_potential_to"),
    ("have the potential to", "may", "pl_have_potential_to"),
    ("it is necessary that", "must", "pl_it_is_necessary"),
    ("it is crucial that", "must", "pl_it_is_crucial"),
    ("it is mandatory that", "must", "pl_it_is_mandatory"),

    # Redundant Doublets & Tautologies
    ("each and every", "every", "pl_each_and_every"),
    ("first and foremost", "first", "pl_first_and_foremost"),
    ("one and only", "only", "pl_one_and_only"),
    ("basic fundamentals", "fundamentals", "pl_basic_fundamentals"),
    ("past history", "history", "pl_past_history"),
    ("future plans", "plans", "pl_future_plans"),
    ("end result", "result", "pl_end_result"),
    ("final outcome", "outcome", "pl_final_outcome"),
    ("unexpected surprise", "surprise", "pl_unexpected_surprise"),
    ("completely eliminate", "eliminate", "pl_completely_eliminate"),
    ("currently existing", "existing", "pl_currently_existing"),
    ("true facts", "facts", "pl_true_facts"),
    ("exact same", "same", "pl_exact_same"),
    ("gather together", "gather", "pl_gather_together"),
    ("consensus of opinion", "consensus", "pl_consensus_of_opinion"),
    ("advance notice", "notice", "pl_advance_notice"),
    ("advance reservations", "reservations", "pl_advance_reservations"),
    ("revert back", "revert", "pl_revert_back"),
    ("reply back", "reply", "pl_reply_back"),
    ("return back", "return", "pl_return_back"),
    ("refer back", "refer", "pl_refer_back"),
    ("collaborate together", "collaborate", "pl_collaborate_together"),
    ("join together", "join", "pl_join_together"),
    ("merge together", "merge", "pl_merge_together"),
    ("mix together", "mix", "pl_mix_together"),
    ("plan ahead", "plan", "pl_plan_ahead"),
    ("postpone until later", "postpone", "pl_postpone_until_later"),
    ("cancel out", "cancel", "pl_cancel_out"),

    ("parts per billion", "ppb", "rule_ppb"),
    ("less than or equal to", "≤", "rule_lte"),
    ("greater than or equal to", "≥", "rule_gte"),
    ("not equal to", "≠", "rule_neq"),
    ("does not equal", "≠", "rule_dneq"),

    # German Phrase Compaction
    ("zum beispiel", "z. B.", "de_zum_beispiel"),
    ("das heißt", "d. h.", "de_das_heisst"),
    ("unter umständen", "u. U.", "de_unter_umstaenden"),
    ("im vergleich zu", "ggü.", "de_im_vergleich_zu"),

    # French Phrase Compaction
    ("par exemple", "p. ex.", "fr_par_exemple"),
    ("c'est-à-dire", "c.-à-d.", "fr_cest_a_dire"),
    ("en ce qui concerne", "concernant", "fr_en_ce_qui_concerne"),

    # Spanish Phrase Compaction
    ("por ejemplo", "p. ej.", "es_por_ejemplo"),
    ("con respecto a", "respecto a", "es_con_respecto_a"),
    ("en relación con", "sobre", "es_en_relacion_con"),
]

PHRASE_RULES: list[PhraseRule] = [
    PhraseRule(pattern=pat, replacement=repl, rule_id=rid, reversible=False)
    for pat, repl, rid in _WORDINESS_CATALOG
]
