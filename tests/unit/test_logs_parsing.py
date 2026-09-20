"""Tests for log parsing and multi-failure isolation (Cargo, Pytest)."""

from contextcull.ingest.decoder import ingest_bytes
from contextcull.parse.logs import parse_test_log_blocks


def test_cargo_multi_failure_distinct_locations():
    """Verify that multiple cargo test failures receive their distinct panic sites and assertions."""
    cargo_log = """
running 3 tests
test test_auth ... FAILED
test test_db ... FAILED
test test_cache ... ok

failures:

---- test_auth stdout ----
thread 'test_auth' panicked at src/auth.rs:42:9:
assertion `left == right` failed
  left: "unauthorized"
 right: "authorized"

---- test_db stdout ----
thread 'test_db' panicked at src/db.rs:105:13:
assertion `left == right` failed
  left: 500
 right: 200

failures:
    test_auth
    test_db

test result: FAILED. 1 passed; 2 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.05s
"""
    ingest = ingest_bytes(cargo_log.encode("utf-8"))
    blocks = parse_test_log_blocks(ingest)

    # 1 summary header + 2 failure blocks
    fail_blocks = [
        b
        for b in blocks
        if b.metadata.get("runner") == "cargo" and b.block_id.endswith("_test_failure")
    ]
    assert len(fail_blocks) == 2, f"Expected 2 failure blocks, got {len(fail_blocks)}"

    auth_block = next(b for b in fail_blocks if "test_auth" in b.text)
    db_block = next(b for b in fail_blocks if "test_db" in b.text)

    # Verify distinct locations
    assert "src/auth.rs:42:9" in auth_block.text
    assert "src/db.rs:105:13" in db_block.text

    # Verify distinct assertions
    assert 'exp: "authorized" got: "unauthorized"' in auth_block.text
    assert "exp: 200 got: 500" in db_block.text


def test_pytest_multi_failure_distinct_locations():
    """Verify that multiple pytest test failures receive their distinct failure locations."""
    pytest_log = """
============================= test session starts ==============================
rootdir: /app
collected 3 items

tests/test_api.py .FF                                                    [100%]

=================================== FAILURES ===================================
_________________________________ test_login ___________________________________

    def test_login():
>       assert response.status_code == 200
E       assert 401 == 200

tests/test_api.py:18: AssertionError
_________________________________ test_token ___________________________________

    def test_token():
>       assert token.is_valid() == True
E       assert False == True

tests/test_api.py:35: AssertionError
=========================== short test summary info ============================
FAILED tests/test_api.py::test_login - assert 401 == 200
FAILED tests/test_api.py::test_token - assert False == True
========================= 2 failed, 1 passed in 0.25s ==========================
"""
    ingest = ingest_bytes(pytest_log.encode("utf-8"))
    blocks = parse_test_log_blocks(ingest)

    fail_blocks = [
        b
        for b in blocks
        if b.metadata.get("runner") == "pytest" and b.block_id.endswith("_test_failure")
    ]
    assert len(fail_blocks) == 2, f"Expected 2 failure blocks, got {len(fail_blocks)}"

    login_block = next(b for b in fail_blocks if "test_login" in b.text)
    token_block = next(b for b in fail_blocks if "test_token" in b.text)

    assert "tests/test_api.py:18" in login_block.text
    assert "tests/test_api.py:35" in token_block.text
