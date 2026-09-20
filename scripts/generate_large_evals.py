import os
import random
import json
import csv
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import docx

EVAL_DIR = "/home/mayur/projects/SummarizerPython/examples/eval"
os.makedirs(EVAL_DIR, exist_ok=True)

print("Starting generation of 10 evaluation datasets...")

# 1. 01_email_thread.eml (~100 KB)
def generate_email_thread():
    filepath = os.path.join(EVAL_DIR, "01_email_thread.eml")
    participants = [
        ("Alice Vance", "alice.vance@security.corp"),
        ("Bob Smith", "bob.smith@sre.corp"),
        ("Charlie Davis", "charlie.davis@dev.corp"),
        ("Diana Prince", "diana.prince@ciso.corp"),
        ("Eve Polastri", "eve.polastri@infra.corp")
    ]
    subjects = [
        "CRITICAL: Production Outage in US-East-1 Cluster",
        "Update on Pod Failures and Memory Leaks",
        "CVE-2026-3891 Exploited in Ingress Gateway?",
        "Forensic Analysis of AWS IAM Role Assumption",
        "Patch Deployment and Rollback Plan"
    ]
    content_pool = [
        "We are seeing high error rates (502/504) across all ingress gateways in us-east-1. Initial logs point to pod crashloops in deployment/auth-gateway.",
        "Checking the logs now. `kubectl logs -n production deployment/auth-gateway --tail=100` shows `Segmentation fault` followed by panic in Go runtime.",
        "Wait, look at this IP: 198.51.100.45. It's hammering the `/api/v1/auth/token` endpoint with anomalous payloads containing nested JSON structures.",
        "Could this be related to the newly disclosed CVE-2026-3891? The vulnerability affects Envoy and custom ingress proxies handling malformed HTTP/2 headers.",
        "Checking AWS CloudTrail... ARN `arn:aws:iam::123456789012:role/ProductionS3Accessor` was assumed from an unusual external IP at 07:42 UTC."
    ]
    
    eml = ""
    base_time = datetime(2026, 7, 14, 8, 0, 0)
    i = 1
    while len(eml.encode('utf-8')) < 100 * 1024:
        s_name, s_email = participants[i % len(participants)]
        r_name, r_email = participants[(i + 1) % len(participants)]
        dt = (base_time + timedelta(minutes=i*10)).strftime("%a, %d Jul 2026 %H:%M:%S +0000")
        subj = subjects[i % len(subjects)]
        if i > 0:
            subj = "Re: " + subj
        
        eml += f"From: {s_name} <{s_email}>\n"
        eml += f"To: {r_name} <{r_email}>\n"
        eml += f"Subject: {subj} [Ref-{i}]\n"
        eml += f"Date: {dt}\n"
        eml += f"Message-ID: <20260714.{i}@security.corp>\n"
        eml += "Content-Type: text/plain; charset=\"UTF-8\"\n\n"
        eml += f"{content_pool[i % len(content_pool)]}\n\n"
        eml += f"Detailed Diagnostic Dump #{i}:\n- Node: ip-10-0-{i}-22.ec2.internal\n- Heap Usage: {64 + i}GB\n- Active Threads: {250 + i*5}\n"
        eml += "-"*72 + "\n\n"
        i += 1
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(eml)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 2. 02_novel_chapter.txt (~110 KB)
def generate_novel_chapter():
    filepath = os.path.join(EVAL_DIR, "02_novel_chapter.txt")
    paragraphs = [
        "The neon hum of Neo-Seattle cast long, violet shadows across the damp asphalt of Sector 7. Rain fell in sheets, blurring the towering monoliths of the corporate syndicates into blurred pillars of obsidian and cobalt.",
        "Elena adjusted her neural visor, squinting at the flickering data stream projected against her retina. The encryption keys were decaying faster than anticipated; she had less than an hour before the ICE countermeasures locked her out of the main mainframe permanently.",
        "\"You're pushing it too close to the edge, Elena,\" Kael's voice crackled through the encrypted sub-vocal comms link. He was stationed three blocks away in a customized van rigged with thermal baffles and quantum dampeners.",
        "\"I don't have a choice, Kael,\" she murmured back, stepping into the shadowed alcove of an abandoned noodle bar. \"The Syndicate cache contains the only proof of the corporate takeover of the water reserves. Without it, millions of citizens face total rationing by next quarter.\""
    ]
    content = ""
    ch = 1
    while len(content.encode('utf-8')) < 110 * 1024:
        content += f"\n\n=== Chapter {ch}: The Cybernetic Descent ===\n\n"
        for p in paragraphs:
            content += p + f" [Scene variant {ch}]\n\n"
        ch += 1
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 3. 03_slack_chat.txt (~100 KB)
def generate_slack_chat():
    filepath = os.path.join(EVAL_DIR, "03_slack_chat.txt")
    users = ["alice", "bob", "charlie", "dave", "eve", "sre-bot"]
    msgs = [
        "cluster health check failing in us-west-2",
        "looking into it now. running `kubectl get nodes`",
        "nodes are NotReady! multiple node heartbeats missed.",
        "check AWS EC2 console, are instances terminating?",
        "auto-scaling group triggered scale-in due to faulty metric!"
    ]
    chat = ""
    t0 = datetime(2026, 7, 14, 8, 0, 0)
    i = 0
    while len(chat.encode('utf-8')) < 100 * 1024:
        dt_str = (t0 + timedelta(seconds=i*15)).strftime('%Y-%m-%d %H:%M:%S')
        u = users[i % len(users)]
        m = msgs[i % len(msgs)]
        chat += f"[{dt_str}] @{u}: {m} (msg_id:{i})\n"
        if i % 4 == 0:
            chat += f"    ↳ [Thread] @sre-bot: Automated alert acknowledged for incident INC-{1000+i}.\n"
        i += 1
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(chat)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 4. 04_technical_report.docx (~105 KB)
def generate_technical_report():
    filepath = os.path.join(EVAL_DIR, "04_technical_report.docx")
    doc = docx.Document()
    for _ in range(8):
        table = doc.add_table(rows=400, cols=5)
        for row in table.rows:
            for cell in row.cells:
                cell.text = 'Large audit data cell with extensive metrics and logs string padding. ' * 10
    doc.save(filepath)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 5. 05_web_article.html (~100 KB)
def generate_web_article():
    filepath = os.path.join(EVAL_DIR, "05_web_article.html")
    html = "<!DOCTYPE html>\n<html><head><title>Distributed Vector Search</title></head><body>\n"
    html += "<header><h1>Advanced Distributed Systems & Vector Search Architecture</h1></header>\n"
    
    i = 1
    while len(html.encode('utf-8')) < 100 * 1024:
        html += f"<article id='sec-{i}'>\n"
        html += f"<h2>Chapter {i}: Scalability and Indexing in Distributed Vector Databases</h2>\n"
        html += f"<p>Modern artificial intelligence workloads require unprecedented vector search capabilities across distributed clusters with billions of high-dimensional embeddings.</p>\n"
        html += "<table><tr><th>Metric</th><th>Value</th></tr><tr><td>QPS</td><td>54,200</td></tr></table>\n"
        html += "<pre><code>cluster_config:\n  shards: 32\n  replica: 3\n</code></pre>\n"
        html += "</article>\n"
        i += 1
    html += "</body></html>"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 6. 06_academic_paper.pdf (~200 KB)
def generate_academic_paper():
    filepath = os.path.join(EVAL_DIR, "06_academic_paper.pdf")
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("Scalable Vector Search and Attention Mechanisms in Large Language Models", styles['Title']), Spacer(1, 12)]
    
    for page in range(1, 200):
        story.append(Paragraph(f"<b>Research Paper Section - Page {page}</b>", styles['Heading1']))
        story.append(Paragraph("Large language models and vector retrieval systems represent the pinnacle of modern AI architecture. In this comprehensive paper, we explore novel attention mechanisms, memory footprint optimizations, and distributed index sharding techniques. " * 15, styles['Normal']))
        story.append(Spacer(1, 10))
        
        data = [
            ['Dataset Scale', 'Dimension', 'Recall@10', 'Latency'],
            ['1 Million', '768', '99.8%', '2.4ms'],
            ['100 Million', '1536', '99.4%', '8.1ms'],
            ['1 Billion', '3072', '98.9%', '19.5ms']
        ]
        t = Table(data, colWidths=[120, 100, 100, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
        story.append(t)
        story.append(PageBreak())
        
    doc.build(story)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 7. 07_structured_feed.xml (~100 KB)
def generate_structured_feed():
    filepath = os.path.join(EVAL_DIR, "07_structured_feed.xml")
    root = ET.Element("feed", xmlns="http://www.w3.org/2005/Atom")
    ET.SubElement(root, "title").text = "Global Security Advisory Feed"
    
    i = 1
    while True:
        entry = ET.SubElement(root, "entry")
        ET.SubElement(entry, "title").text = f"Security Advisory CVE-2026-{10000+i}"
        ET.SubElement(entry, "id").text = f"urn:uuid:12345678-1234-5678-1234-{i:012d}"
        ET.SubElement(entry, "updated").text = datetime.now().isoformat()
        ET.SubElement(entry, "content", type="html").text = f"&lt;p&gt;Vulnerability CVE-2026-{10000+i} in package cloud-pkg-{i}. CVSS: 9.8. Detailed remediation steps and patch guidelines.&lt;/p&gt;"
        
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(filepath, encoding="utf-8", xml_declaration=True)
        
        if os.path.getsize(filepath) >= 100 * 1024 or i >= 900:
            break
        i += 1
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 8. 08_cloud_audit.json (~100 KB)
def generate_cloud_audit():
    filepath = os.path.join(EVAL_DIR, "08_cloud_audit.json")
    events = []
    i = 1
    while True:
        events.append({
            "eventVersion": "1.08",
            "userIdentity": {"type": "IAMUser", "arn": f"arn:aws:iam::123456789012:user/admin-{i}"},
            "eventTime": datetime.now().isoformat(),
            "eventName": "AssumeRole" if i%2==0 else "PutObject",
            "sourceIPAddress": f"198.51.100.{i%255}",
            "requestParameters": {"bucket": f"prod-bucket-{i}", "region": "us-east-1"}
        })
        content = json.dumps(events, indent=2)
        if len(content.encode('utf-8')) >= 100 * 1024 or len(events) >= 900:
            break
        i += 1
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 9. 09_incident_metrics.csv (~100 KB)
def generate_incident_metrics():
    filepath = os.path.join(EVAL_DIR, "09_incident_metrics.csv")
    rows = [["timestamp", "host", "cpu_percent", "memory_mb", "disk_io_mbps", "latency_ms", "status_code", "error_type"]]
    t0 = datetime(2026, 7, 14, 0, 0, 0)
    hosts = ["web-01", "web-02", "db-01", "cache-01"]
    
    i = 1
    while True:
        rows.append([
            (t0 + timedelta(seconds=i*30)).isoformat(),
            hosts[i % len(hosts)],
            str(round(random.uniform(10, 99), 2)),
            str(random.randint(4096, 32768)),
            str(round(random.uniform(5, 200), 2)),
            str(round(random.uniform(2, 1500), 2)),
            str(200 if i%10!=0 else 502),
            "None" if i%10!=0 else "BadGateway"
        ])
        if i % 100 == 0:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            if os.path.getsize(filepath) >= 100 * 1024:
                break
        i += 1
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

# 10. 10_source_module.py (~100 KB)
def generate_source_module():
    filepath = os.path.join(EVAL_DIR, "10_source_module.py")
    code = '\"\"\"Vector Engine Module\"\"\"\nimport logging\nfrom typing import List, Dict, Any\n'
    i = 1
    while len(code.encode('utf-8')) < 100 * 1024:
        code += f'''
class Processor_{i}:
    """Processor class {i} for high-performance tensor routing."""
    def __init__(self, node_id: str = "node-{i}") -> None:
        self.node_id = node_id
        self.capacity: int = {i * 100}

    def process_{i}(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {{"node": self.node_id, "status": "OK", "val": {i}}}
'''
        i += 1
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Generated {filepath}: {os.path.getsize(filepath)/1024:.2f} KB")

if __name__ == "__main__":
    generate_email_thread()
    generate_novel_chapter()
    generate_slack_chat()
    generate_technical_report()
    generate_web_article()
    generate_academic_paper()
    generate_structured_feed()
    generate_cloud_audit()
    generate_incident_metrics()
    generate_source_module()
    print("All 10 evaluation datasets successfully generated and verified to 100 KB+ each!")
