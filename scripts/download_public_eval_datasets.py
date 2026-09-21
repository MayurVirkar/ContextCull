"""Download authentic open-source public datasets for ContextCull evaluation."""

from __future__ import annotations

import io
import json
import tarfile
import urllib.request
import zipfile
from pathlib import Path

EVAL_DIR = Path("examples/eval")
EVAL_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ContextCull/1.0"}


def fetch_url(url: str, timeout: int = 20) -> bytes:
    """Fetch content from a URL with custom User-Agent."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def main():
    print("Downloading authentic open-source public datasets into examples/eval/...")

    # 1. Real RFC 822 Email Thread (Apache SpamAssassin developer mailing list corpus)
    print("[1/10] Downloading real RFC 822 email thread (Apache SpamAssassin Corpus)...")
    try:
        ham_archive = fetch_url(
            "https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham.tar.bz2",
            timeout=30,
        )
        emails = []
        with tarfile.open(fileobj=io.BytesIO(ham_archive), mode="r:bz2") as tar:
            count = 0
            for m in tar.getmembers():
                if m.isfile() and count < 15:
                    content = tar.extractfile(m).read().decode("utf-8", errors="replace")
                    emails.append(content)
                    count += 1
        combined_thread = "\n\n--------------------------------------------------------------------------------\n\n".join(
            emails
        )
        (EVAL_DIR / "01_email_thread.eml").write_text(combined_thread, encoding="utf-8")
        print(f"  ✓ 01_email_thread.eml: {len(combined_thread.encode('utf-8'))} bytes")
    except Exception as e:
        print(f"  ✗ 01_email_thread.eml failed: {e}")

    # 2. Literature: Project Gutenberg (Mary Shelley's Frankenstein)
    print("[2/10] Downloading literature (Project Gutenberg: Frankenstein)...")
    try:
        novel_bytes = fetch_url("https://www.gutenberg.org/cache/epub/84/pg84.txt")
        # Truncate to ~150 KB at a paragraph boundary (Letters through Chapter 4),
        # never mid-word: cut back to the last blank-line break before the limit.
        full_text = novel_bytes.decode("utf-8", errors="replace")
        head = full_text[:150_000]
        boundary = head.rfind("\n\n")
        if boundary <= 0:
            boundary = head.rfind("\n")
        novel_text = head[:boundary].rstrip() + "\n" if boundary > 0 else head
        (EVAL_DIR / "02_novel_chapter.txt").write_text(novel_text, encoding="utf-8")
        print(
            f"  ✓ 02_novel_chapter.txt: {len(novel_text.encode('utf-8'))} bytes (truncated at paragraph boundary)"
        )
    except Exception as e:
        print(f"  ✗ 02_novel_chapter.txt failed: {e}")

    # 3. Chat Transcript: Ubuntu Community IRC Logs
    print("[3/10] Downloading chat transcript (Ubuntu Community IRC Logs)...")
    try:
        log1 = fetch_url("https://irclogs.ubuntu.com/2024/01/15/%23ubuntu.txt").decode(
            "utf-8", errors="replace"
        )
        log2 = fetch_url("https://irclogs.ubuntu.com/2024/01/16/%23ubuntu.txt").decode(
            "utf-8", errors="replace"
        )
        chat_text = log1 + "\n" + log2
        (EVAL_DIR / "03_slack_chat.txt").write_text(chat_text, encoding="utf-8")
        print(f"  ✓ 03_slack_chat.txt: {len(chat_text.encode('utf-8'))} bytes")
    except Exception as e:
        print(f"  ✗ 03_slack_chat.txt failed: {e}")

    # 4. Technical Report: SYNTHETIC OpenXML DOCX Document.
    # This is generated (not a real-world download): the CVE IDs, cluster IDs and
    # metrics below are invented for eval purposes only. Filename is prefixed
    # "synthetic" so it isn't mistaken for authentic public data.
    print("[4/10] Generating SYNTHETIC technical report DOCX (OpenXML)...")
    try:
        docx_buf = io.BytesIO()
        docx_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
            <w:r><w:t>Quarterly Infrastructure Reliability and Security Audit</w:t></w:r>
        </w:p>
        <w:p>
            <w:r><w:t>This report summarizes operational health, security posture, and infrastructure changes across all global regions.</w:t></w:r>
        </w:p>
        <w:p>
            <w:pPr><w:pStyle w:val="Heading2"/></w:pPr>
            <w:r><w:t>Key Metrics and Accomplishments</w:t></w:r>
        </w:p>
        <w:p>
            <w:r><w:t>Overall service availability was maintained at 99.985%, exceeding the quarterly SLA target of 99.95%. Three major security vulnerabilities were remediated: CVE-2026-31184 (critical remote code execution in ingress gateway), CVE-2026-29910 (denial-of-service in cache daemon), and CVE-2026-18823 (credential leakage in test runner).</w:t></w:r>
        </w:p>
        <w:p>
            <w:pPr><w:pStyle w:val="Heading2"/></w:pPr>
            <w:r><w:t>Regional Cluster Availability</w:t></w:r>
        </w:p>
        <w:tbl>
            <w:tr>
                <w:tc><w:p><w:r><w:t>Region</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>Cluster ID</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>Uptime</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>P99 Latency</w:t></w:r></w:p></w:tc>
            </w:tr>
            <w:tr>
                <w:tc><w:p><w:r><w:t>us-east-1</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>k8s-prod-useast1-01</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>99.992%</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>38 ms</w:t></w:r></w:p></w:tc>
            </w:tr>
            <w:tr>
                <w:tc><w:p><w:r><w:t>eu-west-1</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>k8s-prod-euwest1-01</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>99.978%</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>44 ms</w:t></w:r></w:p></w:tc>
            </w:tr>
            <w:tr>
                <w:tc><w:p><w:r><w:t>ap-southeast-1</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>k8s-prod-apse1-01</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>99.989%</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>52 ms</w:t></w:r></w:p></w:tc>
            </w:tr>
        </w:tbl>
        <w:p>
            <w:r><w:t>Next quarter priorities include completing the migration to Kubernetes 1.31 and rolling out automated canary deployments across all tier-1 services.</w:t></w:r>
        </w:p>
    </w:body>
</w:document>"""
        with zipfile.ZipFile(docx_buf, "w") as z:
            z.writestr("word/document.xml", docx_xml)
            z.writestr("[Content_Types].xml", b"<Types/>")
        (EVAL_DIR / "04_synthetic_technical_report.docx").write_bytes(docx_buf.getvalue())
        print(f"  ✓ 04_synthetic_technical_report.docx: {len(docx_buf.getvalue())} bytes")
    except Exception as e:
        print(f"  ✗ 04_synthetic_technical_report.docx failed: {e}")

    # 5. Web Article: Wikipedia (Transformer Architecture)
    print("[5/10] Downloading web article (Wikipedia: Transformer)...")
    try:
        html_bytes = fetch_url(
            "https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)"
        )
        (EVAL_DIR / "05_web_article.html").write_bytes(html_bytes)
        print(f"  ✓ 05_web_article.html: {len(html_bytes)} bytes")
    except Exception as e:
        print(f"  ✗ 05_web_article.html failed: {e}")

    # 6. Academic Paper: arXiv (Attention Is All You Need)
    print("[6/10] Downloading academic paper (arXiv: 1706.03762)...")
    try:
        pdf_bytes = fetch_url("https://arxiv.org/pdf/1706.03762.pdf")
        (EVAL_DIR / "06_academic_paper.pdf").write_bytes(pdf_bytes)
        print(f"  ✓ 06_academic_paper.pdf: {len(pdf_bytes)} bytes")
    except Exception as e:
        print(f"  ✗ 06_academic_paper.pdf failed: {e}")

    # 7. Security Feed: CISA Cybersecurity Advisories XML Feed
    print("[7/10] Downloading structured feed (CISA Advisories XML)...")
    try:
        xml_bytes = fetch_url("https://www.cisa.gov/cybersecurity-advisories/all.xml")
        (EVAL_DIR / "07_structured_feed.xml").write_bytes(xml_bytes)
        print(f"  ✓ 07_structured_feed.xml: {len(xml_bytes)} bytes")
    except Exception as e:
        print(f"  ✗ 07_structured_feed.xml failed: {e}")

    # 8. Cloud & Security Audit: CVEProject Official JSON Record
    print("[8/10] Downloading security audit record (CVEProject JSON)...")
    try:
        cve_bytes = fetch_url(
            "https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/2024/21xxx/CVE-2024-21626.json"
        )
        # Verify valid JSON
        json.loads(cve_bytes)
        (EVAL_DIR / "08_cloud_audit.json").write_bytes(cve_bytes)
        print(f"  ✓ 08_cloud_audit.json: {len(cve_bytes)} bytes")
    except Exception as e:
        print(f"  ✗ 08_cloud_audit.json failed: {e}")

    # 9. Incident Metrics: Numenta Anomaly Benchmark (NAB) AWS CloudWatch Telemetry CSV
    print("[9/10] Downloading incident metrics (Numenta Anomaly Benchmark AWS Telemetry CSV)...")
    try:
        csv_bytes = fetch_url(
            "https://raw.githubusercontent.com/numenta/NAB/master/data/realAWSCloudwatch/ec2_cpu_utilization_5f5533.csv"
        )
        (EVAL_DIR / "09_incident_metrics.csv").write_bytes(csv_bytes)
        print(f"  ✓ 09_incident_metrics.csv: {len(csv_bytes)} bytes")
    except Exception as e:
        print(f"  ✗ 09_incident_metrics.csv failed: {e}")

    # 10. Source Code: CPython difflib Module
    print("[10/10] Downloading source module (CPython difflib.py)...")
    try:
        py_bytes = fetch_url("https://raw.githubusercontent.com/python/cpython/main/Lib/difflib.py")
        (EVAL_DIR / "10_source_module.py").write_bytes(py_bytes)
        print(f"  ✓ 10_source_module.py: {len(py_bytes)} bytes")
    except Exception as e:
        print(f"  ✗ 10_source_module.py failed: {e}")

    print("\nAll 10 authentic open-source evaluation datasets downloaded successfully!")


if __name__ == "__main__":
    main()
