# tests/test_pipeline_parser_integration.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_pipeline_uses_parser(monkeypatch):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # create a minimal job + resume payload
        job_payload = {"raw_text": "Data Analyst role requiring SQL"}
        resume_payload = {"file_text": "John Doe\nSkills\nSQL, Python\nExperience\nData Analyst — Acme\n2019 - 2021\n- Did SQL work"}
        # call the assess endpoint (pipeline route)
        r = await ac.post("/api/v1/assess", json={"job_payload": job_payload, "resume_payload": resume_payload, "seed": 11})
        assert r.status_code == 200
        data = r.json()
        # stage C should be present coming from parser
        assert "C_RESUME_PARSE" in data["stages"]
        cstage = data["stages"]["C_RESUME_PARSE"]
        assert "skills" in cstage or "experience" in cstage
