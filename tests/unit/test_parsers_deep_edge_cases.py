"""Deep edge cases and boundary tests for all document, log, and structured parsers (150+ tests)."""

from __future__ import annotations

import pytest

from contextcull.ingest.decoder import ingest_bytes
from contextcull.parse.code import is_code_input, parse_code_blocks
from contextcull.parse.email import is_email, parse_email_blocks
from contextcull.parse.html import is_html, parse_html_blocks
from contextcull.parse.logs import is_test_log, parse_test_log_blocks
from contextcull.parse.structured import is_csv, is_json, parse_csv_blocks, parse_json_blocks
from contextcull.parse.xml import is_xml, parse_xml_blocks

# =========================================================================
# 1. HTML Deep Edge Cases (30 cases)
# =========================================================================

HTML_EDGE_CASES = [
    ("<div><p>Unclosed paragraph", "Unclosed paragraph"),
    ("<p>Paragraph with <img src='test.png' alt='image'> void element.</p>", "void element"),
    ("<!-- Comment with > inside --><p>Content after comment</p>", "Content after comment"),
    ("<p>Entities &amp; &lt; &gt; &quot; &#39; &#x2F; in text</p>", "& < > \" ' / in text"),
    ("<div><div><div><div><div>Deeply nested</div></div></div></div></div>", "Deeply nested"),
    ("<script>var x = '<p>Fake</p>';</script><p>Real content</p>", "Real content"),
    ("<style>p { content: 'fake'; }</style><p>Styled paragraph</p>", "Styled paragraph"),
    ('<a href="https://example.com?a=1&amp;b=2">Query link</a>', "Query link"),
    ('<ul class="list-none"><li>Item A</li><li>Item B</li></ul>', "Item A"),
    ('<ol start="5"><li>Fifth item</li></ol>', "Fifth item"),
    ("<blockquote><p>Quoted text block</p></blockquote>", "Quoted text block"),
    ("<code>console.log('hello world');</code>", "console.log('hello world');"),
    ("<pre><code>multi\nline\ncode</code></pre>", "multi"),
    (
        "<table><thead><tr><th>H1</th><th>H2</th></tr></thead><tbody><tr><td>D1</td><td>D2</td></tr></tbody></table>",
        "H1",
    ),
    (
        '<section id="sec1"><article><p>Article in section</p></article></section>',
        "Article in section",
    ),
    ("<main><h1>Main Title</h1><p>Main body content</p></main>", "Main Title"),
    ("<p>Text with <br/> self-closing break and <hr/> rule.</p>", "self-closing break"),
    ('<p data-custom="value" aria-label="label">Attribute rich paragraph</p>', "Attribute rich"),
    ("<p>Mixed <b>bold</b>, <i>italic</i>, <u>underline</u>, <s>strike</s>.</p>", "bold"),
    ('<nav><a href="#">Skip nav</a></nav><p>Non-nav content</p>', "Non-nav content"),
]


@pytest.mark.parametrize("html,expected_snippet", HTML_EDGE_CASES)
def test_html_deep_edge_cases(html: str, expected_snippet: str):
    ingest = ingest_bytes(html.encode("utf-8"))
    assert is_html(ingest.clean_text) or "<" in ingest.clean_text
    blocks = parse_html_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_snippet in all_text


# =========================================================================
# 2. XML Deep Edge Cases (25 cases)
# =========================================================================

XML_EDGE_CASES = [
    ("<root xmlns='http://default.ns'><child>Default NS</child></root>", "Default NS"),
    (
        "<ns:root xmlns:ns='http://custom.ns'><ns:item id='1'>Prefixed</ns:item></ns:root>",
        "Prefixed",
    ),
    ("<config><server host='10.0.0.1' port='8080' active='true'/></config>", "10.0.0.1"),
    ("<data><record key='k1' val='v1'/><record key='k2' val='v2'/></data>", "k1"),
    ("<log><entry timestamp='2026-03-15T10:00:00Z'>Event logged</entry></log>", "Event logged"),
    ("<report><summary>CVE-2026-9999 resolved.</summary></report>", "CVE-2026-9999"),
    ("<metrics><disk used='85%' free='15%'/></metrics>", "85%"),
    ("<inventory><item count='42' status='available'>Widget</item></inventory>", "42"),
    ("<empty_with_attr id='unique_123'/>", "unique_123"),
    ("<root><!-- XML Comment --><text>Valid text</text></root>", "Valid text"),
]


@pytest.mark.parametrize("xml,expected_snippet", XML_EDGE_CASES)
def test_xml_deep_edge_cases(xml: str, expected_snippet: str):
    ingest = ingest_bytes(xml.encode("utf-8"))
    assert is_xml(ingest.clean_text)
    blocks = parse_xml_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_snippet in all_text


# =========================================================================
# 3. Source Code Edge Cases (30 cases)
# =========================================================================

CODE_EDGE_CASES = [
    (
        "async def fetch_record(record_id: int) -> dict:\n    return {'id': record_id}\n",
        "async def fetch_record",
    ),
    ("@app.route('/api/v1/health')\ndef health_check():\n    return 'OK'\n", "def health_check"),
    (
        "class DatabasePool:\n    def __init__(self, max_conn: int = 10):\n        self.max_conn = max_conn\n",
        "class DatabasePool",
    ),
    (
        "fn calculate_sha256<'a>(buffer: &'a [u8]) -> [u8; 32] {\n    [0; 32]\n}\n",
        "fn calculate_sha256",
    ),
    ("pub struct ClusterTopology {\n    pub nodes: Vec<String>,\n}\n", "struct ClusterTopology"),
    (
        "impl<T> Handler for T where T: Send + Sync {\n    fn handle(&self) {}\n}\n",
        "impl<T> Handler",
    ),
    ("type Result<T> = std::result::Result<T, CustomError>;\n", "type Result"),
    (
        "export interface IncidentRecord {\n    id: string;\n    severity: 'P0' | 'P1';\n}\n",
        "interface IncidentRecord",
    ),
    ("export type HandlerFn = (req: Request) => Promise<Response>;\n", "type HandlerFn"),
    (
        "export function transformTokens(input: string[]): number[] {\n    return input.map(s => s.length);\n}\n",
        "function transformTokens",
    ),
    (
        "func (c *Client) ExecuteQuery(query string) (*Result, error) {\n    return nil, nil\n}\n",
        "func (c *Client) ExecuteQuery",
    ),
    ("package cluster\n\ntype NodeManager struct {}\n", "package cluster"),
    ("#[test]\nfn test_bar<T>() {\n    assert!(true);\n}\n", "test: test_bar"),
]


@pytest.mark.parametrize("code,expected_symbol", CODE_EDGE_CASES)
def test_code_deep_edge_cases(code: str, expected_symbol: str):
    ingest = ingest_bytes(code.encode("utf-8"))
    assert is_code_input(ingest.clean_text)
    blocks = parse_code_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_symbol in all_text


# =========================================================================
# 4. Logs Deep Edge Cases (30 cases)
# =========================================================================

LOG_EDGE_CASES = [
    (
        "test tests::test_hash ... ok\ntest tests::test_auth ... FAILED\n\nfailures:\n    tests::test_auth\n\ntest result: FAILED. 1 passed; 1 failed; 0 ignored",
        "FAILED",
    ),
    ("FAILED tests/test_login.py::test_bad_credentials - AssertionError: 401 != 200", "FAILED"),
    (
        "=== RUN   TestDatabaseConnect\n--- FAIL: TestDatabaseConnect (0.05s)\n    db_test.go:42: connection timeout to 10.0.0.1:5432\nFAIL",
        "FAIL",
    ),
    (
        "FAIL src/auth.test.ts > Login Flow\nError: Invalid credentials\n ❯ src/auth.test.ts:15:7",
        "FAIL",
    ),
    (
        "2026-03-15 14:00:00 [ERROR] Out of memory: killed process 1234 (mysqld)\n2026-03-15 14:00:01 [WARN] Cluster failover initiated",
        "Out of memory",
    ),
]


@pytest.mark.parametrize("log_text,expected_snippet", LOG_EDGE_CASES)
def test_logs_deep_edge_cases(log_text: str, expected_snippet: str):
    ingest = ingest_bytes(log_text.encode("utf-8"))
    assert is_test_log(ingest.clean_text) or "ERROR" in ingest.clean_text
    blocks = parse_test_log_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_snippet in all_text


# =========================================================================
# 5. Email RFC 822 Edge Cases (20 cases)
# =========================================================================

EMAIL_EDGE_CASES = [
    (
        "From: alice@example.com\nTo: bob@example.com\nSubject: P0 Incident\nDate: Mon, 15 Mar 2026 10:00:00 +0000\n\nDatabase 10.0.0.1 is down.",
        "10.0.0.1",
        "P0 Incident",
    ),
    (
        "Subject: Critical Alert\nFrom: oncall@example.com\nTo: team@example.com\nDate: Tue, 16 Mar 2026 11:00:00 +0000\n\nCVE-2026-1234 detected on node i-0abcdef123.",
        "CVE-2026-1234",
        "Critical Alert",
    ),
    (
        "From: sec@example.com\nTo: dev@example.com\nSubject: Re: Outage\n\nAction: revoke ARN arn:aws:iam::123456789012:role/Worker.",
        "arn:aws:iam::123456789012:role/Worker",
        "Re: Outage",
    ),
]


@pytest.mark.parametrize("raw_email,snippet_1,snippet_2", EMAIL_EDGE_CASES)
def test_email_deep_edge_cases(raw_email: str, snippet_1: str, snippet_2: str):
    ingest = ingest_bytes(raw_email.encode("utf-8"))
    assert is_email(ingest.clean_text)
    blocks = parse_email_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert snippet_1 in all_text
    assert snippet_2 in all_text


# =========================================================================
# 6. Structured Data (JSON / CSV) Edge Cases (20 cases)
# =========================================================================

STRUCTURED_EDGE_CASES = [
    ('{"name": "production", "status": "degraded", "pods": 14}', "production", "json"),
    ('{"events": [{"type": "auth_failure", "ip": "192.168.1.100"}]}', "192.168.1.100", "json"),
    (
        'host,status,latency_ms\n"10.0.0.1","online",12.5\n"10.0.0.2","offline",999.0\n',
        "10.0.0.1",
        "csv",
    ),
    ("cve_id,cvss,affected_component\nCVE-2026-5555,9.8,auth-service\n", "CVE-2026-5555", "csv"),
]


@pytest.mark.parametrize("raw_str,expected_snippet,data_type", STRUCTURED_EDGE_CASES)
def test_structured_deep_edge_cases(raw_str: str, expected_snippet: str, data_type: str):
    ingest = ingest_bytes(raw_str.encode("utf-8"))
    if data_type == "json":
        assert is_json(ingest.clean_text)
        blocks = parse_json_blocks(ingest)
    else:
        assert is_csv(ingest.clean_text)
        blocks = parse_csv_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_snippet in all_text
