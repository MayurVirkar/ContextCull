"""Run ContextCull compilation benchmark across all multilingual public-domain corpora.

Reports compiler `status` and a `regression` flag (output tokens > input tokens)
separately - never collapsed into a single misleading "PASS". Latency is the
median of 5 runs after a warmup run.
"""

import json
import statistics
import time
from pathlib import Path

from contextcull import CompileMode, CompilePolicy, ContextCompiler
from contextcull.tokenize.profile import get_tokenizer

EVAL_DIR = Path("examples/eval/multilingual")
METADATA_FILE = EVAL_DIR / "METADATA.json"
OUTPUT_DIR = Path("scratch/multilingual_eval")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WARMUP_RUNS = 1
TIMED_RUNS = 5


def run_multilingual_bench():
    with open(METADATA_FILE, encoding="utf-8") as f:
        meta = json.load(f)

    datasets = meta.get("datasets", [])
    tokenizer = get_tokenizer("openai:cl100k_base")
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    results = []

    print("=" * 104)
    print(
        f"{'#':<3} | {'Lang':<5} | {'Work / Author':<38} | {'Raw Tok':<8} | {'TEP Tok':<8} | "
        f"{'Reduc %':<8} | {'Latency':<10} | {'Status':<8} | {'Regression'}"
    )
    print("-" * 104)

    for idx, item in enumerate(datasets, 1):
        filename = item["file"]
        lang = item["language"].upper()
        title = item["title"]
        file_path = EVAL_DIR / filename

        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        res = None
        for _ in range(WARMUP_RUNS):
            res = compiler.compile(raw_bytes, policy=policy)

        latencies_ms = []
        for _ in range(TIMED_RUNS):
            t0 = time.perf_counter()
            res = compiler.compile(raw_bytes, policy=policy)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)
        latency_ms = statistics.median(latencies_ms)

        raw_tokens = res.metrics.get("input_tokens", 0)
        if not raw_tokens:
            raw_tokens = tokenizer.count_tokens(raw_bytes.decode("utf-8", errors="replace"))

        tep_tokens = tokenizer.count_tokens(res.text) if res.text else 0
        reduction_pct = (1.0 - (tep_tokens / raw_tokens)) * 100.0 if raw_tokens > 0 else 0.0
        regression = tep_tokens > raw_tokens

        label = f"{title[:35]}"
        print(
            f"{idx:<3} | {lang:<5} | {label:<38} | {raw_tokens:<8} | {tep_tokens:<8} | "
            f"{reduction_pct:>6.1f}% | {latency_ms:>7.2f}ms | {res.status:<8} | "
            f"{'REGRESSION' if regression else 'ok'}"
        )

        results.append(
            {
                "index": idx,
                "language": lang,
                "title": title,
                "author": item.get("author", ""),
                "filename": filename,
                "raw_tokens": raw_tokens,
                "compiled_tokens": tep_tokens,
                "reduction_pct": round(reduction_pct, 1),
                "latency_ms_median_of_5": round(latency_ms, 2),
                "status": res.status,
                "regression": regression,
            }
        )

    print("=" * 104)

    with open(OUTPUT_DIR / "multilingual_results.json", "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2)


if __name__ == "__main__":
    run_multilingual_bench()
