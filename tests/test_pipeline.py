# tests/test_pipeline.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.llm_mock import run_stage

@pytest.mark.asyncio
async def test_pipeline_runs_and_is_deterministic(monkeypatch):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        job_payload = {"raw_text":"SQL Power BI Data Analyst role SQL Python"}
        resume_payload = {"file_text":"Experienced with SQL and Power BI and dashboards"}
        # call assessment endpoint
        r = await client.post("/api/v1/assess", json={"job_payload": job_payload, "resume_payload": resume_payload, "seed": 123})
        assert r.status_code == 200
        data1 = r.json()
        # call again with same payload & seed
        r2 = await client.post("/api/v1/assess", json={"job_payload": job_payload, "resume_payload": resume_payload, "seed": 123})
        assert r2.status_code == 200
        data2 = r2.json()
        # deterministic: stage outputs should be equal
        assert data1["stages"] == data2["stages"]
        # final score consistent
        assert data1["final_score"] == data2["final_score"]
