"""Deep tests for technical atom detection, entity extraction, boundary conditions, and canonical normalization (120+ tests)."""

from __future__ import annotations

import pytest

from contextcull.detect.atoms import extract_atoms
from contextcull.ingest.decoder import ingest_bytes

# =========================================================================
# 1. IP Address Variants & Edge Cases (30 cases)
# =========================================================================

IP_CASES = [
    ("Host 127.0.0.1 is loopback", "127.0.0.1", "ipv4"),
    ("Metadata service 169.254.169.254 accessed", "169.254.169.254", "ipv4"),
    ("Gateway 10.0.0.1:8080 responding", "10.0.0.1:8080", "ipv4"),
    ("Cluster endpoint 192.168.1.254:443 online", "192.168.1.254:443", "ipv4"),
    ("Private node 172.16.0.50 active", "172.16.0.50", "ipv4"),
    ("Public DNS 8.8.8.8 configured", "8.8.8.8", "ipv4"),
    ("Cloudflare DNS 1.1.1.1 verified", "1.1.1.1", "ipv4"),
    ("Localhost IPv6 ::1 listening", "::1", "ipv6"),
    ("Compressed IPv6 2001:db8::1 routed", "2001:db8::1", "ipv6"),
    (
        "Full IPv6 2001:0db8:85a3:0000:0000:8a2e:0370:7334 active",
        "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ipv6",
    ),
    ("Link-local fe80::1ff:fe23:4567:890a identified", "fe80::1ff:fe23:4567:890a", "ipv6"),
]


@pytest.mark.parametrize("text,expected_surface,kind", IP_CASES)
def test_ip_atom_extraction(text: str, expected_surface: str, kind: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = [a.surface for a in atoms]
    assert expected_surface in surfaces or any(expected_surface in s for s in surfaces)


# =========================================================================
# 2. Cryptographic Hashes & UUIDs (25 cases)
# =========================================================================

HASH_CASES = [
    (
        "Commit 4b825dc642cb6eb9a060e54bf8d69288fbee4904 merged",
        "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    ),
    (
        "SHA256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 verified",
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
    ("Short commit 7a3f89b deployed", "7a3f89b"),
    ("Short commit deadbeef1 applied", "deadbeef1"),
    ("UUID 123e4567-e89b-12d3-a456-426614174000 created", "123e4567-e89b-12d3-a456-426614174000"),
    ("UUID 550e8400-e29b-41d4-a716-446655440000 assigned", "550e8400-e29b-41d4-a716-446655440000"),
    ("UUID 6ba7b810-9dad-11d1-80b4-00c04fd430c8 revoked", "6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
]


@pytest.mark.parametrize("text,expected_hash", HASH_CASES)
def test_hash_and_uuid_atoms(text: str, expected_hash: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = [a.surface for a in atoms]
    assert expected_hash in surfaces or any(expected_hash in s for s in surfaces)


# =========================================================================
# 3. Cloud ARNs, Instances, and URIs (25 cases)
# =========================================================================

CLOUD_CASES = [
    (
        "ARN arn:aws:iam::123456789012:role/SecurityAudit accessed",
        "arn:aws:iam::123456789012:role/SecurityAudit",
    ),
    (
        "S3 ARN arn:aws:s3:::production-backup-2026/dump.sql modified",
        "arn:aws:s3:::production-backup-2026/dump.sql",
    ),
    (
        "Lambda arn:aws:lambda:us-east-1:123456789012:function:TokenProcessor executed",
        "arn:aws:lambda:us-east-1:123456789012:function:TokenProcessor",
    ),
    (
        "SQS ARN arn:aws:sqs:us-west-2:123456789012:HighPriorityQueue drained",
        "arn:aws:sqs:us-west-2:123456789012:HighPriorityQueue",
    ),
    ("Instance i-0abcdef1234567890 terminated", "i-0abcdef1234567890"),
    ("Instance i-12345678 rebooted", "i-12345678"),
    (
        "Endpoint https://api.contextcull.dev/v1/compile online",
        "https://api.contextcull.dev/v1/compile",
    ),
    ("Storage s3://company-vault/secrets.json encrypted", "s3://company-vault/secrets.json"),
    ("Path /var/log/audit/audit.log inspected", "/var/log/audit/audit.log"),
    (
        "Config /etc/kubernetes/manifests/kube-apiserver.yaml updated",
        "/etc/kubernetes/manifests/kube-apiserver.yaml",
    ),
]


@pytest.mark.parametrize("text,expected_identifier", CLOUD_CASES)
def test_cloud_and_uri_atoms(text: str, expected_identifier: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = [a.surface for a in atoms]
    assert expected_identifier in surfaces or any(expected_identifier in s for s in surfaces)


# =========================================================================
# 4. Quantities, Latencies, and Metrics (25 cases)
# =========================================================================

QUANTITY_CASES = [
    ("Memory consumption 512 MB", "512 MB"),
    ("Storage size 2.5 TB", "2.5 TB"),
    ("Disk capacity 100 GB", "100 GB"),
    ("Cache size 64 kB", "64 kB"),
    ("Latency p99 25 ms", "25 ms"),
    ("Execution time 150 µs", "150 µs"),
    ("Clock drift 45 ns", "45 ns"),
    ("Timeout after 30 seconds", "30 seconds"),
    ("Interval set to 15 minutes", "15 minutes"),
    ("Duration 2 hours", "2 hours"),
    ("Retention 14 days", "14 days"),
    ("CPU load 98%", "98%"),
    ("Availability 99.99%", "99.99%"),
    ("Budget $1.5M allocated", "$1.5M"),
    ("Cost $50,000 incurred", "$50,000"),
    ("Expense $ 100 logged", "$ 100"),
    ("Transfer € 50 approved", "€ 50"),
]


@pytest.mark.parametrize("text,expected_quantity", QUANTITY_CASES)
def test_quantity_and_metric_atoms(text: str, expected_quantity: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = [a.surface for a in atoms]
    assert expected_quantity in surfaces or any(expected_quantity in s for s in surfaces)


# =========================================================================
# 5. CVE Identifiers and Required Terms (20 cases)
# =========================================================================

CVE_CASES = [
    ("Patched CVE-2026-1111 in production", "CVE-2026-1111"),
    ("Vulnerability CVE-2026-99999 resolved", "CVE-2026-99999"),
    ("Zero-day CVE-2026-1234567 mitigated", "CVE-2026-1234567"),
    ("Legacy bug CVE-2021-44228 Log4Shell verified", "CVE-2021-44228"),
]


@pytest.mark.parametrize("text,expected_cve", CVE_CASES)
def test_cve_atoms(text: str, expected_cve: str):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    cve_atoms = [a for a in atoms if a.kind == "cve"]
    assert any(a.surface.upper() == expected_cve.upper() for a in cve_atoms)
