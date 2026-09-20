# TEP v2: Token-Efficiency Protocol

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Deterministic](https://img.shields.io/badge/execution-100%25%20deterministic-green.svg)]()
[![Provenance](https://img.shields.io/badge/provenance-byte--exact%20SHA256-blueviolet.svg)]()
[![Speed](https://img.shields.io/badge/latency-%3C200ms%20for%2038--pages-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**TEP v2** is a high-performance, deterministic context compiler and extractive summarization engine. It compiles massive, unstructured technical documents, codebases, logs, and emails into dense, source-mapped context packages optimized for downstream Frontier LLMs (e.g., Google Cloud Gemini, Claude, GPT-4).

TEP v2 reduces token consumption in **under 200 milliseconds**, guarantees **preservation of critical technical entities** (CVEs, IPs, UUIDs, commit hashes, instance IDs, quantities), and outputs a **verifiable byte-level provenance manifest**.

---

## The Problem: Why Raw LLMs and Classic Summarizers Fail

1. **The LLM "Lost in the Middle" & Quadratic Cost Problem:**
   Feeding 20,000 to 100,000 tokens of raw documents directly into frontier models incurs high latency, quadratic self-attention cost ($O(N^2)$), and risk of hallucination or dropped context.
2. **The Classic Summarizer "Centrality Trap" (Sumy / LexRank / LSA):**
   Graph-centrality summarizers like LexRank and SVD-based engines like LSA select sentences with high vocabulary overlap with the rest of the text. However, in security and technical reports, **the most critical facts (a CVE ID, an AWS instance ID, an exfiltration count) appear in only 1 or 2 sentences**. Because they lack broad lexical overlap, standard LexRank and LSA assign them near-zero centrality and **drop up to 95% of critical facts**.

---

## Empirical Benchmark

Evaluated on the 38-page incident report (`examples/sample_incident.txt`, 20,303 tokens) measuring ground-truth retention across 19 critical technical atoms (CVEs, AWS IDs, exfiltrated secret counts, microservice names). Tested on Linux, Python 3.13.15:

| Summarizer Engine | Latency | Output Tokens | Token Reduction | Atoms Retained (19 Ground Truth) | Atoms Dropped |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **TEP v2 (Zero-Budget, Generic)** | **161 ms** | **8,473** | **58.3%** | **18 / 19 (94.7%)** | `14 write tokens` |
| **Sumy LexRank (100 sentences)** | 2,978 ms | 3,746 | 81.5% | **3 / 19 (15.8%)** | `CVE-2026-66384`, `CVE-2026-53362`, `i-0622056ec3e996a7c`, `artifactory-3`, ... (16 total) |
| **Sumy LSA (100 sentences)** | 667 ms | 2,758 | 86.4% | **3 / 19 (15.8%)** | `CVE-2026-53362`, `956 secrets`, `moon-bot`, `moon-landing`, ... (16 total) |
| **Sumy LexRank (50 sentences)** | 2,915 ms | 2,002 | 90.1% | **3 / 19 (15.8%)** | `CVE-2026-66384`, `CVE-2026-53362`, `i-0622056ec3e996a7c`, `artifactory-3`, ... (16 total) |
| **Sumy LSA (50 sentences)** | 666 ms | 1,495 | 92.6% | **1 / 19 (5.3%)** | `CVE-2026-53362`, `i-0622056ec3e996a7c`, `artifactory-3`, `956 secrets`, ... (18 total) |

To reproduce the benchmark table locally:
```bash
uv run python bench/run_benchmark.py examples/sample_incident.txt
```

---

## Architecture: 10-Stage Deterministic Pipeline

TEP v2 eliminates hallucination by operating as a pure compiler with zero neural weights at compile time:

```mermaid
flowchart TD
    A["Raw Input (Bytes / File / Markdown / Logs)"] --> B["Stage 1: Ingestion & Invariant SourceMap"]
    B --> C["Stage 2: Structural Routing & Block Parsing"]
    B --> D["Stage 3: Protected Atom Detection (CVEs, IPs, Hashes, IDs)"]
    C & D --> E["Stage 4: Multilingual Candidate Segmentation"]
    E --> F["Stage 5: Sparse TF-IDF & Vectorized LexRank Graph"]
    F & D --> G["Stage 6: Selection (Submodular Entity Floor + Marginal Entropy)"]
    G --> H["Stage 7: Structural Context Closure"]
    H --> I["Stage 8: Transactional Rewriting (Discourse Pruning & Aho-Corasick)"]
    I --> J["Stage 9: Invariant Validation"]
    J --> K["Stage 10: Render Context & SHA-256 Provenance Manifest"]
    K --> L["Downstream Frontier LLM (Cloud Gemini)"]
```

### Key Stages Explained
1. **Immutable Ingestion & SourceMap:** Computes SHA-256 document fingerprint and byte-to-char translation table. Fast-paths ANSI-free inputs.
2. **Block Parsing & Routing:** Classifies and parses content across diverse document formats:
   - **HTML / Web Pages** (`.html`, `.htm`): Cleans DOM, strips scripts/styles/navigation, extracts headings, prose, lists, tables with exact source spans.
   - **XML** (`.xml`): Secure parsing of structured tags, attributes, and data elements via `defusedxml`.
   - **DOCX** (`.docx`): Direct OpenXML zip extraction of Word paragraphs, headings, and tables.
   - **PDF** (`.pdf`): Multi-page text extraction preserving document headings, paragraphs, and tables.
   - **JSON & CSV** (`.json`, `.csv`): Structured key-value fields and tabular records.
   - **Markdown** (`.md`): CommonMark AST parsing for headings, tables, code fences, and lists.
   - **Source Code & Logs**: High-precision parsing for Python, Rust, TS, Go, Cargo, Pytest, Vitest.
   - **RFC 822 Emails**: Header extraction (From, To, Subject, Date) and body segmentation.
   - **Plain Text**: Universal sentence boundary detection across Western, CJK, Arabic, and Indic scripts.
3. **Protected Atom Detection:** Regular expressions for critical identifiers (CVEs, IPv4/IPv6, UUIDs, Git SHAs, AWS Instance IDs, quantities, timestamps), automatically marking critical classes `required=True`.
4. **Candidate Unit Segmentation:** Universal sentence segmentation across Western, CJK (`。！？`), Arabic, and Indic scripts.
5. **Sparse LexRank Engine:** Computes top-$k$ cosine similarity graph via `sparse-dot-topn` and `scipy.sparse` power-iteration PageRank in ~15 ms.
6. **Submodular Entity Floor & Marginal Entropy Elbow:**
   - **Entity Floor:** Guarantees any sentence containing an essential entity atom is locked into the summary.
   - **Pareto Marginal Entropy:** In zero-budget mode, dynamically stops selecting narrative sentences when information gain flattens.
7. **Context Closure:** Restores structural dependencies (headers, parent code blocks) so output units remain coherent.
8. **Transactional Rewriting:** Losslessly prunes bureaucratic discourse scaffolding while strictly protecting attribution. Applies abbreviation rewrites via an Aho-Corasick automaton only if token cost strictly decreases and all required atoms are preserved.
9. **Invariant Validation:** Enforces strict invariants: 100% source backing for copied segments, valid bounds for rewrites, zero dropped required atoms, and budget compliance.
10. **Provenance Manifest:** Emits a JSON manifest detailing the exact byte spans `[start, end]` in the original source for every segment.

---

## Production Pipeline: TEP v2 + Cloud Gemini

The recommended architecture pairs TEP v2 as a deterministic pre-processor with Cloud Gemini as the synthesizer:

```
[Raw 38-page Doc / 20k tokens]
            │
            ▼  (161 ms, zero compute cost, 100% deterministic)
   ┌─────────────────┐
   │     TEP v2      │ ──► Drops non-contributing scaffolding, locks in 95%+ critical facts
   └─────────────────┘
            │
            ▼  [Compiled Context: 7.8k - 12.9k tokens]
   ┌─────────────────┐
   │  Cloud Gemini   │ ──► Generates dense, executive smart-caveman summary
   └─────────────────┘
            │
            ▼
[Final Actionable Summary]
```

---

## Installation

TEP v2 requires Python 3.13+. Install using `uv` (recommended) or `pip`:

```bash
# Clone the repository
git clone https://github.com/MayurVirkar/TEPv2.git
cd TEPv2

# Install dependencies using uv
uv sync

# Or using pip
pip install -e .
```

---

## CLI Usage

TEP includes a command-line interface powered by Typer:

### 1. Compile in Zero-Budget Mode (Natural Floor)
Automatically compress a document to its natural information-dense floor without guessing token counts:

```bash
tep compile examples/sample_incident.txt --output compiled.md --manifest manifest.json
```

### 2. Compile with a Target Token Budget
Enforce a hard token budget against a target tokenizer (e.g., `openai:cl100k_base`):

```bash
tep compile examples/sample_incident.txt \
  --budget 8000 \
  --tokenizer openai:cl100k_base \
  --output summary_8k.md \
  --manifest manifest_8k.json
```

If the requested budget is too small to safely retain all critical atoms, TEP raises `TARGET_BUDGET_UNSAFE` with the minimum safe token threshold.

### 3. Inspect Blocks and Atoms
View detected structural blocks and protected atoms:

```bash
tep inspect examples/sample_incident.txt --show blocks,atoms
```

### 4. Validate Provenance
Verify that a compiled summary and manifest match the original source file 1:1:

```bash
tep validate compiled.md --manifest manifest.json --source examples/sample_incident.txt
```

---

## Python API Usage

```python
from tep.api import ContextCompiler
from tep.ir.models import CompilePolicy, TokenBudget

compiler = ContextCompiler.from_profile("compact")

# Zero-Budget Natural Floor Compilation
result = compiler.compile_file("examples/sample_incident.txt")

if result.ok:
    print(f"Compressed from {result.metrics['input_tokens']} to {result.metrics['output_tokens']} tokens")
    print(result.text)
    
    # Access provenance manifest
    manifest = result.manifest
    print(f"Document SHA-256: {manifest['source']['document_id']}")
    print(f"Verified copy segments: {manifest['metrics']['copy_segments_count']}")
    print(f"Required atom coverage: {manifest['metrics']['required_atom_coverage'] * 100:.1f}%")
```

---

## Project Structure

```
TEPv2/
├── pyproject.toml              # Build configuration & dependencies
├── README.md                   # Project documentation & benchmarks
├── LICENSE                     # MIT License
├── .github/workflows/ci.yml    # GitHub Actions CI workflow
├── bench/
│   └── run_benchmark.py        # Reproducible empirical benchmark script
├── examples/
│   └── sample_incident.txt     # Real-world 38-page benchmark incident report
├── src/
│   └── tep/
│       ├── api.py              # ContextCompiler main entry point
│       ├── cli.py              # Command-line interface
│       ├── errors.py           # Protocol & budget error types
│       ├── closure/            # Structural hierarchy & context closure
│       ├── detect/             # Protected atom & multilingual language detection
│       ├── features/           # Universal TF-IDF vectorizer
│       ├── ingest/             # SourceMap & byte-exact decoders
│       ├── ir/                 # Intermediate representation & span models
│       ├── parse/              # Parsers (HTML, XML, DOCX, PDF, JSON, CSV, Code, Markdown, Logs, Email)
│       ├── rank/               # Vectorized sparse LexRank / PageRank
│       ├── render/             # Output renderer & provenance manifest
│       ├── rewrite/            # Transactional discourse pruning & rule engine
│       ├── route/              # Block router
│       ├── segment/            # Universal multilingual sentence segmentation
│       ├── select/             # Submodular entity floor & marginal entropy selection
│       ├── tokenize/           # Tokenizer profile abstraction (tiktoken, etc.)
│       └── validate/           # Invariant validators
└── tests/
    ├── differential/           # Differential test suite vs. baseline models
    ├── property/               # Hypothesis property-based span invariance tests
    └── unit/                   # Unit tests (atoms, budget, rewrite, spans, logs, multilingual, provenance)
```

---

## Testing & Quality Assurance

Run the comprehensive test suite with `pytest`:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=tep --cov-report=term-missing
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
