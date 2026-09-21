# ContextCull

[![CI](https://github.com/MayurVirkar/ContextCull/actions/workflows/ci.yml/badge.svg)](https://github.com/MayurVirkar/ContextCull/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

ContextCull is a deterministic, extractive pre-processor for LLM prompts. You give it a long
document (an email archive, chat log, web page, PDF, Word file, JSON/XML/CSV export or a source
file). It removes structural noise and low-information sentences, and returns two things:

- a shorter text made only of sentences and lines taken from the input;
- a JSON manifest that maps every piece of that text back to byte offsets in the original file.

It does not generate text and has no model weights. It makes no network calls, and the same
input always produces byte-identical output.

## Contents

- [When to use it](#when-to-use-it)
- [Results at a glance](#results-at-a-glance)
- [Installation](#installation)
- [Quick start](#quick-start)
- [What is guaranteed](#what-is-guaranteed)
- [Provenance manifest and validation](#provenance-manifest-and-validation)
- [Supported input formats](#supported-input-formats)
- [How the pipeline works](#how-the-pipeline-works)
- [Modes and policy options](#modes-and-policy-options)
- [Benchmarks](#benchmarks)
- [Multilingual corpora](#multilingual-corpora)
- [Known limitations](#known-limitations)
- [Development](#development)
- [Project layout](#project-layout)

## When to use it

ContextCull works well when:

- the input carries a lot of structural overhead: mail transport headers, HTML markup and
  navigation, mailing-list footers, quoted reply chains, test-runner noise. On the email
  corpus below it cuts 83.7% of tokens and keeps 16 of 18 hand-picked body facts;
- you need to show where every line of a prompt came from, for audits or when debugging a
  retrieval pipeline;
- specific identifiers must survive. CVE IDs, IPv4/IPv6 addresses, UUIDs, git SHAs, AWS
  instance IDs, and any terms you pass with `--require-term` are guaranteed to appear in the
  output. If they can't all fit in a token budget, the compile fails instead.

It is the wrong tool when:

- you want a summary in the LLM sense. ContextCull selects sentences; it does not paraphrase,
  merge or explain them;
- the text is already dense prose. On a Frankenstein excerpt, simply keeping the first half of
  the book retained more of our test facts (14/20) than ContextCull did at the same length
  (9/20);
- every fact matters. Outside the required identifier classes, sentence selection is a
  heuristic. On the *Attention Is All You Need* paper it keeps 11 of 20 hand-picked
  numeric details (hyperparameters, scores) while halving the length;
- the input is a numeric table. CSV rows that each carry a timestamp are all treated as
  entity-bearing and kept, so a metrics CSV is returned almost unchanged.

## Results at a glance

These numbers come from the benchmark in `bench/`, run on Linux with Python 3.13.15. The
[Benchmarks](#benchmarks) section has the method and the full tables.

- **Recall** means hand-labelled facts from the raw document (`bench/facts/*.json`) that
  appear verbatim in the output.
- **Tokens** are `cl100k_base`.
- **"Plain text"** is what a trivial parser already gives you: stdlib `email` for mail,
  `html.parser` visible text for HTML, `pypdf` text for PDF, the file itself otherwise.
- **"Lead"** is the first N tokens of the plain text, where N is ContextCull's output size.

| Document | Plain-text tokens | ContextCull tokens | Reduction vs plain text | ContextCull recall | Lead recall (same size) | Latency |
| :--- | ---: | ---: | ---: | :---: | :---: | ---: |
| Email corpus (15 SpamAssassin messages) | 7,150 | 3,534 | 50.6% | 16/18 | 11/18 | 94 ms |
| Ubuntu IRC log | 16,213 | 11,407 | 29.6% | 17/22 | 9/22 | 134 ms |
| Wikipedia article (HTML) | 31,268 | 18,722 | 40.1% | 13/18 | 18/18 | 1,684 ms |
| *Attention Is All You Need* (PDF) | 9,565 | 4,535 | 52.6% | 11/20 | 13/20 | 813 ms |
| Frankenstein, first chapters | 34,336 | 18,737 | 45.4% | 9/20 | 14/20 | 345 ms |
| CPython `difflib.py` | 21,241 | 10,295 | 51.5% | 7/16 | 9/16 | 128 ms |
| CISA advisories (XML) | 131,358 | 94,559 | 28.0% | 14/15 | 15/15 | 869 ms |
| CVE record (JSON) | 14,661 | 12,207 | 16.7% | 15/15 | 15/15 | 70 ms |
| EC2 CPU metrics (CSV) | 72,396 | 72,395 | 0.0% | 20/20 | 20/20 | 582 ms |

Measured against raw input, the reductions look larger: 83.7% for the email, 94.6% for the
HTML, 99.7% for the PDF. That is mostly because of what the format parsers strip, not
because of sentence selection. The plain-text column is the fairer comparison.

On structure-heavy inputs (mail, chat logs), ContextCull keeps noticeably more facts than a
same-size cut or Sumy LexRank/LSA. On clean prose, papers and code it does not beat a simple
"take the beginning" cut.

## Installation

Requires Python 3.13 or newer. ContextCull is not on PyPI yet, so install it from GitHub:

```bash
pip install "git+https://github.com/MayurVirkar/ContextCull.git"
```

To pin the tagged release:

```bash
pip install "git+https://github.com/MayurVirkar/ContextCull.git@v1.0.0"
```

For development:

```bash
git clone https://github.com/MayurVirkar/ContextCull.git
cd ContextCull
uv sync --all-groups
bash scripts/gate.sh
```

Runtime dependencies are `numpy`, `scipy`, `scikit-learn`, `sparse-dot-topn`, `tiktoken`,
`markdown-it-py`, `pypdf`, `defusedxml`, `lingua-language-detector`, `ahocorasick-rs`,
`orjson` and `typer-slim`.

## Quick start

### Command line

The package installs two equivalent commands, `contextcull` and `cull`.

```bash
# Compile with no token budget. ContextCull decides how much to keep.
contextcull compile examples/eval/01_email_thread.eml -o compiled.md --manifest manifest.json

# Compile into a hard budget of 1,000 cl100k_base tokens.
contextcull compile examples/eval/01_email_thread.eml \
  --budget 1000 --tokenizer openai:cl100k_base \
  -o summary_1k.md --manifest manifest_1k.json

# Make sure specific terms survive (repeatable).
contextcull compile report.txt -r "PostgreSQL" -r "us-east-1"

# Show the parsed blocks and detected atoms.
contextcull inspect examples/eval/01_email_thread.eml --show blocks,atoms

# Check a compiled file against its manifest and the original source.
contextcull validate compiled.md --manifest manifest.json --source examples/eval/01_email_thread.eml
```

`compile` options:

| Option | Default | Meaning |
| :--- | :--- | :--- |
| `--budget`, `-b` | none | Target output size in tokens. Without it, ContextCull picks its own cut-off (see [Selection](#how-the-pipeline-works)). |
| `--tokenizer`, `-t` | `openai:cl100k_base` | Tokenizer used for counting. Accepts `openai:<encoding or model>`, `cl100k_base`, `o200k_base`, `p50k_base`, `r50k_base`, `gpt-4`, `gpt-4o`, `gpt-3.5-turbo`, or `heuristic:<name>` for a rough 4-characters-per-token estimate. Unknown names are rejected. |
| `--mode`, `-m` | `compact` | `verbatim`, `strict`, `compact` or `task` (see [Modes](#modes-and-policy-options)). |
| `--output`, `-o` | stdout | Where to write the compiled text. |
| `--manifest` | none | Where to write the provenance manifest (JSON). |
| `--require-term`, `-r` | none | A term that must appear in the output. Repeatable. |
| `--hard-budget / --soft-budget` | hard | With a hard budget, the compile fails if the required content cannot fit. |
| `--abbreviations / --no-abbreviations` | off | Replace long technical words with standard short forms (e.g. `configuration` → `cfg`) when that saves tokens. |

The CLI exits with `0` on success and a non-zero code on any other status.

### Python

```python
from contextcull import ContextCompiler, CompilePolicy, TokenBudget

compiler = ContextCompiler()  # compact mode

result = compiler.compile_file("examples/eval/01_email_thread.eml")
if result.ok:
    print(result.metrics["input_tokens"], "->", result.metrics["output_tokens"], "tokens")
    prompt_context = result.text
    manifest = result.manifest

# Hard budget, plus terms that must survive:
result = compiler.compile(
    open("report.txt", "rb").read(),
    budget=TokenBudget(tokens=2000, profile="openai:cl100k_base", hard_budget=True),
    policy=CompilePolicy(required_terms=("PostgreSQL", "us-east-1")),
)
if result.status == "TARGET_BUDGET_UNSAFE":
    print("Need at least", result.metrics["minimum_safe_tokens"], "tokens")
```

`compile()` accepts `str` or `bytes`. `compile_file()` reads the file as bytes, so PDF and DOCX
work directly. Both return a `CompileResult` with these fields:

- `status`
- `ok`
- `text`
- `manifest`
- `metrics`
- `diagnostics`

`result.write_text(path)` and `result.write_manifest(path)` save the text and the manifest.

A one-call helper is also available: `from contextcull import summarize; summarize(text) -> str`.

## What is guaranteed

**Deterministic output.** The same input bytes, options and package version always give the
same output bytes. This was checked across different `PYTHONHASHSEED` values.

**Required atoms always survive.** Detection is regex-based. These classes are marked required:

| Class | Example |
| :--- | :--- |
| CVE identifiers | `CVE-2024-21626` |
| IPv4 addresses | `10.0.0.12`, `10.0.0.12:8080` |
| IPv6 addresses | `2001:db8::1` |
| UUIDs | `123e4567-e89b-12d3-a456-426614174000` |
| AWS instance IDs | `i-0abc12345def67890` |
| Full git SHAs | 40 or 64 hex characters |
| Short git SHAs | 7–12 hex characters next to a word like *commit*, *sha*, *rev*, *merge* or *fixes* |
| Your own terms | anything passed with `--require-term` or `CompilePolicy.required_terms` |

Dotted numbers that follow *version*, *release*, *section* or *upgrade from* are not treated as
IP addresses.

- **Without a budget,** every sentence or block that contains a required atom is kept.
- **With a hard budget,** if those sentences don't fit, the compile returns
  `TARGET_BUDGET_UNSAFE`. It reports `minimum_safe_tokens` and the atoms that would be lost.
- **After selection,** a final validation step checks that every required atom is in the
  output. If one is missing, the result is `INVARIANT_FAILED` and no text is returned.

**Soft atoms are best effort.** These are extracted too, and they steer selection, but they are
not guaranteed:

- quantities with units;
- currency amounts;
- timestamps;
- file paths and URLs;
- code identifiers;
- e-mail addresses;
- compliance acronyms (GDPR, SOC2, …);
- negations ("not approved", "без", "不能").

**Hard budgets are respected.** When a hard budget returns `OK`, the output's exact token count
under the chosen tokenizer is at or below the budget. Heading context that selection pulls in
and the newlines between units both count towards that total.

**Every output line points back to the source.** See the next section.

### Result statuses

| Status | Meaning |
| :--- | :--- |
| `OK` | Compiled successfully. |
| `TARGET_BUDGET_UNSAFE` | Hard budget too small for the required content. `metrics["minimum_safe_tokens"]` says how much is needed; the manifest lists `missing_atoms`. |
| `INVARIANT_FAILED` | Final validation found a provenance mismatch, a missing required atom or a budget overrun. No text is returned; `diagnostics` explains why. |
| `INPUT_TOO_LARGE` | Input (or extracted text) is over 10 MB. |
| `UNDECODABLE_INPUT` | The text encoding could not be determined, e.g. ambiguous UTF-16 without a byte-order mark. |

Empty input returns `OK` with empty text.

## Provenance manifest and validation

Each manifest records:

- the source's SHA-256;
- the format, and what the byte offsets refer to (`span_basis`);
- the tokenizer and compile mode;
- metrics;
- one entry per output segment.

Here is a manifest for a small plain-text input:

```json
{
  "schema_version": "1.0",
  "status": "OK",
  "source": {
    "document_id": "sha256:bdf6dab3…",
    "byte_length": 262,
    "format": "text",
    "span_basis": "raw_bytes"
  },
  "tokenizer": { "profile": "openai:cl100k_base", "exact": true },
  "metrics": {
    "input_tokens": 69, "output_tokens": 64, "compression_ratio": 0.0725,
    "required_atom_coverage": 1.0, "retained_required_atoms_count": 2,
    "copy_segments_count": 3, "rewrite_segments_count": 1, "aggregate_segments_count": 0
  },
  "output_segments": [
    { "output_start": 23, "output_end": 102, "kind": "copy",
      "sources": [{ "document_id": "sha256:bdf6dab3…", "start": 24, "end": 103 }],
      "rule_id": null }
  ]
}
```

- `output_start`/`output_end` are byte offsets in the compiled text.
- `sources[].start`/`end` are byte offsets in the source.
- `required_atom_coverage` counts only required atoms. `total_atom_coverage` is a weaker
  presence check over all detected atoms.

Segments come in three kinds:

| Kind | What it is | How `validate` checks it |
| :--- | :--- | :--- |
| `copy` | The text is exactly the source bytes at the given span. | Decodes the source span with the document's encoding and compares it to the output bytes. |
| `rewrite` | The source sentence after a rule-based rewrite. `rule_id` names the rules applied, e.g. `discourse_prune` or `wg_in_order_to`. | Bounds and rule attribution only. The text is intentionally different from the source. |
| `aggregate` | Text assembled by a format parser, e.g. an email header block (the message's `From`/`To`/`Cc`/`Subject`/`Date` lines joined together) or a test-runner summary line. | Bounds only. |

**PDF and DOCX spans point into extracted text.** For these files the spans index the text
that ContextCull extracted, not the binary file, and the manifest says so with
`"span_basis": "extracted_text"` and `extracted_text_sha256`. `contextcull validate`
re-extracts the text from the source file, checks that hash, and then verifies spans against
it. Blocks produced by the PDF and DOCX parsers are marked `rewrite`, so they get bounds and
hash checks, not byte-for-byte checks.

`validate` prints what it actually checked. If it could not byte-verify any segment, it
exits with code 3 and prints a warning. Pass `--allow-unverified` to accept that.

## Supported input formats

The router picks one parser per document, in this order:

| Format | How it is detected | What the parser produces |
| :--- | :--- | :--- |
| PDF | `%PDF` magic bytes | Page text via `pypdf`, split into headings and paragraphs. Capped at 5,000 pages and 10 M extracted characters. |
| DOCX | ZIP containing `word/document.xml` | Paragraphs, headings and tables. The XML is read with a 10 MB decompressed-size cap and parsed with `defusedxml`. |
| HTML | Markup sniffing | Visible text only (scripts, styles and navigation dropped), split into headings, prose, lists and tables. |
| XML | Markup sniffing | Element text via `defusedxml`. |
| JSON | Parses as JSON | Key/value records. |
| CSV/TSV | `csv.Sniffer` | Header line plus 10-row chunks, copied verbatim. |
| Test-runner logs | Cargo, pytest, Vitest, Go test markers | A pass/fail summary line plus one block per failure with its location and assertion. |
| Source code | Test markers such as `#[test]`, `def test_`, `it('…')` | One block per function or test. |
| Email (RFC 822 / mbox) | `From:` and `Subject:` headers | Per message: one header block with From, To, Cc, Subject and Date. Transport and list headers (Received, Return-Path, X-*, List-*, …) are dropped. Quoted replies, signatures and list footers (Yahoo Groups, SourceForge, Mailman) are removed; the body is split into sentences. |
| Markdown | `#`, fences, tables or list markers | CommonMark blocks via `markdown-it-py`. |
| Plain text | Fallback | Paragraphs, then sentences. |

Text inputs can be in any of these encodings:

- UTF-8, with or without a BOM;
- UTF-16 LE or BE, with a BOM, or without one when the byte pattern is unambiguous;
- Latin-1 as a fallback.

ANSI colour escapes are stripped for analysis, but offsets still refer to the original bytes.

Sentence splitting handles Western punctuation, CJK `。！？`, Arabic `؟ ۔`, and Devanagari `।`.
It does not split on decimals, IP addresses, or common abbreviations (e.g., z. B., p. ex., …).
It also does not split on an ellipsis followed by lowercase text or a parenthesis.

## How the pipeline works

1. **Ingest.** The input is hashed (SHA-256), its encoding detected, and a table built that
   maps each character to its byte offset. Inputs over 10 MB are rejected.
2. **Parse.** The document is routed to one of the format parsers above, which produce typed
   blocks (heading, prose, list, table, code, log, email header, …), each with a source span.
3. **Detect atoms.** Regular expressions find required and soft atoms (see
   [What is guaranteed](#what-is-guaranteed)). Atoms outside the parsed blocks, such as the
   contents of `<script>` tags, are discarded.
4. **Segment.** Prose blocks are split into sentences; other blocks stay whole. Each unit
   records which atoms it contains. Boilerplate is filtered out: page numbers, tables of
   contents, and very short lines with no atoms or digits.
5. **Rank.** Units are vectorised with TF-IDF (word 1–2-grams; the token pattern also handles
   CJK). A sparse top-k cosine-similarity graph is built with `sparse-dot-topn`, and PageRank
   runs over it. This stage takes about 15 ms for ~700 units.
6. **Select.**
   - *Without a budget:* units with required atoms, test failures and email
     decisions/requests are kept. A greedy set cover then adds units until every distinct
     entity string is covered. The remaining units are added greedily, best new-vocabulary
     per token first (weighted by PageRank). That growth curve is cut at its knee, found
     with the Kneedle method.
   - *With a budget:* the mandatory units are placed first, then units that cover new
     entities, then units ranked by PageRank. Each unit's cost includes any heading it will
     pull in and the newline that separates it. If the exact token count of the result
     still overshoots, the lowest-ranked units are dropped until it fits.
7. **Closure.** The nearest preceding heading of each selected unit is added, so selected text
   keeps its section context.
8. **Rewrite** (`compact`/`task` modes only).
   - A fixed list of wordiness rules is applied, e.g. "in order to" → "to", or "due to the
     fact that" → "because".
   - Leading filler such as "It should be noted that" or "Furthermore," is removed.
   - Numeric units get short forms, e.g. "30 minutes" → "30 min".
   - With `abbreviations=True`, a short list of unambiguous technical terms is shortened as well.
   - Text inside backticks, header-like lines and capitalised mid-sentence words are never
     rewritten.
   - A rewrite is kept only if it strictly lowers the token count and every required atom in
     the unit survives; otherwise the original text is used.
9. **Validate.** Copy segments are compared to their source bytes. Required atoms are checked
   for presence, and the budget is re-checked with the exact tokenizer.
10. **Render.** Units are joined with newlines in source order, and the manifest is written.

## Modes and policy options

| Mode | Behaviour |
| :--- | :--- |
| `verbatim`, `strict` | Selection only. No rewriting; every emitted unit is copied or parser-aggregated. (The two modes currently behave identically.) |
| `compact` (default), `task` | Selection plus the rewrite stage above. (Currently identical; `task` is reserved for future query-aware selection.) |

`CompilePolicy` fields that affect output:

| Field | Default | Effect |
| :--- | :--- | :--- |
| `mode` | `compact` | See above. |
| `required_terms` | `()` | Extra terms that must survive. |
| `abbreviations` | `False` | Enable technical-term abbreviations in the rewrite stage. |
| `discourse_pruning` | `True` | Strip leading filler phrases in the rewrite stage. |
| `filter_boilerplate` | `True` | Drop page numbers, tables of contents and very short atom-free lines before ranking. |
| `preserve_failures` | `True` | Always keep test-failure blocks. |
| `max_k_neighbors` | `10` | Neighbours per unit in the similarity graph. |
| `pagerank_damping` | `0.85` | PageRank damping factor. |

`preserve_negation`, `preserve_modality`, `preserve_causality`, `source_order`, `with_legend`
and `min_safe_tokens` exist on the dataclass but are not used by the current pipeline.

## Benchmarks

### Method

The benchmark (`bench/run_benchmark.py`) avoids grading ContextCull with its own detectors:

- **Ground truth** comes from `bench/facts/<doc>.json`: 15–22 strings per document, picked by
  hand from the raw text. They cover body facts as well as identifiers, and a fact counts only
  if it appears verbatim in the output (whitespace normalised). The synthetic DOCX has no fact
  list.
- **Baselines** are compared at the same token count as ContextCull's output (`cl100k_base`):
  - *lead*: the first N tokens of the plain text;
  - *Sumy LexRank* and *Sumy LSA*: the sentence count is binary-searched to match N;
  - *format-native full*: the plain text itself, at full length.
- **Sumy input cap.** Sumy only sees the first ~40,000 characters of long documents, because
  its LSA recomputes an SVD on every call. On the novel, the XML, the JSON and the CSV it
  therefore returns less text than the matched size; the full report flags this.
- **Latency** is the median of 5 runs after a warm-up, measured in-process on a shared 32-vCPU
  Linux machine.
- **Status and regression are reported separately.** An output larger than its input is
  flagged as a regression, never counted as a pass.

Reproduce:

```bash
uv run --group bench python bench/run_benchmark.py --all   # writes bench/results/benchmark_results.{md,json}
python scripts/run_10_evals.py                             # compile-only table for the 10 formats
python scripts/run_multilingual_bench.py                   # compile-only table for the 12 corpora
```

### Recall at matched size

This table compares fact recall for every engine. The full per-document tables, with token
counts and latencies, are in [`bench/results/benchmark_results.md`](bench/results/benchmark_results.md).

| Document | ContextCull | Lead | Sumy LexRank | Sumy LSA | Plain text (full) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Email corpus | **16/18** | 11/18 | 6/18 | 11/18 | 18/18 |
| Ubuntu IRC log | **17/22** | 9/22 | 15/22 | 14/22 | 22/22 |
| Wikipedia (HTML) | 13/18 | **18/18** | 18/18 † | 18/18 † | 18/18 |
| Attention paper (PDF) | 11/20 | 13/20 | **14/20** | 9/20 | 20/20 |
| Frankenstein | 9/20 | **14/20** | 8/20 † | 8/20 † | 20/20 |
| `difflib.py` | 7/16 | **9/16** | 9/16 | 9/16 | 16/16 |
| CISA feed (XML) | 14/15 | **15/15** | 6/15 † | 6/15 † | 15/15 |
| CVE record (JSON) | 15/15 | 15/15 | 15/15 † | 15/15 † | 15/15 |
| EC2 metrics (CSV) | 20/20 | 20/20 | 7/20 † | 7/20 † | 20/20 |

† Sumy's output was shorter than the matched size because of its input cap.

### Compile-only results for the 10 evaluation files

These are reductions against the raw file, as produced by `scripts/run_10_evals.py`.

| # | File | Source | Raw tokens | Output tokens | Reduction | Latency |
| :-: | :--- | :--- | ---: | ---: | ---: | ---: |
| 1 | `01_email_thread.eml` | Apache SpamAssassin public corpus (15 unrelated messages, 2002) | 21,662 | 3,534 | 83.7% | 95 ms |
| 2 | `02_novel_chapter.txt` | *Frankenstein*, Project Gutenberg #84 (first ~150 KB) | 34,336 | 18,737 | 45.4% | 346 ms |
| 3 | `03_slack_chat.txt` | Ubuntu IRC logs, `#ubuntu`, 15–16 Jan 2024 | 16,213 | 11,407 | 29.6% | 134 ms |
| 4 | `04_synthetic_technical_report.docx` | **Synthetic**, generated by `scripts/` (invented CVE IDs) | 236 | 237 | −0.4% (regression) | 4 ms |
| 5 | `05_web_article.html` | Wikipedia, "Transformer (deep learning architecture)" | 343,709 | 18,722 | 94.6% | 1,687 ms |
| 6 | `06_academic_paper.pdf` | arXiv 1706.03762 | 9,579 † | 4,535 | 52.7% | 802 ms |
| 7 | `07_structured_feed.xml` | CISA cybersecurity advisories feed | 131,358 | 94,559 | 28.0% | 875 ms |
| 8 | `08_cloud_audit.json` | CVE-2024-21626 record, CVEProject/cvelistV5 | 14,661 | 12,207 | 16.7% | 69 ms |
| 9 | `09_incident_metrics.csv` | Numenta Anomaly Benchmark, EC2 CPU utilisation | 72,396 | 72,395 | 0.0% | 580 ms |
| 10 | `10_source_module.py` | CPython `Lib/difflib.py` | 21,241 | 10,295 | 51.5% | 127 ms |

† For PDF and DOCX, "raw tokens" means tokens of the extracted text.

The synthetic DOCX is only 236 tokens, and ContextCull keeps all of it; joining the
paragraphs adds one token. Source URLs, licences and SHA-256 hashes for every file are in
`examples/eval/METADATA.json`.

## Multilingual corpora

`examples/eval/multilingual/` holds 12 public-domain texts. For each one, the download script
(`scripts/download_multilingual_public_evals.py`) checks two things before saving it:

- the title line matches;
- at least 80% of the letters are in the expected script.

| # | Language | Text | Source | Raw tokens | Output tokens | Reduction | Latency |
| :-: | :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| 1 | English | *Alice's Adventures in Wonderland*, Carroll | Gutenberg #11 | 37,328 | 15,094 | 59.6% | 318 ms |
| 2 | English | *Calculus Made Easy*, Thompson | Gutenberg #33283 (from HTML) | 51,877 | 12,562 | 75.8% | 507 ms |
| 3 | Chinese | 西遊記 *Journey to the West*, Wu Cheng'en (truncated to ~500 KB) | Gutenberg #23962 | 251,906 | 140,252 | 44.3% | 943 ms |
| 4 | Hindi | Premchand: *Idgah*, *Poos ki Raat*, *Bade Bhai Sahab* | hi.wikisource.org | 52,141 | 9,578 | 81.6% | 159 ms |
| 5 | Spanish | *Don Quijote*, Cervantes (full, 2.2 MB) | Gutenberg #2000 | 664,427 | 438,643 | 34.0% | 9,208 ms |
| 6 | French | *Le Tour du monde en quatre-vingts jours*, Verne | Gutenberg #800 | 131,363 | 53,205 | 59.5% | 939 ms |
| 7 | Arabic | كليلة ودمنة *Kalila wa Dimna*, two chapters | ar.wikisource.org | 29,701 | 15,970 | 46.2% | 91 ms |
| 8 | Bengali | গীতাঞ্জলি *Gitanjali* (1913), Tagore, 16 poems | bn.wikisource.org | 11,831 | 1,487 | 87.4% | 30 ms |
| 9 | Portuguese | *Dom Casmurro*, Machado de Assis | Gutenberg #55752 | 123,493 | 73,969 | 40.1% | 1,156 ms |
| 10 | Russian | *1001 задача для умственного счёта*, Rachinsky | Gutenberg #16527 | 75,824 | 75,592 | 0.3% | 339 ms |
| 11 | Japanese | 羅生門 *Rashōmon*, Akutagawa | Gutenberg #1982 | 6,990 | 2,348 | 66.4% | 15 ms |
| 12 | Hebrew | ספר בראשית *Genesis* (unpointed Masoretic text) | — | 95,457 | 93,065 | 2.5% | 194 ms |

These are compile-only numbers. No fact lists exist for these corpora, so they show how much
text is removed and how fast, not what is kept. The Russian text is an arithmetic problem
book, where nearly every line holds numbers; the Hebrew text is one verse per line. Both
compress very little for that reason. Wikisource transcriptions are CC BY-SA 4.0; the
underlying works are public domain.

## Known limitations

- **Selection is a heuristic.**
  - Outside required atoms, it can drop sentences a reader would consider essential.
  - In the email benchmark, two body facts are still lost ("populating md0 with tar",
    "exmh.TODO"). They reach the selector but fall below the knee cut.
  - On the paper, most dropped facts are hyperparameters written in tables and inline maths.
- **No query awareness.** Selection does not know what question the LLM will be asked.
  `task` mode is reserved for that but currently behaves like `compact`.
- **Short inputs pass through almost unchanged.** With only a few sentences, the knee cut
  usually keeps all of them.
- **Numeric tables barely compress.** Every row that holds a timestamp or quantity counts as
  entity-bearing.
- **One parser per document.** A Markdown file with an embedded email, or a log inside
  prose, is handled by whichever parser the router picks first.
- **PDF quality depends on `pypdf`.** Multi-column layouts, tables and maths can come out in
  a scrambled order.
- **Language support is regex-based.** Negation detection covers common words in English,
  Spanish, Portuguese, French, German, Russian, Hindi, Bengali, Arabic, Persian, Hebrew and
  Chinese. Devanagari and Bengali vowel signs break `\b` word boundaries, so plain-word
  negation matching in those scripts is weaker than the bound-negation pattern.
  `lingua-language-detector` is used only by `contextcull.detect.language` and is not part of
  the compile path.
- **Size limit.** Input over 10 MB (after PDF/DOCX extraction) is rejected with
  `INPUT_TOO_LARGE`.
- **Not on PyPI yet.**

## Development

```bash
uv sync --all-groups
bash scripts/gate.sh
```

`scripts/gate.sh` runs the same six steps as CI (`.github/workflows/ci.yml`):

1. `ruff format --check`
2. `ruff check`
3. `pyright`
4. `bandit` over `src/`, skipping B105, B110 and B112 (reasons in `pyproject.toml`)
5. `pip-audit` over the locked runtime dependencies
6. `pytest` with coverage, which must be at least 80%

Current local result: 1,282 tests pass in about 5 s, with 95.19% line coverage of
`src/contextcull` (`cli.py` is excluded from coverage).

The test suite covers:

- **Units:** `tests/unit/`. Per-stage tests, provenance round-trips, encoding edge cases
  (UTF-8/UTF-16 with and without a BOM, Latin-1, ANSI escapes), DOCX zip-bomb rejection, PDF
  caps, and budget sweeps over Markdown with headings.
- **Property:** `tests/property/`. Hypothesis tests for SourceMap byte-offset round-trips.
- **Multilingual:** `tests/multilingual/`. 187 tests, about 17 per language across 11
  languages, generated by `scripts/generate_multilingual_tests.py` from hand-written native
  sentences. They cover segmentation, atom extraction, negation, byte-exact spans, and an
  end-to-end compile on a slice of each real corpus.
- **Differential:** `tests/differential/`. Compares against the Rust `tep-test` binary when
  `TEP_RUST_BIN` points to it; otherwise only the Python assertions run.

## Project layout

```
ContextCull/
├── src/contextcull/
│   ├── api.py            # ContextCompiler: runs the pipeline
│   ├── cli.py            # contextcull / cull commands
│   ├── errors.py         # exception types and their result statuses
│   ├── ingest/           # hashing, encoding detection, byte↔char source map
│   ├── route/            # picks a parser per document
│   ├── parse/            # pdf, docx, html, xml, json/csv, logs, code, email, markdown, text
│   ├── detect/           # atom regexes (required/soft), language detection helper
│   ├── segment/          # sentence splitting
│   ├── features/         # TF-IDF vectoriser
│   ├── rank/             # sparse similarity graph + PageRank
│   ├── select/           # budget-free (knee) and budgeted selection
│   ├── closure/          # heading closure
│   ├── rewrite/          # wordiness rules, filler pruning, abbreviations
│   ├── validate/         # final invariant checks
│   ├── render/           # output assembly and manifest
│   └── ir/               # data classes: spans, blocks, atoms, units, policy, result
├── bench/                # benchmark script, hand-labelled facts, results
├── examples/eval/        # 10 evaluation files + 12 multilingual corpora, with METADATA.json
├── scripts/              # dataset download, eval runners, test generator, gate.sh
└── tests/                # unit, property, multilingual, differential
```

## License

The code is under the MIT License; see [LICENSE](LICENSE). The evaluation files keep their own
licences, listed in `examples/eval/METADATA.json` and `examples/eval/multilingual/METADATA.json`.
Wikipedia and Wikisource texts are CC BY-SA 4.0, and the Numenta NAB CSV is AGPL-3.0.
