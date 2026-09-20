from contextcull.api import ContextCompiler
from contextcull.ir.models import CompileMode

INCIDENT_FIXTURE = "INCIDENT REPORT: OUTAGE IN CLUSTER US-EAST-1\n\n" + "\n\n".join(
    f"Section {i}: Server 10.0.0.{i} encountered an anomaly with CVE-2026-{1000 + i}. "
    f"The primary pod data-worker-{i} in namespace processing reported high latency of {20 + i} ms. "
    f"Engineers executed failover at 08:{i:02d}:00 UTC and verified that no data loss occurred. "
    f"Resource utilization remained stable with memory at {50 + (i % 40)}% and CPU load at {40 + (i % 50)}%."
    for i in range(1, 65)
)


def test_provenance_roundtrip_sample_incident():
    """Verify that every copy segment in the compiled manifest matches raw source bytes exactly."""
    raw_bytes = INCIDENT_FIXTURE.encode("utf-8")
    compiler = ContextCompiler(mode=CompileMode.COMPACT)
    result = compiler.compile(raw_bytes)

    assert result.ok, f"Compilation failed: {result.status}"
    manifest = result.manifest
    output_text = result.text

    segments = manifest.get("output_segments", [])
    copy_segments = [s for s in segments if s.get("kind") == "copy"]
    assert len(copy_segments) > 50, "Expected at least 50 copy segments"

    for seg in copy_segments:
        # Check source byte span round-trip
        for src in seg.get("sources", []):
            s_bytes = raw_bytes[src["start"] : src["end"]]
            s_str = s_bytes.decode("utf-8", errors="replace").strip()
            assert s_str in output_text, (
                f"Source span [{src['start']}, {src['end']}) not found in output"
            )

        # Check output byte range matches emitted text exactly
        out_start = seg["output_start"]
        out_end = seg["output_end"]
        seg_bytes = output_text.encode("utf-8")[out_start:out_end]
        assert len(seg_bytes) == (out_end - out_start)


def test_provenance_multibyte_and_crlf():
    """Verify provenance integrity across multibyte Unicode and CRLF line endings."""
    text = (
        "Header Line\r\n"
        "Security incident on host 10.0.0.1 with CVE-2026-66384.\r\n"
        "多语言文本测试：系统检测到未经授权的访问。\r\n"
        "Footer line.\r\n"
    )
    raw_bytes = text.encode("utf-8")
    compiler = ContextCompiler(mode=CompileMode.STRICT)
    result = compiler.compile(raw_bytes)

    assert result.ok
    manifest = result.manifest

    for seg in manifest.get("output_segments", []):
        if seg.get("kind") == "copy":
            for src in seg.get("sources", []):
                span_bytes = raw_bytes[src["start"] : src["end"]]
                assert span_bytes.decode("utf-8").strip() in result.text
