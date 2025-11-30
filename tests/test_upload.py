# tests/test_upload.py
import pytest
import io
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_protected_upload(monkeypatch):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # create user & get token
        r = await ac.post("/auth/signup", json={"email":"uploader@test.com","password":"pass123"})
        token = r.json()["access_token"]

        # monkeypatch store_file to simulate storage
        fake_store = AsyncMock(return_value="fake-key.pdf")
        monkeypatch.setattr("app.api.v1.uploads.store_file", fake_store)

        # monkeypatch enqueue_stream_job to avoid real Redis
        import app.services.queue as queue_mod
        monkeypatch.setattr(queue_mod, "enqueue_stream_job", AsyncMock())

        files = {"file": ("resume.pdf", b"PDFDATA", "application/pdf")}
        headers = {"Authorization": f"Bearer {token}"}
        resp = await ac.post("/api/v1/upload-resume", files=files, headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "resume_id" in body
        assert body["storage_key"] == "fake-key.pdf"
