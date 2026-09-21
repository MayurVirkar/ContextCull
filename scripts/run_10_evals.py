"""Run ContextCull compilation benchmark across all 10 evaluation datasets."""

import json
import time
from pathlib import Path

from contextcull import CompileMode, CompilePolicy, ContextCompiler
from contextcull.tokenize.profile import get_tokenizer

EVAL_DIR = Path("examples/eval")
OUTPUT_DIR = Path("scratch/eval")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATASETS = [
    ("01_email_thread.eml", "Email Thread (RFC 822)"),
    ("02_novel_chapter.txt", "Novel Chapter (Literature)"),
    ("03_slack_chat.txt", "Slack Chat Transcript"),
    ("04_technical_report.docx", "Technical Report (DOCX)"),
    ("05_web_article.html", "Web Article (HTML DOM)"),
    ("06_academic_paper.pdf", "Academic Paper (PDF)"),
    ("07_structured_feed.xml", "Security Feed (XML RSS)"),
    ("08_cloud_audit.json", "Audit Log (JSON)"),
    ("09_incident_metrics.csv", "Metrics Log (CSV)"),
    ("10_source_module.py", "Source Code (Python AST)"),
]


def run_evals():
    tokenizer = get_tokenizer("openai:cl100k_base")
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    policy = CompilePolicy(mode=CompileMode.COMPACT)

    results = []

    print("=" * 80)
    print(
        f"{'#':<3} | {'Dataset':<28} | {'Raw Tok':<8} | {'TEP Tok':<8} | {'Reduc %':<8} | {'Latency':<8} | {'Status'}"
    )
    print("-" * 80)

    for idx, (filename, label) in enumerate(DATASETS, 1):
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

        atoms_total = len(res.manifest.get("source", {}).get("atoms", []))

        # Save compiled output for subagent examination
        out_path = OUTPUT_DIR / f"{Path(filename).stem}_tep.txt"
        with open(out_path, "w", encoding="utf-8") as out_f:
            out_f.write(res.text)

        eval_record = {
            "index": idx,
            "filename": filename,
            "label": label,
            "status": res.status,
            "raw_tokens": raw_tokens,
            "tep_tokens": tep_tokens,
            "reduction_pct": round(reduction_pct, 1),
            "latency_ms": round(latency_ms, 1),
            "atoms_count": atoms_total,
            "output_path": str(out_path),
            "diagnostics": res.diagnostics,
        }
        results.append(eval_record)

        print(
            f"{idx:<3} | {label:<28} | {raw_tokens:<8} | {tep_tokens:<8} | {reduction_pct:>6.1f}% | {latency_ms:>6.1f}ms | {res.status}"
        )

    print("=" * 80)

    with open(OUTPUT_DIR / "eval_results.json", "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2)


if __name__ == "__main__":
    run_evals()
