"""Integration tests for Review API endpoints.

Note: These tests mock the LLM provider since we don't want real API calls in tests.
Tests that require real LLM calls are marked with pytest.mark.skip.
"""
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.asyncio
class TestReviewAPI:
    """Test review endpoints."""

    async def test_health_endpoint(self, app):
        """Health endpoint should be accessible."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

    async def test_root_endpoint(self, app):
        """Root endpoint should return app info."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "ContractSentinel"
            assert data["status"] == "running"

    async def test_export_nonexistent_review(self, app):
        """Export should return 404 for non-existent review."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/review/export/99999")
            assert response.status_code == 404

    @pytest.mark.skip(reason="Requires real LLM API key")
    async def test_upload_and_review_stream(self, app):
        """Upload-and-review should return SSE stream with complete event containing review_id.
        
        This test requires a real DeepSeek API key and is skipped by default.
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create a test text file
            files = {
                "file": ("test_contract.txt", b"This is a test contract.", "text/plain"),
            }
            data = {
                "contract_type": "general",
                "jurisdiction": "CN",
            }

            response = await client.post(
                "/api/review/upload-and-review",
                files=files,
                data=data,
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            # Parse SSE events
            events = []
            for line in response.text.split("\n"):
                if line.startswith("data: "):
                    import json
                    events.append(json.loads(line[6:]))

            # Should have a complete event
            complete_events = [e for e in events if e.get("stage") == "complete"]
            assert len(complete_events) == 1
            assert "review_id" in complete_events[0]
            assert "all_risks" in complete_events[0]


@pytest.mark.asyncio
class TestCompareAPI:
    """Test compare endpoints."""

    async def test_list_comparisons_requires_auth(self, app):
        """Listing comparisons should require authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/compare")
            assert response.status_code in (401, 403)

    async def test_get_nonexistent_comparison(self, app):
        """Getting a non-existent comparison should return 401/404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/compare/99999")
            assert response.status_code in (401, 403, 404)


@pytest.mark.asyncio
class TestAssistantAPI:
    """Test assistant endpoints."""

    async def test_chat_stream_empty_message(self, app):
        """Should reject empty message."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/assistant/chat/stream?message=")
            assert response.status_code == 400

    async def test_sessions_requires_auth(self, app):
        """Session endpoints should require authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/assistant/sessions")
            assert response.status_code in (401, 403)

    async def test_create_session_with_auth(self, app):
        """Should create a session when authenticated."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register + Login
            await client.post(
                "/api/auth/register",
                json={"email": "chat@example.com", "password": "ChatPass123"},
            )
            login_resp = await client.post(
                "/api/auth/login",
                json={"email": "chat@example.com", "password": "ChatPass123"},
            )
            token = login_resp.json()["access_token"]

            # Create session
            response = await client.post(
                "/api/assistant/sessions?title=测试会话",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "测试会话"
            assert "id" in data

            # List sessions
            list_resp = await client.get(
                "/api/assistant/sessions",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert list_resp.status_code == 200
            sessions = list_resp.json()
            assert len(sessions) >= 1
