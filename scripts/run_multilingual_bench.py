"""Run ContextCull compilation benchmark across all multilingual public-domain corpora."""

import json
import time
from pathlib import Path

from contextcull import CompileMode, CompilePolicy, ContextCompiler
from contextcull.tokenize.profile import get_tokenizer

EVAL_DIR = Path("examples/eval/multilingual")
METADATA_FILE = EVAL_DIR / "METADATA.json"
OUTPUT_DIR = Path("scratch/multilingual_eval")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_multilingual_bench():
    with open(METADATA_FILE, encoding="utf-8") as f:
        meta = json.load(f)

    datasets = meta.get("datasets", [])
    tokenizer = get_tokenizer("openai:cl100k_base")
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    results = []

    print("=" * 90)
    print(
        f"{'#':<3} | {'Lang':<5} | {'Work / Author':<38} | {'Raw Tok':<8} | {'TEP Tok':<8} | {'Reduc %':<8} | {'Latency':<8} | {'Status'}"
    )
    print("-" * 90)

    for idx, item in enumerate(datasets, 1):
        filename = item["file"]
        lang = item["language"].upper()
        title = item["title"]
        file_path = EVAL_DIR / filename

        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        t0 = time.perf_counter()
        res = compiler.compile(raw_bytes, policy=policy)
        t1 = time.perf_counter()

        raw_tokens = res.metrics.get("input_tokens", 0)
        if not raw_tokens:
            raw_tokens = tokenizer.count_tokens(raw_bytes.decode("utf-8", errors="replace"))

        latency_ms = (t1 - t0) * 1000.0
        tep_tokens = tokenizer.count_tokens(res.text) if res.text else 0
        reduction_pct = (1.0 - (tep_tokens / raw_tokens)) * 100.0 if raw_tokens > 0 else 0.0

        label = f"{title[:35]}"
        print(
            f"{idx:<3} | {lang:<5} | {label:<38} | {raw_tokens:<8} | {tep_tokens:<8} | {reduction_pct:>6.1f}% | {latency_ms:>7.0f}ms | {res.status}"
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
                "latency_ms": round(latency_ms, 1),
                "status": res.status,
            }
        )

    print("=" * 90)

    with open(OUTPUT_DIR / "multilingual_results.json", "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2)


if __name__ == "__main__":
    run_multilingual_bench()
