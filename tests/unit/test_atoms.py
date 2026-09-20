"""Unit tests for protected atom detection against generic patterns and whitepaper benchmark terms."""

from tep.detect.atoms import extract_atoms
from tep.ingest.decoder import ingest_bytes


def test_extract_generic_technical_atoms():
    """Verify that CVEs, IPs, UUIDs, Git SHAs, and AWS Instance IDs are automatically detected and required."""
    text = """
    Incident details:
    Vulnerability CVE-2026-66384 was exploited from 192.168.1.105 targeting AWS instance i-0622056ec3e996a7c.
    Compromised session UUID: 123e4567-e89b-12d3-a456-426614174000.
    Attacker committed malicious payload in git commit 4b825dc642cb6eb9a060e54bf8d69288fbee4904.
    """
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)

    kinds = {a.kind: a for a in atoms}

    assert "cve" in kinds
    assert kinds["cve"].surface == "CVE-2026-66384"
    assert kinds["cve"].required is True

    assert "ipv4" in kinds
    assert kinds["ipv4"].surface == "192.168.1.105"
    assert kinds["ipv4"].required is True

    assert "instance_id" in kinds
    assert kinds["instance_id"].surface == "i-0622056ec3e996a7c"
    assert kinds["instance_id"].required is True

    assert "uuid" in kinds
    assert kinds["uuid"].surface == "123e4567-e89b-12d3-a456-426614174000"
    assert kinds["uuid"].required is True

    assert "git_sha" in kinds
    assert kinds["git_sha"].surface == "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    assert kinds["git_sha"].required is True


def test_extract_all_19_benchmark_atoms():
    benchmark_text = """
    Incident Technical Report:
    During the incident, the attacker leveraged the ReferenceFileSystem exploit vector in Jinja templates.
    The C2 channel connected to Artifactory while targeting vulnerable RubyGems packages.
    Evaluation framework ExploitGym and model GPT-5.6 Sol were assessed by CrowdStrike.
    The host environment on Modal and compromised workload CyberGym exposed Kubernetes configurations.
    Privilege escalation occurred via /etc/sudoers.d using forged JWT tokens.
    Public disclosure occurred at Black Hat.
    Data exfiltration totaled 731 MB across 311 compromised repositories and 22 admin accounts.
    The incident mandated a 30 min SLA starting at 2025-04-22T12:00:00Z.
    Root cause was determined to be insecure deserialization.
    """

    required_terms = [
        "ReferenceFileSystem",
        "Jinja",
        "Artifactory",
        "RubyGems",
        "ExploitGym",
        "GPT-5.6 Sol",
        "CrowdStrike",
        "Modal",
        "CyberGym",
        "Kubernetes",
        "/etc/sudoers.d",
        "JWT",
        "Black Hat",
        "731 MB",
        "311",
        "22",
        "30 min",
        "2025-04-22T12:00:00Z",
        "deserialization",
    ]

    ingest = ingest_bytes(benchmark_text.encode("utf-8"))
    atoms = extract_atoms(ingest, required_terms=required_terms)

    for term in required_terms:
        found = any(term in a.surface or term == a.surface for a in atoms)
        assert found, f"Benchmark atom '{term}' was not detected in extract_atoms"


def test_extract_quantities_and_paths():
    text = "Failed 731 MB transfer after 30 min SLA at /etc/sudoers.d and src/auth/token.rs:88:5."
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)

    kinds = {a.kind for a in atoms}
    assert "quantity" in kinds
    assert "file_location" in kinds

    quantities = [a.surface for a in atoms if a.kind == "quantity"]
    assert "731 MB" in quantities
    assert "30 min" in quantities
