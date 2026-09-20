"""Reproducible empirical benchmark comparing TEP v2 against Sumy (LexRank and LSA)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import tiktoken

from tep.api import ContextCompiler
from tep.ir.models import CompileMode, CompilePolicy


def run_benchmark(file_path: Path) -> None:
    if not file_path.exists():
        print(f"Error: file {file_path} does not exist", file=sys.stderr)
        sys.exit(1)

    raw_bytes = file_path.read_bytes()
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    enc = tiktoken.get_encoding("cl100k_base")
    raw_tokens = len(enc.encode(raw_text))

    print(f"Benchmark Document: {file_path}")
    print(f"Raw Size: {len(raw_bytes)} bytes | {raw_tokens} tokens (cl100k_base)\n")

    # 19 Ground-truth benchmark atoms from whitepaper
    ground_truth_atoms = [
        "CVE-2026-66384",
        "CVE-2026-53362",
        "i-0622056ec3e996a7c",
        "artifactory-3",
        "956 secrets",
        "moon-bot",
        "moon-landing",
        "xetcas",
        "14 write tokens",
        "16 MB",
        "731 MB",
        "RefJinja",
        "HDF5",
        "JRuby",
        "karchive7dee-admin",
        "minizfe78",
        "Organization 1",
        "30 min",
        "2026-07-11",
    ]

    results = []

    # 1. TEP v2 Deterministic Zero-Budget Compiler
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    policy = CompilePolicy(mode=CompileMode.COMPACT, discourse_pruning=True)

    # Warmup
    _ = compiler.compile(raw_bytes, policy=policy)

    t0 = time.perf_counter()
    tep_res = compiler.compile(raw_bytes, policy=policy)
    t1 = time.perf_counter()
    tep_latency = (t1 - t0) * 1000.0

    tep_tokens = len(enc.encode(tep_res.text))
    tep_reduction = (1.0 - (tep_tokens / raw_tokens)) * 100.0
    tep_retained = [a for a in ground_truth_atoms if a in tep_res.text]
    tep_dropped = [a for a in ground_truth_atoms if a not in tep_res.text]

    results.append(
        {
            "engine": "TEP v2 (Zero-Budget, Generic)",
            "latency_ms": tep_latency,
            "output_tokens": tep_tokens,
            "reduction_pct": tep_reduction,
            "retained_count": len(tep_retained),
            "total_count": len(ground_truth_atoms),
            "dropped": tep_dropped,
        }
    )

    # 2. Sumy LexRank & LSA (if sumy is installed)
    try:
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.summarizers.lex_rank import LexRankSummarizer
        from sumy.summarizers.lsa import LsaSummarizer

        parser = PlaintextParser.from_string(raw_text, Tokenizer("english"))

        for count in (100, 50):
            # LexRank
            lex = LexRankSummarizer()
            t0 = time.perf_counter()
            lex_sentences = lex(parser.document, count)
            t1 = time.perf_counter()
            lex_latency = (t1 - t0) * 1000.0
            lex_text = "\n".join(str(s) for s in lex_sentences)
            lex_tokens = len(enc.encode(lex_text))
            lex_reduction = (1.0 - (lex_tokens / raw_tokens)) * 100.0
            lex_retained = [a for a in ground_truth_atoms if a in lex_text]
            lex_dropped = [a for a in ground_truth_atoms if a not in lex_text]

            results.append(
                {
                    "engine": f"Sumy LexRank ({count} sent)",
                    "latency_ms": lex_latency,
                    "output_tokens": lex_tokens,
                    "reduction_pct": lex_reduction,
                    "retained_count": len(lex_retained),
                    "total_count": len(ground_truth_atoms),
                    "dropped": lex_dropped,
                }
            )

            # LSA
            lsa = LsaSummarizer()
            t0 = time.perf_counter()
            lsa_sentences = lsa(parser.document, count)
            t1 = time.perf_counter()
            lsa_latency = (t1 - t0) * 1000.0
            lsa_text = "\n".join(str(s) for s in lsa_sentences)
            lsa_tokens = len(enc.encode(lsa_text))
            lsa_reduction = (1.0 - (lsa_tokens / raw_tokens)) * 100.0
            lsa_retained = [a for a in ground_truth_atoms if a in lsa_text]
            lsa_dropped = [a for a in ground_truth_atoms if a not in lsa_text]

            results.append(
                {
                    "engine": f"Sumy LSA ({count} sent)",
                    "latency_ms": lsa_latency,
                    "output_tokens": lsa_tokens,
                    "reduction_pct": lsa_reduction,
                    "retained_count": len(lsa_retained),
                    "total_count": len(ground_truth_atoms),
                    "dropped": lsa_dropped,
                }
            )

    except ImportError:
        print("Note: sumy and nltk not installed; skipping classic summarizer comparison.")

    # Print Table
    print(
        "| Summarizer Engine | Latency | Output Tokens | Token Reduction | Atoms Retained (19 Ground Truth) | Atoms Dropped |"
    )
    print("| :--- | :---: | :---: | :---: | :---: | :--- |")
    for r in results:
        dropped_str = ", ".join(f"`{d}`" for d in r["dropped"][:4])
        if len(r["dropped"]) > 4:
            dropped_str += f", ... ({len(r['dropped'])} total)"
        elif not r["dropped"]:
            dropped_str = "None (100% retained)"

        print(
            f"| **{r['engine']}** | {r['latency_ms']:.0f} ms | {r['output_tokens']:,} | "
            f"{r['reduction_pct']:.1f}% | **{r['retained_count']} / {r['total_count']} ({r['retained_count'] / r['total_count'] * 100:.1f}%)** | "
            f"{dropped_str} |"
        )


if __name__ == "__main__":
    target = Path("examples/sample_incident.txt")
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    run_benchmark(target)
