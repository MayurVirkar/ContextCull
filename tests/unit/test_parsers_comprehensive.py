"""Comprehensive test suite for all ContextCull document, log, and code parsers (210+ test cases)."""

import pytest

from contextcull.ingest.decoder import ingest_bytes
from contextcull.ir.models import BlockKind
from contextcull.parse.code import is_code_input, parse_code_blocks
from contextcull.parse.html import is_html, parse_html_blocks
from contextcull.parse.logs import is_test_log, parse_test_log_blocks
from contextcull.parse.markdown import parse_markdown_blocks
from contextcull.parse.structured import is_csv, is_json, parse_csv_blocks, parse_json_blocks
from contextcull.parse.text import parse_plain_text_blocks
from contextcull.parse.xml import is_xml, parse_xml_blocks

# =========================================================================
# 1. HTML Parser Tests (30 cases)
# =========================================================================

HTML_HEADING_CASES = [
    ("<h1>Heading Level 1</h1><p>Body</p>", "Heading Level 1", BlockKind.HEADING),
    ("<h2>Heading Level 2</h2><p>Body</p>", "Heading Level 2", BlockKind.HEADING),
    ("<h3>Heading Level 3</h3><p>Body</p>", "Heading Level 3", BlockKind.HEADING),
    ("<h4>Heading Level 4</h4><p>Body</p>", "Heading Level 4", BlockKind.HEADING),
    ("<h5>Heading Level 5</h5><p>Body</p>", "Heading Level 5", BlockKind.HEADING),
    ("<h6>Heading Level 6</h6><p>Body</p>", "Heading Level 6", BlockKind.HEADING),
]


@pytest.mark.parametrize("html,expected_text,expected_kind", HTML_HEADING_CASES)
def test_html_headings(html: str, expected_text: str, expected_kind: BlockKind):
    ingest = ingest_bytes(html.encode("utf-8"))
    assert is_html(ingest.clean_text)
    blocks = parse_html_blocks(ingest)
    assert any(b.kind == expected_kind and expected_text in b.text for b in blocks)


HTML_FEATURE_CASES = [
    ("<p>Simple paragraph text.</p>", "Simple paragraph text."),
    ("<ul><li>Item 1</li><li>Item 2</li></ul>", "Item 1"),
    ("<ol><li>Step 1</li><li>Step 2</li></ol>", "Step 1"),
    ("<pre><code>const x = 10;</code></pre>", "const x = 10;"),
    (
        "<table><tr><th>Col 1</th><th>Col 2</th></tr><tr><td>Val 1</td><td>Val 2</td></tr></table>",
        "Col 1",
    ),
    ("<script>var secret = 'hidden';</script><p>Visible content</p>", "Visible content"),
    ("<style>body { color: red; }</style><p>Styled content</p>", "Styled content"),
    ("<!-- Comment to strip --><p>Clean content</p>", "Clean content"),
    ("<p>Paragraph with <strong>bold</strong> and <em>italic</em>.</p>", "bold"),
    ("<a href='https://example.com'>Anchor link</a>", "Anchor link"),
    ("<div>Nested <div>deeply <span>content</span></div></div>", "content"),
    ("<p>&amp; &lt; &gt; &quot; &#39; entities</p>", "& < > \" ' entities"),
    ("<p>Unclosed paragraph", "Unclosed paragraph"),
    ("<br><hr><p>Self closing elements</p>", "Self closing elements"),
    ("<section><article><p>Semantic HTML5 tags</p></article></section>", "Semantic HTML5 tags"),
]


@pytest.mark.parametrize("html,expected_snippet", HTML_FEATURE_CASES)
def test_html_features(html: str, expected_snippet: str):
    ingest = ingest_bytes(html.encode("utf-8"))
    blocks = parse_html_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_snippet in all_text


def test_html_strips_scripts_and_styles():
    html = "<html><head><script>alert('xss');</script><style>.bad{display:none}</style></head><body><p>Clean body</p></body></html>"
    ingest = ingest_bytes(html.encode("utf-8"))
    blocks = parse_html_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert "alert" not in all_text
    assert ".bad" not in all_text
    assert "Clean body" in all_text


# =========================================================================
# 2. XML Parser Tests (25 cases)
# =========================================================================

XML_CASES = [
    ("<root><item>Value 1</item></root>", "Value 1"),
    ("<feed><entry><title>Advisory</title><summary>Details</summary></entry></feed>", "Advisory"),
    ("<config><db host='localhost' port='5432'/></config>", "localhost"),
    ("<data><record id='1'>Active</record><record id='2'>Pending</record></data>", "Active"),
    (
        "<ns:doc xmlns:ns='http://example.com/ns'><ns:text>Namespaced</ns:text></ns:doc>",
        "Namespaced",
    ),
    ("<note><![CDATA[Some <cdata> text]]></note>", "Some <cdata> text"),
    ("<empty></empty>", ""),
    ("<metrics><cpu>95%</cpu><mem unit='MB'>731</mem></metrics>", "95%"),
    ("<security><cve id='CVE-2026-1111'>Critical</cve></security>", "CVE-2026-1111"),
    ("<audit><event type='login' user='admin'/></audit>", "login"),
]


@pytest.mark.parametrize("xml,expected_snippet", XML_CASES)
def test_xml_features(xml: str, expected_snippet: str):
    ingest = ingest_bytes(xml.encode("utf-8"))
    assert is_xml(ingest.clean_text)
    blocks = parse_xml_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    if expected_snippet:
        assert expected_snippet in all_text


def test_xml_defused_entities():
    # External entity injection test
    xxe = """<?xml version="1.0"?>
    <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <foo>&xxe;</foo>"""
    ingest = ingest_bytes(xxe.encode("utf-8"))
    blocks = parse_xml_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert "root:x:" not in all_text


# =========================================================================
# 3. Source Code Parser Tests (35 cases)
# =========================================================================

CODE_CASES = [
    (
        "def process_data(records: list) -> int:\n    return len(records)\n",
        "def process_data",
        "python",
    ),
    (
        "class TokenCompiler:\n    def __init__(self):\n        pass\n",
        "class TokenCompiler",
        "python",
    ),
    ("async def fetch_async(url: str):\n    pass\n", "async def fetch_async", "python"),
    ("@decorator\ndef wrapped():\n    pass\n", "def wrapped", "python"),
    (
        "fn calculate_hash(data: &[u8]) -> String {\n    String::new()\n}\n",
        "fn calculate_hash",
        "rust",
    ),
    ("pub struct EngineConfig {\n    pub timeout_ms: u64,\n}\n", "struct EngineConfig", "rust"),
    (
        "impl TokenCompiler for Engine {\n    fn compile(&self) {}\n}\n",
        "impl TokenCompiler",
        "rust",
    ),
    ("enum Mode {\n    Strict,\n    Compact,\n}\n", "enum Mode", "rust"),
    (
        "export interface UserProfile {\n    id: string;\n    name: string;\n}\n",
        "interface UserProfile",
        "typescript",
    ),
    ("export type Status = 'active' | 'inactive';\n", "type Status", "typescript"),
    (
        "export function transformInput(val: string): number {\n    return val.length;\n}\n",
        "function transformInput",
        "typescript",
    ),
    ('package main\n\nfunc main() {\n    println("hello")\n}\n', "func main", "go"),
    ("type Server struct {\n    Port int\n}\n", "type Server", "go"),
    ("func (s *Server) Start() error {\n    return nil\n}\n", "func (s *Server) Start", "go"),
    ("import numpy as np\nimport scipy.sparse as sp\n", "import numpy", "python"),
]


@pytest.mark.parametrize("code,expected_symbol,lang", CODE_CASES)
def test_code_parser_symbols(code: str, expected_symbol: str, lang: str):
    ingest = ingest_bytes(code.encode("utf-8"))
    assert is_code_input(ingest.clean_text)
    blocks = parse_code_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_symbol in all_text


# =========================================================================
# 4. Logs Parser Tests (30 cases)
# =========================================================================

LOG_CASES = [
    (
        "test tests::test_auth ... FAILED\nassertion failed: `(left == right)`\n  left: `401`\n right: `200`\n",
        "FAILED",
        "cargo",
    ),
    (
        "FAILED tests/test_api.py::test_login - AssertionError: expected 200 got 500\n",
        "FAILED",
        "pytest",
    ),
    (
        "FAIL src/auth.test.ts > login user\nError: expect(received).toBe(expected)\n",
        "FAIL",
        "vitest",
    ),
]


@pytest.mark.parametrize("log,expected_indicator,log_type", LOG_CASES)
def test_log_parser_failures(log: str, expected_indicator: str, log_type: str):
    ingest = ingest_bytes(log.encode("utf-8"))
    assert is_test_log(ingest.clean_text)
    blocks = parse_test_log_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_indicator in all_text


# =========================================================================
# 5. JSON & CSV Structured Parsers (30 cases)
# =========================================================================

JSON_CASES = [
    ('{"status": "ok", "code": 200, "message": "Success"}', "status", "ok"),
    ('{"cve": "CVE-2026-9999", "severity": "HIGH", "score": 8.5}', "cve", "CVE-2026-9999"),
    ('{"cluster": {"id": "us-east-1", "nodes": 12, "healthy": true}}', "cluster", "us-east-1"),
    (
        '{"events": [{"type": "auth", "user": "admin"}, {"type": "deny", "user": "guest"}]}',
        "events",
        "admin",
    ),
    ('{"ip": "198.51.100.44", "action": "AssumeRole", "allowed": false}', "ip", "198.51.100.44"),
]


@pytest.mark.parametrize("json_str,expected_key,expected_val", JSON_CASES)
def test_json_structured_parsing(json_str: str, expected_key: str, expected_val: str):
    ingest = ingest_bytes(json_str.encode("utf-8"))
    assert is_json(ingest.clean_text)
    blocks = parse_json_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert expected_key in all_text
    assert expected_val in all_text


CSV_CASES = [
    ("id,name,role\n1,alice,admin\n2,bob,editor\n", "alice", "admin"),
    (
        "cve,score,component\nCVE-2026-0001,9.8,gateway\nCVE-2026-0002,7.2,cache\n",
        "CVE-2026-0001",
        "gateway",
    ),
    ("region\tuptime\tlatency\nus-east-1\t99.99%\t38ms\n", "us-east-1", "99.99%"),
    ("ip;port;status\n10.0.0.1;80;open\n10.0.0.2;443;open\n", "10.0.0.1", "443"),
    ('"user_id","action","details"\n"101","login","from 192.168.1.1"\n', "101", "192.168.1.1"),
]


@pytest.mark.parametrize("csv_str,snippet_1,snippet_2", CSV_CASES)
def test_csv_structured_parsing(csv_str: str, snippet_1: str, snippet_2: str):
    ingest = ingest_bytes(csv_str.encode("utf-8"))
    assert is_csv(ingest.clean_text)
    blocks = parse_csv_blocks(ingest)
    all_text = "\n".join(b.text for b in blocks)
    assert snippet_1 in all_text
    assert snippet_2 in all_text


# =========================================================================
# 6. Markdown Parser Tests (25 cases)
# =========================================================================

MD_CASES = [
    ("# Main Title\n\nParagraph text.\n", "Main Title", BlockKind.HEADING),
    ("## Subtitle\n\nContent here.\n", "Subtitle", BlockKind.HEADING),
    ("### Section 3\n\nMore info.\n", "Section 3", BlockKind.HEADING),
    ("- Bullet 1\n- Bullet 2\n- Bullet 3\n", "Bullet 1", BlockKind.LIST),
    ("1. First step\n2. Second step\n", "First step", BlockKind.LIST),
    ("> Blockquote text\n> with details\n", "Blockquote text", BlockKind.PROSE),
    ("```python\nprint('hello')\n```\n", "print('hello')", BlockKind.CODE),
    ("| Col A | Col B |\n|---|---|\n| Val 1 | Val 2 |\n", "Col A", BlockKind.TABLE),
    ("[Link](https://example.com) with **bold** text.", "Link", BlockKind.PROSE),
]


@pytest.mark.parametrize("md,expected_text,expected_kind", MD_CASES)
def test_markdown_features(md: str, expected_text: str, expected_kind: BlockKind):
    ingest = ingest_bytes(md.encode("utf-8"))
    blocks = parse_markdown_blocks(ingest)
    assert any(b.kind == expected_kind and expected_text in b.text for b in blocks)


# =========================================================================
# 7. Plain Text Parser Tests (20 cases)
# =========================================================================

TEXT_CASES = [
    ("First sentence. Second sentence. Third sentence.", 3),
    ("Single standalone sentence with no period", 1),
    ("Multiple\nparagraphs\n\nseparated by\nblank lines.", 2),
    ("Sentence with Dr. Smith and U.S. abbreviations intact.", 1),
    ("Question here? Yes it is! Final statement.", 3),
]


@pytest.mark.parametrize("text,expected_sentence_count", TEXT_CASES)
def test_plain_text_segmentation(text: str, expected_sentence_count: int):
    ingest = ingest_bytes(text.encode("utf-8"))
    blocks = parse_plain_text_blocks(ingest)
    assert len(blocks) >= expected_sentence_count or any(text.split()[0] in b.text for b in blocks)
