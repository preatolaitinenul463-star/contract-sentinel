"""Integration tests for Auth API."""
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.asyncio
class TestAuthAPI:
    """Test authentication endpoints."""

    async def test_register_success(self, app):
        """Should register a new user successfully."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/auth/register",
                json={
                    "email": "newuser@example.com",
                    "password": "TestPassword123",
                    "full_name": "Test User",
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["full_name"] == "Test User"
            assert "hashed_password" not in data

    async def test_register_duplicate_email(self, app):
        """Should reject duplicate email registration."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register first time
            await client.post(
                "/api/auth/register",
                json={"email": "dup@example.com", "password": "Password123"},
            )
            # Try again with same email
            response = await client.post(
                "/api/auth/register",
                json={"email": "dup@example.com", "password": "Password456"},
            )
            assert response.status_code == 400
            assert "已被注册" in response.json()["detail"]

    async def test_login_success(self, app):
        """Should login with correct credentials and get JWT token."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register
            await client.post(
                "/api/auth/register",
                json={"email": "login@example.com", "password": "MyPassword123"},
            )
            # Login
            response = await client.post(
                "/api/auth/login",
                json={"email": "login@example.com", "password": "MyPassword123"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["expires_in"] > 0

    async def test_login_wrong_password(self, app):
        """Should reject login with wrong password."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register
            await client.post(
                "/api/auth/register",
                json={"email": "wrongpw@example.com", "password": "CorrectPass"},
            )
            # Login with wrong password
            response = await client.post(
                "/api/auth/login",
                json={"email": "wrongpw@example.com", "password": "WrongPass"},
            )
            assert response.status_code == 401

    async def test_get_me_with_token(self, app):
        """Should return user info with valid JWT token."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Register + Login
            await client.post(
                "/api/auth/register",
                json={"email": "me@example.com", "password": "TestPass123", "full_name": "Me User"},
            )
            login_resp = await client.post(
                "/api/auth/login",
                json={"email": "me@example.com", "password": "TestPass123"},
            )
            token = login_resp.json()["access_token"]

            # Get /me
            response = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "me@example.com"
            assert data["full_name"] == "Me User"

    async def test_get_me_without_token(self, app):
        """Should reject /me without token."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/auth/me")
            assert response.status_code in (401, 403)
