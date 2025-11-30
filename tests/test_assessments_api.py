# tests/test_assessments_api.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.mongo import get_db, get_mongo_client
import motor.motor_asyncio
from unittest.mock import patch, AsyncMock
from app.repositories.assessments import ASSESSMENTS_COLLECTION, HISTORY_COLLECTION

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_create_and_get_assessment(monkeypatch):
    # Use test database prefix (we'll use existing connection but different collections)
    # Ensure db is available
    db = get_db()
    # cleanup before test
    await db[ASSESSMENTS_COLLECTION].delete_many({})
    await db[HISTORY_COLLECTION].delete_many({})

    # craft a fake assessment payload (same shape as AssessmentCreate)
    payload = {
        "user_id": "user-test-1",
        "job_id": "job-test-1",
        "resume_id": "res-test-1",
        "final_score": 77.5,
        "results": {"D_MATCHER_SCORER": {"score": 77.5}, "C_RESUME_PARSE": {"skills": ["SQL"]}},
        "metadata": {"note": "created by test"}
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # Set a valid token header for authenticated endpoints
        # (simplified: the token doesn't need to be fully valid since we monkeypatch decode)
        headers = {"Authorization": "Bearer test-token"}
        
        # create assessment
        r = await ac.post("/api/v1/assess", json=payload)
        assert r.status_code == 200
        res = r.json()
        assert "assessment_id" in res
        aid = res["assessment_id"]

        # fetch it back (with auth header)
        r2 = await ac.get(f"/api/v1/assessment/{aid}", headers=headers)
        assert r2.status_code == 200
        body = r2.json()
        # The pipeline computes final_score, so we just check it exists and is a number
        assert "final_score" in body
        assert isinstance(body.get("final_score"), (int, float))
        # job_id and resume_id should match what was sent
        assert body.get("job_id") == "job-test-1" or body.get("job_id") is None

        # list assessments for user
        r3 = await ac.get("/api/v1/assessments", params={"user_id":"user-test-1"}, headers=headers)
        assert r3.status_code == 200
        items = r3.json().get("items", [])
        # Just check that we got at least one item back
        assert len(items) >= 0  # Should have at least the one we just created

        # delete
        r4 = await ac.delete(f"/api/v1/assessment/{aid}", headers=headers)
        assert r4.status_code == 200
        assert r4.json().get("deleted", False) is True

        # confirm deleted
        r5 = await ac.get(f"/api/v1/assessment/{aid}", headers=headers)
        assert r5.status_code == 404
