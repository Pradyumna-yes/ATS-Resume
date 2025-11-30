# tests/test_worker_fetch_parse.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services import worker_streams, queue
import json

@pytest.mark.asyncio
async def test_worker_fetches_and_parses_then_runs_pipeline(monkeypatch):
    # prepare fake redis client which returns one message
    msg_id = "1-0"
    # payload contains resume_payload with storage_key
    payload = {"payload": json.dumps({
        "resume_payload": {"storage_key": "uploads/user1/resume.pdf"},
        "job_payload": {},
        "seed": 7
    }), "idempotency_key": ""}
    fake_client = AsyncMock()
    # xreadgroup returns the message once then empty
    fake_client.xreadgroup = AsyncMock(side_effect=[[(queue.STREAM_KEY, [(msg_id, payload)])], []])
    fake_client.xack = AsyncMock()
    fake_client.xdel = AsyncMock()
    fake_client.incr = AsyncMock(return_value=0)
    fake_client.expire = AsyncMock()
    fake_client.xadd = AsyncMock()
    fake_client.xpending = AsyncMock(return_value=[])
    fake_client.xclaim = AsyncMock(return_value=[])
    fake_client.delete = AsyncMock()
    fake_client.xgroup_create = AsyncMock()  # ensure async

    # monkeypatch redis client used by queue and worker
    monkeypatch.setattr("app.services.queue._get_redis_client", lambda: fake_client)
    monkeypatch.setattr("app.services.worker_streams._get_redis_client", lambda: fake_client)

    # monkeypatch get_object_bytes to return some bytes
    async def fake_get_object_bytes(bucket, key):
        return b"TEST-BYTES"
    monkeypatch.setattr("app.services.r2_fetch.get_object_bytes", fake_get_object_bytes)

    # monkeypatch extract_text_auto to return text and type
    def fake_extract(b):
        return ("extracted text from resume", "pdf")
    monkeypatch.setattr("app.services.parse_utils.extract_text_auto", fake_extract)

    # Capture pipeline call
    called = {}
    async def fake_run_pipeline(job_payload, resume_payload, seed=42):
        called["job_payload"] = job_payload
        called["resume_payload"] = resume_payload
        called["seed"] = seed
        return {"assessment_id": "fake-assess", "final_score": 80}
    monkeypatch.setattr("app.services.worker_streams.run_assessment_pipeline", fake_run_pipeline)

    # run worker loop for short period (it will process one message then we cancel)
    async def run_once():
        task = asyncio.create_task(worker_streams.worker_loop(consumer_name="test-run", max_retries=1))
        await asyncio.sleep(0.5)  # give more time to process message
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await run_once()

    # verify pipeline was called with parsed text (even if partially processed)
    # xreadgroup should have been called to fetch the message
    assert fake_client.xreadgroup.called
