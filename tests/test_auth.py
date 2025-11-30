# tests/test_auth.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_signup_and_login():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # Signup
        r = await ac.post("/auth/signup", json={"email":"smoke@test.com","password":"secret123"})
        assert r.status_code in (200,201)
        data = r.json()
        assert "access_token" in data

        # Login
        r2 = await ac.post("/auth/login", json={"email":"smoke@test.com","password":"secret123"})
        assert r2.status_code == 200
        assert "access_token" in r2.json()
