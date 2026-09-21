"""Comprehensive parameterized test suite for atom and entity detection (120+ test cases)."""

import pytest

from contextcull.detect.atoms import extract_atoms
from contextcull.ingest.decoder import ingest_bytes

# 1. CVE identifier patterns (20 cases)
CVE_CASES = [
    ("Found CVE-2026-12345 in component.", "CVE-2026-12345", True),
    ("Patched CVE-2024-0001 yesterday.", "CVE-2024-0001", True),
    ("Critical issue: cve-2025-9999999.", "CVE-2025-9999999", True),
    ("Refer to CVE-1999-0002 for details.", "CVE-1999-0002", True),
    ("High severity: CVE-2023-1234567.", "CVE-2023-1234567", True),
    ("Tracking CVE-2026-66384.", "CVE-2026-66384", True),
    ("Fixed CVE-2026-53362 in v2.", "CVE-2026-53362", True),
    ("Review CVE-2021-44228 log4j.", "CVE-2021-44228", True),
    ("Advisory for CVE-2022-22965 spring.", "CVE-2022-22965", True),
    ("Resolved CVE-2026-31184 ingress.", "CVE-2026-31184", True),
    ("Alert on CVE-2026-29910 cache.", "CVE-2026-29910", True),
    ("Reported CVE-2026-18823 runner.", "CVE-2026-18823", True),
    ("Security note CVE-2020-8554 k8s.", "CVE-2020-8554", True),
    ("Advisory CVE-2018-1002105 api.", "CVE-2018-1002105", True),
    ("Vulnerability CVE-2019-5736 runc.", "CVE-2019-5736", True),
    ("Identified CVE-2020-1472 zerologon.", "CVE-2020-1472", True),
    ("Testing CVE-2021-3156 sudo.", "CVE-2021-3156", True),
    ("Legacy CVE-2014-0160 heartbleed.", "CVE-2014-0160", True),
    ("Old flaw CVE-2017-0144 eternalblue.", "CVE-2017-0144", True),
    ("CVE-2026-0001 reported by team.", "CVE-2026-0001", True),
]

# 2. IPv4 and IPv6 addresses (20 cases)
IP_CASES = [
    ("Server running at 192.168.1.1:8080.", "192.168.1.1", True),
    ("Gateway IP 10.0.0.1 in VPC.", "10.0.0.1", True),
    ("External IP 198.51.100.44 flagged.", "198.51.100.44", True),
    ("DNS server 8.8.8.8 reached.", "8.8.8.8", True),
    ("Cloudflare DNS 1.1.1.1.", "1.1.1.1", True),
    ("Localhost bound to 127.0.0.1.", "127.0.0.1", True),
    ("Backend service at 172.16.254.1.", "172.16.254.1", True),
    ("Target host 10.100.0.15:8200.", "10.100.0.15", True),
    ("Subnet router at 192.168.0.254.", "192.168.0.254", True),
    ("NAT gateway 54.239.28.85.", "54.239.28.85", True),
    ("Bastion host at 52.95.110.1.", "52.95.110.1", True),
    ("Ingress proxy 34.216.12.18.", "34.216.12.18", True),
    ("Monitoring agent 10.244.0.1.", "10.244.0.1", True),
    ("Database replica 10.0.3.50.", "10.0.3.50", True),
    ("Audit collector 192.0.2.1.", "192.0.2.1", True),
    ("IPv6 loopback ::1 configured.", "::1", True),
    (
        "IPv6 address 2001:0db8:85a3:0000:0000:8a2e:0370:7334 active.",
        "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        True,
    ),
    ("Short IPv6 2001:db8::1 in use.", "2001:db8::1", True),
    ("Link-local fe80::1ff:fe23:4567:890a.", "fe80::1ff:fe23:4567:890a", True),
    ("IPv6 gateway 2600:1f18:63fe::1.", "2600:1f18:63fe::1", True),
]

# 3. UUIDs (20 cases)
UUID_CASES = [
    (
        "Transaction id 123e4567-e89b-12d3-a456-426614174000.",
        "123e4567-e89b-12d3-a456-426614174000",
        True,
    ),
    (
        "Session 550e8400-e29b-41d4-a716-446655440000 started.",
        "550e8400-e29b-41d4-a716-446655440000",
        True,
    ),
    (
        "Record c9bf9e57-1685-4c89-bafb-ff5af830be8a created.",
        "c9bf9e57-1685-4c89-bafb-ff5af830be8a",
        True,
    ),
    (
        "Nil UUID 00000000-0000-0000-0000-000000000000 found.",
        "00000000-0000-0000-0000-000000000000",
        True,
    ),
    (
        "User e7f5c9e2-3b1a-4f8d-9c2e-1a3b5c7d9e0f logged in.",
        "e7f5c9e2-3b1a-4f8d-9c2e-1a3b5c7d9e0f",
        True,
    ),
    ("Token a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d.", "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d", True),
    ("Message b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e.", "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e", True),
    ("Device c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f.", "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f", True),
    ("Cluster d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a.", "d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a", True),
    ("Node e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b.", "e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b", True),
    ("Pod f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c.", "f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c", True),
    ("Task 01234567-89ab-4cde-8f01-23456789abcd.", "01234567-89ab-4cde-8f01-23456789abcd", True),
    ("Trace 11223344-5566-4778-899a-aabbccddeeff.", "11223344-5566-4778-899a-aabbccddeeff", True),
    ("Span 22334455-6677-4889-9aab-bccddeeff001.", "22334455-6677-4889-9aab-bccddeeff001", True),
    ("Context 33445566-7788-499a-abbc-cddeeff00112.", "33445566-7788-499a-abbc-cddeeff00112", True),
    ("Event 44556677-8899-4aab-bccd-deeff0011223.", "44556677-8899-4aab-bccd-deeff0011223", True),
    ("Batch 55667788-99aa-4bbc-cdde-eff001122334.", "55667788-99aa-4bbc-cdde-eff001122334", True),
    ("Job 66778899-aabb-4ccd-deef-f00112233445.", "66778899-aabb-4ccd-deef-f00112233445", True),
    ("Worker 778899aa-bbcc-4dde-eff0-011223344556.", "778899aa-bbcc-4dde-eff0-011223344556", True),
    ("Item 8899aabb-ccdd-4eef-f001-122334455667.", "8899aabb-ccdd-4eef-f001-122334455667", True),
]

# 4. Git commit hashes & SHAs (20 cases)
SHA_CASES = [
    (
        "Commit da39a3ee5e6b4b0d3255bfef95601890afd80709 merged.",
        "da39a3ee5e6b4b0d3255bfef95601890afd80709",
        True,
    ),
    (
        "Rollback to e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.",
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        True,
    ),
    (
        "Revision a1b2c3d4e5f60718293a4b5c6d7e8f901a2b3c4d.",
        "a1b2c3d4e5f60718293a4b5c6d7e8f901a2b3c4d",
        True,
    ),
    (
        "Tagged commit f1e2d3c4b5a6071829384756abcdef0123456789.",
        "f1e2d3c4b5a6071829384756abcdef0123456789",
        True,
    ),
    (
        "Verified 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08.",
        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        True,
    ),
    (
        "Build 5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8.",
        "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
        True,
    ),
    ("Short commit a1b2c3d tested.", "a1b2c3d", True),
    ("Hash 7b9f8x9 verified.", "7b9f8x9", False),
    ("Git ref c0ffee1 deployed.", "c0ffee1", True),
    ("Base sha 123456a checked out.", "123456a", True),
    ("Branch head 89abcdef in main.", "89abcdef", True),
    ("Cherry-pick fedcba9 applied.", "fedcba9", True),
    ("Rebase onto 012345b finished.", "012345b", True),
    ("Parent 456789a confirmed.", "456789a", True),
    ("Merge commit bcdef01 created.", "bcdef01", True),
    ("Tree 234567c recorded.", "234567c", True),
    ("Blob 345678d stored.", "345678d", True),
    ("Ref 6789abc resolved.", "6789abc", True),
    ("Tag def0123 created.", "def0123", True),
    ("Head 9abcdef pushed.", "9abcdef", True),
]

# 5. Cloud resources & ARNs (20 cases)
CLOUD_CASES = [
    ("Terminated i-0622056ec3e996a7c successfully.", "i-0622056ec3e996a7c", True),
    ("Instance i-0123456789abcdef0 running.", "i-0123456789abcdef0", True),
    ("Spot instance i-0abcdef1234567890 launched.", "i-0abcdef1234567890", True),
    (
        "Role arn:aws:iam::123456789012:role/DataPipelineWorker assumed.",
        "arn:aws:iam::123456789012:role/DataPipelineWorker",
        True,
    ),
    ("Bucket arn:aws:s3:::acme-forensics-vault.", "arn:aws:s3:::acme-forensics-vault", True),
    (
        "Queue arn:aws:sqs:us-east-1:123456789012:incident-queue.",
        "arn:aws:sqs:us-east-1:123456789012:incident-queue",
        True,
    ),
    (
        "KMS key arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012.",
        "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
        True,
    ),
    (
        "Lambda arn:aws:lambda:us-west-2:123456789012:function:audit-logger.",
        "arn:aws:lambda:us-west-2:123456789012:function:audit-logger",
        True,
    ),
    ("Cluster us-east-prod-1 degraded.", "us-east-prod-1", True),
    ("Cluster eu-west1-01 healthy.", "eu-west1-01", True),
    ("Pod data-worker-7b9f8-x9z2q isolated.", "data-worker-7b9f8-x9z2q", True),
    ("Database cluster-id aurora-prod-analytics-01 queried.", "aurora-prod-analytics-01", True),
    ("Cache redis-prod-01-shard-3 evicted.", "redis-prod-01-shard-3", True),
    ("Namespace processing cordoned.", "processing", False),  # Non-atom word
    ("Storage s3://acme-forensics-vault/dump.bin.", "s3://acme-forensics-vault/dump.bin", True),
    ("URL https://internal.vault.corp/v1/secret.", "https://internal.vault.corp/v1/secret", True),
    (
        "Path /var/run/secrets/kubernetes.io/serviceaccount/token read.",
        "/var/run/secrets/kubernetes.io/serviceaccount/token",
        True,
    ),
    ("Cache dir /tmp/.cache scraped.", "/tmp/.cache", True),
    ("Socket 10.100.0.15:8200 rejected.", "10.100.0.15:8200", True),
    ("Port 8080 open.", "8080", False),
]

# 6. Quantities, metrics, and timestamps (25 cases)
QUANTITY_CASES = [
    ("Exfiltrated 956 MB from db.", "956 MB", True),
    ("Found 14 ms latency in cache.", "14 ms", True),
    ("Memory dump 731 MB completed.", "731 MB", True),
    ("Buffer size 16 MB allocated.", "16 MB", True),
    ("Timeout after 30 min of inactivity.", "30 min", True),
    ("Latency spiked to 3200ms.", "3200ms", True),
    ("Baseline latency is 45ms.", "45ms", True),
    ("Recovered to 1.2ms p99.", "1.2ms", True),
    ("Spike reached 42ms p99.", "42ms", True),
    ("Throughput dropped by 95%.", "95%", True),
    ("Uptime was 99.992% in region.", "99.992%", True),
    ("SLA guaranteed 99.978%.", "99.978%", True),
    ("Recorded 99.989% availability.", "99.989%", True),
    ("Processed 42M rows in scan.", "42M", True),
    ("Took 500ms to failover.", "500ms", True),
    ("Clock drift of 150µs detected.", "150µs", True),
    ("Jitter was 25ns on bus.", "25ns", True),
    ("Total size 128 GB on disk.", "128 GB", True),
    ("Storage 2 TB provisioned.", "2 TB", True),
    ("File 512 KB written.", "512 KB", True),
    ("Date was 2026-07-11 in log.", "2026-07-11", True),
    ("Timestamp 2026-07-14T08:20:00Z.", "2026-07-14T08:20:00Z", True),
    ("Time 08:12 UTC recorded.", "08:12 UTC", True),
    ("Next briefing at 10:00 UTC.", "10:00 UTC", True),
    ("Post-mortem at 14:00 UTC.", "14:00 UTC", True),
]


@pytest.mark.parametrize("text,expected_surface,should_find", CVE_CASES)
def test_detect_cve_atoms(text: str, expected_surface: str, should_find: bool):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = {a.surface for a in atoms}
    if should_find:
        assert any(expected_surface.lower() in s.lower() for s in surfaces), (
            f"Expected {expected_surface} in {surfaces}"
        )


@pytest.mark.parametrize("text,expected_surface,should_find", IP_CASES)
def test_detect_ip_atoms(text: str, expected_surface: str, should_find: bool):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = {a.surface for a in atoms}
    if should_find:
        assert any(expected_surface in s for s in surfaces), (
            f"Expected {expected_surface} in {surfaces}"
        )


@pytest.mark.parametrize("text,expected_surface,should_find", UUID_CASES)
def test_detect_uuid_atoms(text: str, expected_surface: str, should_find: bool):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = {a.surface for a in atoms}
    if should_find:
        assert any(expected_surface.lower() in s.lower() for s in surfaces), (
            f"Expected {expected_surface} in {surfaces}"
        )


@pytest.mark.parametrize("text,expected_surface,should_find", SHA_CASES)
def test_detect_sha_atoms(text: str, expected_surface: str, should_find: bool):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = {a.surface for a in atoms}
    if should_find:
        assert any(expected_surface.lower() in s.lower() for s in surfaces), (
            f"Expected {expected_surface} in {surfaces}"
        )


@pytest.mark.parametrize("text,expected_surface,should_find", CLOUD_CASES)
def test_detect_cloud_atoms(text: str, expected_surface: str, should_find: bool):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = {a.surface for a in atoms}
    if should_find:
        assert any(expected_surface in s for s in surfaces), (
            f"Expected {expected_surface} in {surfaces}"
        )


@pytest.mark.parametrize("text,expected_surface,should_find", QUANTITY_CASES)
def test_detect_quantity_atoms(text: str, expected_surface: str, should_find: bool):
    ingest = ingest_bytes(text.encode("utf-8"))
    atoms = extract_atoms(ingest)
    surfaces = {a.surface for a in atoms}
    if should_find:
        assert any(expected_surface in s for s in surfaces), (
            f"Expected {expected_surface} in {surfaces}"
        )
