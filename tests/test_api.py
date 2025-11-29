# tests/test_api.py
import os
import io
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import UploadFile
from app.main import app

# use pytest-asyncio
@pytest.mark.asyncio
async def test_upload_resume_monkeypatched(monkeypatch):
    """
    Test upload-resume endpoint by monkeypatching store_file to return a fake key.
    """
    async def fake_store_file(file: UploadFile):
        # simulate storing and return a fake key string
        # we can also verify file.filename and content type
        content = await file.read()
        assert content  # ensure file content was forwarded
        return "fake-key-1234.pdf"

    # monkeypatch the store_file in the API routes module where it's used
    import app.api.v1.routes as routes_mod
    monkeypatch.setattr(routes_mod, "store_file", fake_store_file)

    test_file_bytes = b"PDF-TEST-CONTENT"
    files = {"file": ("test_resume.pdf", test_file_bytes, "application/pdf")}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.post("/api/v1/upload-resume", files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert "resume_id" in body
        assert body["filename"] == "test_resume.pdf"
        assert body["storage_key"] == "fake-key-1234.pdf"
