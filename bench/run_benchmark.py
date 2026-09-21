"""Reproducible empirical benchmark: ContextCull vs. Sumy vs. trivial baselines.

Ground truth is NOT derived from ContextCull's own output (that was the bug in
the previous version of this script: it extracted atoms with ContextCull, then
scored ContextCull against its own extraction - a tautology that could never
fail). Instead, each eval document has a hand-labelled fact list in
bench/facts/<doc>.json: strings a human pulled directly from the RAW document,
spread across it, that a good compressor must keep.

Baselines run at a TOKEN BUDGET MATCHED to ContextCull's own output size for
that document (binary search for Sumy's sentence count; a token-sliced "lead"
baseline), so every engine is compared at the same compression ratio instead
of some baselines being handed a bigger budget:
  - Sumy LexRank / LSA, sentence count binary-searched to match token count.
  - "lead": first N tokens of the format-native plain text.
  - format-native trivial extraction, run at FULL length (no cutting): stdlib
    `email` for .eml, stdlib `html.parser` for .html, pypdf for .pdf. This is
    the "what if you just stripped the container format" baseline.
  - ContextCull itself (contextcull.ContextCompiler, COMPACT mode).

Every engine reports status and a `regression` flag (output tokens > input
tokens) as SEPARATE fields - a non-OK status or a regression is never folded
into a misleading single "PASS". Latency is the median of 5 runs after a
warmup run.

Run: uv run --group bench python bench/run_benchmark.py [--all] [file ...]
Output: bench/results/benchmark_results.json and benchmark_results.md
"""

from __future__ import annotations

import argparse
import email
import json
import re
import statistics
import sys
import time
from collections.abc import Callable
from email import policy as email_policy
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import tiktoken

from contextcull import CompileMode, CompilePolicy, ContextCompiler

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = REPO_ROOT / "examples" / "eval"
FACTS_DIR = Path(__file__).resolve().parent / "facts"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

WARMUP_RUNS = 1
TIMED_RUNS = 5

ALL_DOCS = [
    "01_email_thread.eml",
    "02_novel_chapter.txt",
    "03_slack_chat.txt",
    "04_synthetic_technical_report.docx",
    "05_web_article.html",
    "06_academic_paper.pdf",
    "07_structured_feed.xml",
    "08_cloud_audit.json",
    "09_incident_metrics.csv",
    "10_source_module.py",
]

ENC = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(ENC.encode(text, disallowed_special=()))


def median_latency_ms[T](
    fn: Callable[[], T], warmup: int = WARMUP_RUNS, runs: int = TIMED_RUNS
) -> tuple[float, T]:
    results: list[T] = [fn() for _ in range(warmup)]
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        results.append(fn())
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples), results[-1]


# --------------------------------------------------------------------------
# Format-native trivial extractors (independent of ContextCull's own parsers,
# so the benchmark can't be fooled by ContextCull's ingest code changing).
# --------------------------------------------------------------------------


def _split_mbox_messages(raw_text: str) -> list[str]:
    """Split an mbox-style concatenation on 'From ...' envelope lines."""
    from_line = re.compile(r"^From \S+.*\d{4}\s*$")
    lines = raw_text.splitlines(keepends=True)
    messages: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if from_line.match(line) and current:
            messages.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        messages.append(current)
    return ["".join(m) for m in messages] if messages else [raw_text]


def extract_eml_native(raw_bytes: bytes) -> str:
    """stdlib `email`: From/To/Subject/Date headers + text/plain body per message."""
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    rendered = []
    for msg_text in _split_mbox_messages(raw_text):
        msg = email.message_from_string(msg_text, policy=email_policy.default)
        headers = [f"{h}: {msg.get(h)}" for h in ("From", "To", "Subject", "Date") if msg.get(h)]
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body = part.get_content()
                    except Exception:  # noqa: BLE001 - fall back to raw payload decode
                        payload = part.get_payload(decode=True)
                        body = (
                            payload.decode("utf-8", errors="replace")
                            if isinstance(payload, bytes)
                            else ""
                        )
                    break
        else:
            try:
                body = msg.get_content()
            except Exception:  # noqa: BLE001
                payload = msg.get_payload(decode=True)
                body = (
                    payload.decode("utf-8", errors="replace")
                    if isinstance(payload, bytes)
                    else str(msg.get_payload())
                )
        rendered.append("\n".join(headers) + "\n\n" + str(body))
    return "\n\n----------\n\n".join(rendered)


class _VisibleTextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript"}
    BLOCK = {"p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def extract_html_native(raw_bytes: bytes) -> str:
    """stdlib `html.parser`: visible text, skipping script/style/nav/footer/header/noscript."""
    html_text = raw_bytes.decode("utf-8", errors="replace")
    parser = _VisibleTextExtractor()
    parser.feed(html_text)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_native(raw_bytes: bytes) -> str:
    """pypdf text extraction, whitespace-normalized (matches bench/facts/06_academic_paper.json)."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", text).strip()


def format_native_text(filename: str, raw_bytes: bytes) -> str | None:
    """Returns None (not applicable) for formats with no independent trivial extractor
    (docx/xml/json/csv/py) - their raw bytes already decode as plain text, so the
    "format-native" baseline is the same as the raw text for those."""
    ext = Path(filename).suffix.lower()
    if ext == ".eml":
        return extract_eml_native(raw_bytes)
    if ext == ".html":
        return extract_html_native(raw_bytes)
    if ext == ".pdf":
        return extract_pdf_native(raw_bytes)
    if ext == ".docx":
        return None
    return raw_bytes.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# Matched-budget baselines
# --------------------------------------------------------------------------


def lead_baseline(native_text: str, target_tokens: int) -> str:
    tokens = ENC.encode(native_text, disallowed_special=())
    return ENC.decode(tokens[:target_tokens])


_SUMY_DOC_CACHE: dict[int, Any] = {}

# ponytail: sumy's LsaSummarizer re-runs a full SVD over ALL sentences on every call
# regardless of the requested sentence count, so the binary search below (even at
# ~12 calls) is O(12x) the cost of one SVD over the whole document. On a long native
# text (e.g. a ~150KB novel, thousands of sentences) that's minutes, not seconds.
# Cap the text sumy analyzes so the benchmark stays runnable; ContextCull and the
# other baselines still see the FULL document. Upgrade path if this matters: cache
# the fitted SVD across binary-search steps instead of truncating the input.
SUMY_MAX_CHARS = 40_000


def _sumy_parse(native_text: str):
    """Parses `native_text` into a sumy document once per text (cached by id), since
    the (nltk-backed) sentence tokenizer is the expensive part and both LexRank and
    LSA summarize the same parsed document."""
    try:
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.parsers.plaintext import PlaintextParser
    except ImportError:
        return None
    text = native_text[:SUMY_MAX_CHARS]
    key = id(native_text)
    if key not in _SUMY_DOC_CACHE:
        _SUMY_DOC_CACHE.clear()  # one doc at a time is all we need
        _SUMY_DOC_CACHE[key] = PlaintextParser.from_string(text, Tokenizer("english")).document
    return _SUMY_DOC_CACHE[key]


def _sumy_prepare(native_text: str, algorithm: str):
    document = _sumy_parse(native_text)
    if document is None:
        return None
    from sumy.summarizers.lex_rank import LexRankSummarizer
    from sumy.summarizers.lsa import LsaSummarizer

    summarizer = LexRankSummarizer() if algorithm == "lexrank" else LsaSummarizer()
    return document, summarizer, len(document.sentences)


def _sumy_render(document, summarizer, n: int) -> str:
    return "\n".join(str(s) for s in summarizer(document, n)) if n > 0 else ""


def sumy_matched_sentence_count(document, summarizer, n_sentences: int, target_tokens: int) -> int:
    """Binary search the largest sentence count whose rendered token count doesn't
    exceed the target budget. This search is NOT part of the timed latency - only
    the final render at the matched count is timed, same as the other baselines."""
    if n_sentences == 0 or target_tokens <= 0:
        return 0
    lo, hi = 0, n_sentences
    best_n = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        text = _sumy_render(document, summarizer, mid)
        if count_tokens(text) <= target_tokens:
            best_n = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best_n


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def fact_recall(text: str, facts: list[str]) -> tuple[int, int]:
    hits = sum(1 for f in facts if f in text)
    return hits, len(facts)


def engine_record(
    name: str,
    text: str,
    raw_tokens: int,
    native_tokens: int | None,
    facts: list[str] | None,
    latency_ms: float,
    status: str = "OK",
) -> dict:
    out_tokens = count_tokens(text)
    record = {
        "engine": name,
        "status": status,
        "regression": out_tokens > raw_tokens,
        "output_tokens": out_tokens,
        "reduction_vs_raw_pct": round((1.0 - out_tokens / raw_tokens) * 100.0, 1)
        if raw_tokens
        else 0.0,
        "reduction_vs_native_pct": (
            round((1.0 - out_tokens / native_tokens) * 100.0, 1) if native_tokens else None
        ),
        "latency_ms_median_of_5": round(latency_ms, 2),
    }
    if facts is not None:
        hits, total = fact_recall(text, facts)
        record["fact_recall"] = f"{hits}/{total}"
        record["fact_recall_pct"] = round(hits / total * 100.0, 1) if total else None
    else:
        record["fact_recall"] = "N/A"
        record["fact_recall_pct"] = None
    return record


def run_one(filename: str) -> dict:
    path = EVAL_DIR / filename
    raw_bytes = path.read_bytes()
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    raw_tokens = count_tokens(raw_text)

    native_text = format_native_text(filename, raw_bytes)
    native_tokens = count_tokens(native_text) if native_text is not None else None

    facts_path = FACTS_DIR / f"{Path(filename).stem}.json"
    facts = None
    if facts_path.exists():
        facts = json.loads(facts_path.read_text(encoding="utf-8"))["facts"]

    engines = []

    # 1. ContextCull (COMPACT mode, budget-free natural-density selection).
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=True)
    cc_latency, cc_res = median_latency_ms(lambda: compiler.compile(raw_bytes, policy=policy))
    target_tokens = count_tokens(cc_res.text)
    cc_record = engine_record(
        "contextcull",
        cc_res.text,
        raw_tokens,
        native_tokens,
        facts,
        cc_latency,
        status=cc_res.status,
    )
    engines.append(cc_record)

    # 2. format-native trivial extraction, full length, no cutting.
    if native_text is not None:
        native_latency, _ = median_latency_ms(lambda: format_native_text(filename, raw_bytes))
        engines.append(
            engine_record(
                "format_native_full", native_text, raw_tokens, native_tokens, facts, native_latency
            )
        )
        budget_text = native_text
    else:
        budget_text = raw_text

    # 3. "lead": first N tokens of the format-native text, matched to ContextCull's budget.
    lead_latency, lead_text = median_latency_ms(lambda: lead_baseline(budget_text, target_tokens))
    engines.append(
        engine_record("lead_matched", lead_text, raw_tokens, native_tokens, facts, lead_latency)
    )

    # 4. Sumy LexRank / LSA, sentence count matched to ContextCull's budget.
    # The binary search for the matched sentence count runs once (untimed); only
    # the final render at that fixed count is timed, so latency reflects a single
    # summarization call like the other baselines, not the whole search.
    for algo, label in (("lexrank", "sumy_lexrank_matched"), ("lsa", "sumy_lsa_matched")):
        prepared = _sumy_prepare(budget_text, algo)
        if prepared is None:
            continue
        document, summarizer, n_sentences = prepared
        matched_n = sumy_matched_sentence_count(document, summarizer, n_sentences, target_tokens)
        latency, text = median_latency_ms(
            lambda d=document, s=summarizer, n=matched_n: _sumy_render(d, s, n)
        )
        engines.append(engine_record(label, text, raw_tokens, native_tokens, facts, latency))

    return {
        "file": filename,
        "raw_tokens": raw_tokens,
        "native_plain_tokens": native_tokens,
        "target_tokens_matched_to_contextcull": target_tokens,
        "facts_total": len(facts) if facts is not None else None,
        "sumy_analyzed_first_n_chars": min(len(budget_text), SUMY_MAX_CHARS),
        "engines": engines,
    }


def render_markdown(all_results: list[dict]) -> str:
    lines = [
        "# ContextCull benchmark",
        "",
        "Matched-token-budget comparison. Ground truth = hand-labelled facts pulled from the raw",
        "document (bench/facts/*.json), independent of ContextCull's own parsing. `status`/`regression`",
        "are reported separately - a regression is never mislabelled PASS.",
        "",
    ]
    for doc in all_results:
        lines.append(f"## {doc['file']}")
        lines.append("")
        lines.append(
            f"Raw tokens: {doc['raw_tokens']} | Format-native plain tokens: "
            f"{doc['native_plain_tokens'] if doc['native_plain_tokens'] is not None else 'N/A'} | "
            f"Facts: {doc['facts_total'] if doc['facts_total'] is not None else 'N/A (no bench/facts file)'}"
        )
        lines.append(
            f"Sumy baselines analyzed the first {doc['sumy_analyzed_first_n_chars']:,} chars "
            "of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - "
            "ContextCull and the other baselines see the full document."
        )
        lines.append("")
        lines.append(
            "| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |"
        )
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for e in doc["engines"]:
            reduc_native = (
                f"{e['reduction_vs_native_pct']:.1f}%"
                if e["reduction_vs_native_pct"] is not None
                else "N/A"
            )
            lines.append(
                f"| {e['engine']} | {e['status']} | {'YES' if e['regression'] else 'no'} | "
                f"{e['output_tokens']:,} | {e['reduction_vs_raw_pct']:.1f}% | {reduc_native} | "
                f"{e['fact_recall']} | {e['latency_ms_median_of_5']:.2f} ms |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="Run all 10 examples/eval/ documents.")
    ap.add_argument(
        "files", nargs="*", help="Specific eval filenames (relative to examples/eval/)."
    )
    args = ap.parse_args()

    targets = ALL_DOCS if args.all or not args.files else args.files

    all_results = []
    for filename in targets:
        path = EVAL_DIR / filename
        if not path.exists():
            print(f"skip (not found): {filename}", file=sys.stderr)
            continue
        print(f"Benchmarking {filename} ...")
        all_results.append(run_one(filename))

    (RESULTS_DIR / "benchmark_results.json").write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    markdown = render_markdown(all_results)
    (RESULTS_DIR / "benchmark_results.md").write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
