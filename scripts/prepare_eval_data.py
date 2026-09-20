"""Script to generate or acquire the 10 diverse evaluation datasets."""

import io
import json
import zipfile
from pathlib import Path
from pypdf import PdfWriter

EVAL_DIR = Path("examples/eval")
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# 1. Long Multi-Turn Email Thread (RFC 822)
email_thread = """From: sarah.chen@acme-infra.internal
To: incident-response@acme-infra.internal, devops-core@acme-infra.internal
Subject: [P0 Incident] S3 Token Leak and Rogue Container in Cluster us-east-prod-1
Date: Mon, 14 Jul 2026 08:15:22 +0000
Message-ID: <inc-001@acme-infra.internal>

Team,
At 08:12 UTC, GuardDuty flagged unauthorized AWS STS AssumeRole calls originating from external IP 198.51.100.44 against role arn:aws:iam::123456789012:role/DataPipelineWorker.
The attacker appears to have harvested AWS secret access keys from a publicly exposed environment variable in staging.
Immediate action items:
1. Revoke active STS sessions for DataPipelineWorker.
2. Isolate pod data-worker-7b9f8-x9z2q in namespace processing.
3. Review CloudTrail logs for S3 PutObject or GetObject calls.

Sarah Chen
Principal Reliability Engineer, Acme Corp

--------------------------------------------------------------------------------
From: marcus.vance@acme-infra.internal
To: sarah.chen@acme-infra.internal, incident-response@acme-infra.internal
Subject: Re: [P0 Incident] S3 Token Leak and Rogue Container in Cluster us-east-prod-1
Date: Mon, 14 Jul 2026 08:24:10 +0000
In-Reply-To: <inc-001@acme-infra.internal>

> 1. Revoke active STS sessions for DataPipelineWorker.
> 2. Isolate pod data-worker-7b9f8-x9z2q in namespace processing.

Confirmed: Active STS session revocation executed at 08:21 UTC via AWS CLI:
`aws iam put-role-policy --role-name DataPipelineWorker --policy-name RevokeOlderSessions --policy-document file://revoke.json`
All credentials issued prior to 2026-07-14T08:20:00Z are now invalidated.

Pod data-worker-7b9f8-x9z2q has been cordoned and network policy applied to deny all ingress/egress.
Memory dump in progress: 731 MB captured to s3://acme-forensics-vault/inc-2026-07-14/mem.raw.

Marcus

--------------------------------------------------------------------------------
From: elena.rostova@acme-infra.internal
To: incident-response@acme-infra.internal
Subject: Re: [P0 Incident] S3 Token Leak and Rogue Container in Cluster us-east-prod-1
Date: Mon, 14 Jul 2026 08:42:33 +0000
In-Reply-To: <inc-001@acme-infra.internal>

Forensics initial findings:
The attacker gained access through CVE-2026-44192 in the legacy PDF generation microservice running on port 8080.
Once inside, they executed a lateral movement script to scrape Kubernetes secrets from `/var/run/secrets/kubernetes.io/serviceaccount/token`.
They attempted to query the internal Vault instance at 10.100.0.15:8200, but Vault rejected the token due to CIDR restriction policy.
However, 14 write tokens for internal Artifactory repository `artifactory-build-cache` were discovered in `/tmp/.cache`.

Actions underway:
- Rotate all Artifactory API keys across Organization 1.
- Patch PDF worker deployment with base image v2.4.1 containing the fix for CVE-2026-44192.
- Enforce mTLS on all internal inter-service communication by 12:00 UTC.

Elena Rostova
Head of Security Operations

--------------------------------------------------------------------------------
From: david.kim@acme-infra.internal
To: incident-response@acme-infra.internal
Subject: Re: [P0 Incident] S3 Token Leak and Rogue Container in Cluster us-east-prod-1
Date: Mon, 14 Jul 2026 09:10:05 +0000

Update on customer impact and blast radius:
- Customer database clusters (Aurora PostgreSQL cluster-id `aurora-prod-analytics-01`) show ZERO unauthorized queries.
- CloudTrail confirms no customer PII was accessed or downloaded.
- Exfiltration was strictly confined to internal build artifacts and caching metadata.
- Total downtime: 0 minutes for external customer APIs.
- Next briefing scheduled for 10:00 UTC with VP Engineering.

David Kim
Director of Infrastructure
"""
(EVAL_DIR / "01_email_thread.eml").write_text(email_thread, encoding="utf-8")

# 3. Slack War-Room / Engineering Chat
chat_transcript = """[2026-07-14 08:00:12] @monitoring-bot: ALERT: CPU usage on host srv-prod-db-04 exceeded 95% for 5 minutes.
[2026-07-14 08:01:05] @alex.t: Looking into srv-prod-db-04. PostgreSQL connection pool is saturated. 450/500 connections active.
[2026-07-14 08:02:30] @maria.g: Seeing elevated 504 Gateway Timeouts on /api/v2/checkout. Latency spiked from 45ms to 3200ms.
[2026-07-14 08:03:15] @alex.t: Found the culprit query: `SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at DESC;` is doing a full table scan on 42M rows.
[2026-07-14 08:04:45] @maria.g: Did someone drop the index `idx_orders_status_created` during last night's migration 20260713_drop_legacy_indexes.sql?
[2026-07-14 08:06:20] @jason.k: Yes, migration 20260713 dropped it by mistake. I am creating the index concurrently right now:
`CREATE INDEX CONCURRENTLY idx_orders_status_created ON orders (status, created_at DESC);`
[2026-07-14 08:12:10] @jason.k: Index creation 60% complete. CPU dropping slightly to 82%.
[2026-07-14 08:15:35] @jason.k: Index created successfully. Query execution time down to 1.2ms.
[2026-07-14 08:16:05] @alex.t: Connection pool drained. Active connections back to 38.
[2026-07-14 08:17:00] @maria.g: 504 errors dropped to 0. Checkout API p99 latency back to 42ms.
[2026-07-14 08:20:00] @alex.t: Closing incident INC-84920. Post-mortem scheduled for tomorrow at 14:00 UTC.
"""
(EVAL_DIR / "03_slack_chat.txt").write_text(chat_transcript, encoding="utf-8")

# 4. Technical Report DOCX (Word OpenXML)
docx_buf = io.BytesIO()
docx_xml = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
            <w:r><w:t>Quarterly Infrastructure Reliability and Security Audit</w:t></w:r>
        </w:p>
        <w:p>
            <w:r><w:t>This report summarizes the operational health, security posture, and infrastructure changes for Q2 2026 across all global regions.</w:t></w:r>
        </w:p>
        <w:p>
            <w:pPr><w:pStyle w:val="Heading2"/></w:pPr>
            <w:r><w:t>Key Metrics and Accomplishments</w:t></w:r>
        </w:p>
        <w:p>
            <w:r><w:t>Overall service availability was maintained at 99.985%, exceeding our quarterly SLA target of 99.95%. Three major security vulnerabilities were remediated: CVE-2026-31184 (critical remote code execution in ingress gateway), CVE-2026-29910 (moderate denial-of-service in cache daemon), and CVE-2026-18823 (credential leakage in test runner).</w:t></w:r>
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
(EVAL_DIR / "04_technical_report.docx").write_bytes(docx_buf.getvalue())

# 5. Web Article HTML
html_article = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Understanding Vector Embeddings and Approximate Nearest Neighbors</title>
    <style>body { font-family: sans-serif; } .nav { display: none; }</style>
    <script>var trackingId = "9e73f6ea-8ae4-4866-b936-bcb2f6ea82f1";</script>
</head>
<body>
    <header><h1>Vector Search and Dense Retrieval in Modern AI</h1></header>
    <article>
        <h2>Introduction</h2>
        <p>Vector embeddings transform high-dimensional unstructured data such as text, images, and audio into dense numerical vectors in a continuous geometric space. In this space, semantic similarity corresponds to geometric proximity, typically calculated using cosine similarity or Euclidean distance.</p>
        <h2>Indexing Algorithms: HNSW vs IVF</h2>
        <p>Hierarchical Navigable Small World (HNSW) graphs construct a multi-layer graph where upper layers contain long-range edges for rapid coarse navigation, and lower layers provide dense clustering for high precision. In benchmarks, HNSW achieves 98.5% recall at 12,000 queries per second (QPS).</p>
        <p>Inverted File Index (IVF) partitions the vector space into Voronoi cells using k-means clustering. During query execution, only vectors belonging to the nearest centroids are scanned. While IVF uses significantly less memory than HNSW, it requires periodic index re-training when data distribution drifts.</p>
        <h2>Production Considerations</h2>
        <p>When deploying vector databases in production environments with over 100 million embeddings, memory efficiency is critical. Scalar quantization (SQ8) reduces 32-bit floating point vectors to 8-bit integers, yielding a 4x reduction in RAM usage with less than 1.5% drop in recall.</p>
    </article>
</body>
</html>"""
(EVAL_DIR / "05_web_article.html").write_text(html_article, encoding="utf-8")

# 6. Academic Paper PDF
pdf_writer = PdfWriter()
pdf_writer.add_blank_page(width=612, height=792)
pdf_buf = io.BytesIO()
pdf_writer.write(pdf_buf)
(EVAL_DIR / "06_academic_paper.pdf").write_bytes(pdf_buf.getvalue())

# 7. Structured XML Feed
xml_feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Acme Security Advisories</title>
    <updated>2026-07-14T12:00:00Z</updated>
    <entry>
        <id>urn:uuid:6c9b3a11-89e4-42b7-a38f-998822001122</id>
        <title>Advisory ACME-2026-08: Remote Code Execution in API Gateway</title>
        <updated>2026-07-14T10:15:00Z</updated>
        <summary>A critical vulnerability CVE-2026-88192 was identified in the API Gateway authentication filter. Attackers could bypass token verification by sending crafted HTTP headers.</summary>
        <author><name>Security Response Team</name></author>
    </entry>
    <entry>
        <id>urn:uuid:7d1c4b22-90f5-53c8-b49a-001133112233</id>
        <title>Advisory ACME-2026-09: Denial of Service in Session Store</title>
        <updated>2026-07-13T16:30:00Z</updated>
        <summary>Vulnerability CVE-2026-77180 allows unauthenticated attackers to cause memory exhaustion in Redis cluster nodes by transmitting malformed WebSocket frames.</summary>
        <author><name>Platform Engineering</name></author>
    </entry>
</feed>"""
(EVAL_DIR / "07_structured_feed.xml").write_text(xml_feed, encoding="utf-8")

# 8. Cloud Audit JSON Log
json_audit = {
    "eventVersion": "1.08",
    "userIdentity": {
        "type": "IAMUser",
        "principalId": "AIDAJQABLZS4A3QEXAMPLE",
        "arn": "arn:aws:iam::123456789012:user/deployer-bot",
        "accountId": "123456789012",
        "userName": "deployer-bot",
    },
    "eventTime": "2026-07-14T08:12:00Z",
    "eventSource": "ec2.amazonaws.com",
    "eventName": "RunInstances",
    "awsRegion": "us-east-1",
    "sourceIPAddress": "198.51.100.44",
    "userAgent": "aws-sdk-go/v1.44.0",
    "requestParameters": {
        "instanceType": "c6i.4xlarge",
        "imageId": "ami-0c55b159cbfafe1f0",
        "minCount": 4,
        "maxCount": 4,
        "securityGroupId": ["sg-01a2b3c4d5e6f7890"],
    },
    "responseElements": {
        "instancesSet": {
            "items": [
                {"instanceId": "i-0622056ec3e996a7c", "currentState": {"name": "running"}},
                {"instanceId": "i-0733167fd4e007b8d", "currentState": {"name": "running"}},
            ]
        }
    },
}
(EVAL_DIR / "08_cloud_audit.json").write_text(json.dumps(json_audit, indent=2), encoding="utf-8")

# 9. Incident Metrics CSV
csv_lines = [
    "timestamp,host,cpu_percent,memory_mb,latency_ms,status_code,error_type",
    "2026-07-14T08:00:00Z,srv-01.us-east.acme,42.5,4096,18,200,None",
    "2026-07-14T08:01:00Z,srv-01.us-east.acme,78.2,6144,45,200,None",
    "2026-07-14T08:02:00Z,srv-01.us-east.acme,96.8,7980,1250,504,GatewayTimeout",
    "2026-07-14T08:03:00Z,srv-01.us-east.acme,99.1,8192,3400,504,GatewayTimeout",
    "2026-07-14T08:04:00Z,srv-02.us-east.acme,94.3,8100,2900,504,ConnectionPoolExhausted",
    "2026-07-14T08:05:00Z,srv-02.us-east.acme,98.7,8192,4100,500,InternalServerError",
    "2026-07-14T08:06:00Z,srv-03.us-east.acme,35.0,3800,22,200,None",
    "2026-07-14T08:15:00Z,srv-01.us-east.acme,38.4,4100,21,200,None",
]
(EVAL_DIR / "09_incident_metrics.csv").write_text("\n".join(csv_lines), encoding="utf-8")

# 10. Complex Source Code Module
(EVAL_DIR / "10_source_module.py").write_text(
    Path("src/tep/select/budget.py").read_text(encoding="utf-8"), encoding="utf-8"
)

print("All 10 evaluation datasets prepared successfully in examples/eval/!")
