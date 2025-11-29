# tests/test_smoke_api.py
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_job_and_resume_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        job_payload = {"raw_text": "SmokeTest: Data Scientist JD - Python, SQL"}
        r = await ac.post("/api/v1/jobs", json=job_payload)
        assert r.status_code == 200
        job = r.json()
        assert "id" in job or "_id" in job

        resume_payload = {"original_filename": "smoke_resume.pdf", "storage_key": "smoke-key"}
        r2 = await ac.post("/api/v1/resumes/db-save", json=resume_payload)
        assert r2.status_code == 200
        res = r2.json()
        assert "id" in res or "_id" in res

        # GET back
        job_id = job.get("id") or job.get("_id")
        r3 = await ac.get(f"/api/v1/jobs/{job_id}")
        assert r3.status_code == 200

        resume_id = res.get("id") or res.get("_id")
        r4 = await ac.get(f"/api/v1/resumes/{resume_id}")
        assert r4.status_code == 200
