# ContextCull benchmark

Matched-token-budget comparison. Ground truth = hand-labelled facts pulled from the raw
document (bench/facts/*.json), independent of ContextCull's own parsing. `status`/`regression`
are reported separately - a regression is never mislabelled PASS.

## 01_email_thread.eml

Raw tokens: 21662 | Format-native plain tokens: 7150 | Facts: 18
Sumy baselines analyzed the first 29,612 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 3,534 | 83.7% | 50.6% | 16/18 | 94.44 ms |
| format_native_full | OK | no | 7,150 | 67.0% | 0.0% | 18/18 | 9.71 ms |
| lead_matched | OK | no | 3,534 | 83.7% | 50.6% | 11/18 | 1.54 ms |
| sumy_lexrank_matched | OK | no | 3,532 | 83.7% | 50.6% | 6/18 | 335.96 ms |
| sumy_lsa_matched | OK | no | 3,489 | 83.9% | 51.2% | 11/18 | 150.22 ms |

## 02_novel_chapter.txt

Raw tokens: 34336 | Format-native plain tokens: 34336 | Facts: 20
Sumy baselines analyzed the first 40,000 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 18,737 | 45.4% | 45.4% | 9/20 | 345.02 ms |
| format_native_full | OK | no | 34,336 | 0.0% | 0.0% | 20/20 | 0.04 ms |
| lead_matched | OK | no | 18,737 | 45.4% | 45.4% | 14/20 | 6.86 ms |
| sumy_lexrank_matched | OK | no | 8,392 | 75.6% | 75.6% | 8/20 | 582.98 ms |
| sumy_lsa_matched | OK | no | 8,392 | 75.6% | 75.6% | 8/20 | 228.23 ms |

## 03_slack_chat.txt

Raw tokens: 16213 | Format-native plain tokens: 16213 | Facts: 22
Sumy baselines analyzed the first 40,000 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 11,407 | 29.6% | 29.6% | 17/22 | 134.11 ms |
| format_native_full | OK | no | 16,213 | 0.0% | 0.0% | 22/22 | 0.01 ms |
| lead_matched | OK | no | 11,407 | 29.6% | 29.6% | 9/22 | 3.28 ms |
| sumy_lexrank_matched | OK | no | 11,398 | 29.7% | 29.7% | 15/22 | 348.37 ms |
| sumy_lsa_matched | OK | no | 11,373 | 29.9% | 29.9% | 14/22 | 139.95 ms |

## 04_synthetic_technical_report.docx

Raw tokens: 1169 | Format-native plain tokens: N/A | Facts: N/A (no bench/facts file)
Sumy baselines analyzed the first 3,047 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 237 | 79.7% | N/A | N/A | 4.73 ms |
| lead_matched | OK | no | 237 | 79.7% | N/A | N/A | 0.30 ms |
| sumy_lexrank_matched | OK | no | 227 | 80.6% | N/A | N/A | 0.38 ms |
| sumy_lsa_matched | OK | no | 227 | 80.6% | N/A | N/A | 0.36 ms |

## 05_web_article.html

Raw tokens: 343709 | Format-native plain tokens: 31268 | Facts: 18
Sumy baselines analyzed the first 40,000 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 18,722 | 94.6% | 40.1% | 13/18 | 1683.94 ms |
| format_native_full | OK | no | 31,268 | 90.9% | 0.0% | 18/18 | 57.58 ms |
| lead_matched | OK | no | 18,722 | 94.6% | 40.1% | 18/18 | 6.70 ms |
| sumy_lexrank_matched | OK | no | 9,231 | 97.3% | 70.5% | 18/18 | 2036.11 ms |
| sumy_lsa_matched | OK | no | 9,231 | 97.3% | 70.5% | 18/18 | 533.29 ms |

## 06_academic_paper.pdf

Raw tokens: 1365492 | Format-native plain tokens: 9565 | Facts: 20
Sumy baselines analyzed the first 39,507 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 4,535 | 99.7% | 52.6% | 11/20 | 812.74 ms |
| format_native_full | OK | no | 9,565 | 99.3% | 0.0% | 20/20 | 743.06 ms |
| lead_matched | OK | no | 4,535 | 99.7% | 52.6% | 13/20 | 1.94 ms |
| sumy_lexrank_matched | OK | no | 4,514 | 99.7% | 52.8% | 14/20 | 525.85 ms |
| sumy_lsa_matched | OK | no | 4,527 | 99.7% | 52.7% | 9/20 | 201.86 ms |

## 07_structured_feed.xml

Raw tokens: 131358 | Format-native plain tokens: 131358 | Facts: 15
Sumy baselines analyzed the first 40,000 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 94,559 | 28.0% | 28.0% | 14/15 | 869.16 ms |
| format_native_full | OK | no | 131,358 | 0.0% | 0.0% | 15/15 | 0.10 ms |
| lead_matched | OK | no | 94,559 | 28.0% | 28.0% | 15/15 | 23.94 ms |
| sumy_lexrank_matched | OK | no | 12,450 | 90.5% | 90.5% | 6/15 | 40.44 ms |
| sumy_lsa_matched | OK | no | 12,450 | 90.5% | 90.5% | 6/15 | 17.04 ms |

## 08_cloud_audit.json

Raw tokens: 14661 | Format-native plain tokens: 14661 | Facts: 15
Sumy baselines analyzed the first 40,000 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 12,207 | 16.7% | 16.7% | 15/15 | 69.54 ms |
| format_native_full | OK | no | 14,661 | 0.0% | 0.0% | 15/15 | 0.01 ms |
| lead_matched | OK | no | 12,207 | 16.7% | 16.7% | 15/15 | 3.87 ms |
| sumy_lexrank_matched | OK | no | 6,395 | 56.4% | 56.4% | 15/15 | 1.61 ms |
| sumy_lsa_matched | OK | no | 6,395 | 56.4% | 56.4% | 15/15 | 0.94 ms |

## 09_incident_metrics.csv

Raw tokens: 72396 | Format-native plain tokens: 72396 | Facts: 20
Sumy baselines analyzed the first 40,000 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 72,395 | 0.0% | 0.0% | 20/20 | 581.62 ms |
| format_native_full | OK | no | 72,396 | 0.0% | 0.0% | 20/20 | 0.01 ms |
| lead_matched | OK | no | 72,395 | 0.0% | 0.0% | 20/20 | 14.90 ms |
| sumy_lexrank_matched | OK | no | 24,195 | 66.6% | 66.6% | 7/20 | 0.01 ms |
| sumy_lsa_matched | OK | no | 24,195 | 66.6% | 66.6% | 7/20 | 0.02 ms |

## 10_source_module.py

Raw tokens: 21241 | Format-native plain tokens: 21241 | Facts: 16
Sumy baselines analyzed the first 40,000 chars of the format-native text (SUMY_MAX_CHARS cap, see bench/run_benchmark.py) - ContextCull and the other baselines see the full document.

| Engine | Status | Regression | Output Tok | Reduc vs Raw | Reduc vs Native | Fact Recall | Latency (median x5) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| contextcull | OK | no | 10,295 | 51.5% | 51.5% | 7/16 | 127.74 ms |
| format_native_full | OK | no | 21,241 | 0.0% | 0.0% | 16/16 | 0.01 ms |
| lead_matched | OK | no | 10,295 | 51.5% | 51.5% | 9/16 | 5.01 ms |
| sumy_lexrank_matched | OK | no | 9,242 | 56.5% | 56.5% | 9/16 | 316.62 ms |
| sumy_lsa_matched | OK | no | 9,242 | 56.5% | 56.5% | 9/16 | 118.05 ms |
