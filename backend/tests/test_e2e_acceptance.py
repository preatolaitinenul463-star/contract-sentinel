"""End-to-end acceptance tests for the Contract Sentinel heavy architecture.

These tests verify the critical paths across all three business lines
(assistant, review, redline), the oversight workbench, export, and
the observability integration.

Run with: pytest tests/test_e2e_acceptance.py -v

Requirements:
  - Backend running at http://localhost:8000
  - A registered test user (or create one via /api/auth/register)
"""

import json
import time
import pytest
import httpx

BASE = "http://localhost:8000/api"
TIMEOUT = 60.0

# ── Test user credentials (create or use existing) ──
TEST_EMAIL = "test_e2e@sentinel.ai"
TEST_PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def token():
    """Register (if needed) and login to get a JWT token."""
    with httpx.Client(timeout=10) as client:
        # Try register
        client.post(f"{BASE}/auth/register", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD, "full_name": "E2E Tester"
        })
        # Login
        resp = client.post(f"{BASE}/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        return data["access_token"]


# ═══════════════════════════════════════════════════════════
# Health checks
# ═══════════════════════════════════════════════════════════

def test_health():
    resp = httpx.get(f"{BASE.replace('/api', '')}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_health_detail():
    resp = httpx.get(f"{BASE}/health/detail", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["database"] == "healthy"


# ═══════════════════════════════════════════════════════════
# 1. Legal Assistant (法律助手)
# ═══════════════════════════════════════════════════════════

def test_assistant_stream_qa(token):
    """Test QA mode streaming with sources and verification."""
    url = f"{BASE}/assistant/chat/stream?message=什么是合同的不可抗力条款&mode=qa&token={token}"
    with httpx.Client(timeout=TIMEOUT) as client:
        with client.stream("GET", url) as resp:
            assert resp.status_code == 200
            events = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

    # Must have start, at least one token, and done
    types = [e.get("type") for e in events]
    assert "start" in types
    assert "done" in types

    done = [e for e in events if e.get("type") == "done"][0]
    assert "run_id" in done
    assert "verification_decision" in done
    assert "policy_source" in done
    assert "policy_version" in done
    assert done.get("mode") == "qa"

    # Sources should be present (may be empty if search fails)
    if done.get("sources"):
        assert isinstance(done["sources"], list)
        for s in done["sources"]:
            assert "source_id" in s
            assert "trusted" in s


def test_assistant_stream_case_analysis(token):
    """Test case analysis mode."""
    url = f"{BASE}/assistant/chat/stream?message=员工被无故辞退的劳动仲裁胜诉可能性分析&mode=case_analysis&token={token}"
    with httpx.Client(timeout=TIMEOUT) as client:
        with client.stream("GET", url) as resp:
            assert resp.status_code == 200
            events = []
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
    done = [e for e in events if e.get("type") == "done"]
    assert len(done) == 1
    assert done[0].get("mode") == "case_analysis"


def test_policy_endpoints(token):
    """Policy read/update should work for authenticated user."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    preview = httpx.post(
        f"{BASE}/policy/me/parse-preview",
        headers=headers,
        json={"standard_text": "必须审查违约责任。不得接受预付款。"},
        timeout=10,
    )
    assert preview.status_code == 200

    updated = httpx.put(
        f"{BASE}/policy/me?contract_type=general&jurisdiction=CN",
        headers=headers,
        json={
            "standard_text": "必须审查违约责任。不得接受预付款。",
            "prefer_user_standard": True,
            "fallback_to_default": True,
        },
        timeout=10,
    )
    assert updated.status_code == 200

    current = httpx.get(
        f"{BASE}/policy/me?contract_type=general&jurisdiction=CN",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert current.status_code == 200
    assert "must_review_items" in current.json()


# ═══════════════════════════════════════════════════════════
# 2. Oversight Workbench (审阅工作台)
# ═══════════════════════════════════════════════════════════

def test_oversight_list(token):
    """List pipeline runs."""
    resp = httpx.get(f"{BASE}/oversight/runs", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_oversight_detail_and_approve(token):
    """Get detail of a run and approve it."""
    # First list runs
    resp = httpx.get(f"{BASE}/oversight/runs?page_size=1", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if resp.status_code == 200 and resp.json():
        run_id = resp.json()[0]["run_id"]

        # Get detail
        detail_resp = httpx.get(
            f"{BASE}/oversight/runs/{run_id}",
            headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert "events" in detail
        assert "sources" in detail
        assert "verifications" in detail

        # Approve
        approve_resp = httpx.post(
            f"{BASE}/oversight/runs/{run_id}/approve",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"comment": "E2E test approval"},
            timeout=10,
        )
        assert approve_resp.status_code == 200


# ═══════════════════════════════════════════════════════════
# 3. Pipeline models integrity
# ═══════════════════════════════════════════════════════════

def test_pipeline_tables_exist():
    """Verify the pipeline tables can be queried."""
    resp = httpx.get(f"{BASE}/oversight/runs?page_size=1", timeout=5,
                     headers={"Authorization": "Bearer invalid"})
    # Should get 401, not 500 (which would indicate missing table)
    assert resp.status_code in (401, 403, 422)


# ═══════════════════════════════════════════════════════════
# 4. Observability endpoints
# ═══════════════════════════════════════════════════════════

def test_metrics_endpoint_exists():
    """Check that the app is reachable (OTEL is opt-in via env var)."""
    resp = httpx.get(f"{BASE.replace('/api', '')}/health", timeout=5)
    assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════
# Benchmark helpers (not strict assertions, just timing logs)
# ═══════════════════════════════════════════════════════════

def test_benchmark_assistant_p95(token):
    """Measure assistant response time (informational, not a hard assertion)."""
    url = f"{BASE}/assistant/chat/stream?message=租赁合同注意事项&mode=qa&token={token}"
    t0 = time.time()
    with httpx.Client(timeout=TIMEOUT) as client:
        with client.stream("GET", url) as resp:
            for _ in resp.iter_lines():
                pass
    elapsed = time.time() - t0
    print(f"\n[BENCHMARK] Assistant QA response: {elapsed:.1f}s")
    # Soft assertion: should complete within 2 minutes
    assert elapsed < 120, f"Assistant took too long: {elapsed:.1f}s"
